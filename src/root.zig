const std = @import("std");

pub const lexer = @import("lexer.zig");
pub const ast = @import("ast.zig");
pub const parser = @import("parser.zig");
pub const runtime = @import("runtime.zig");
pub const codegen = @import("codegen.zig");
pub const vm = @import("vm.zig");

pub const Value = runtime.Value;
pub const Runtime = runtime.Runtime;
pub const EngageVM = vm.EngageVM;

// ============================================================================
// C ABI for Embedding Engage in Software and Games (include/engage.h)
// ============================================================================

pub const EngageHostNumFn = *const fn (arg: f64, userdata: ?*anyopaque) callconv(.c) f64;

const CHostCallbackCtx = struct {
    func: EngageHostNumFn,
    userdata: ?*anyopaque,
};

fn cHostTrampoline(_: *Runtime, args: []const Value, raw_ctx: ?*anyopaque) anyerror!Value {
    const ctx: *const CHostCallbackCtx = @ptrCast(@alignCast(raw_ctx.?));
    const arg0 = if (args.len > 0) args[0].asNumber() else 0.0;
    const res = ctx.func(arg0, ctx.userdata);
    return Value.fromNumber(res);
}

pub export fn engage_vm_new() ?*EngageVM {
    const ptr = std.heap.smp_allocator.create(EngageVM) catch return null;
    ptr.* = EngageVM.init(std.heap.smp_allocator, null);
    return ptr;
}

pub export fn engage_vm_free(handle: ?*EngageVM) void {
    if (handle) |h| {
        h.deinit();
        std.heap.smp_allocator.destroy(h);
    }
}

pub export fn engage_eval(handle: ?*EngageVM, source_ptr: [*]const u8, source_len: usize) i32 {
    const h = handle orelse return -1;
    const src = source_ptr[0..source_len];
    _ = h.eval(src) catch return 1;
    return 0;
}

pub export fn engage_set_global_num(handle: ?*EngageVM, name_ptr: [*]const u8, name_len: usize, value: f64) i32 {
    const h = handle orelse return -1;
    h.setGlobal(name_ptr[0..name_len], Value.fromNumber(value)) catch return 1;
    return 0;
}

pub export fn engage_get_global_num(handle: ?*EngageVM, name_ptr: [*]const u8, name_len: usize) f64 {
    const h = handle orelse return 0.0;
    if (h.getGlobal(name_ptr[0..name_len])) |v| {
        return v.asNumber();
    }
    return 0.0;
}

pub export fn engage_set_global_str(
    handle: ?*EngageVM,
    name_ptr: [*]const u8,
    name_len: usize,
    val_ptr: [*]const u8,
    val_len: usize,
) i32 {
    const h = handle orelse return -1;
    const alloc = h.allocator();
    const dup_val = alloc.dupe(u8, val_ptr[0..val_len]) catch return 1;
    h.setGlobal(name_ptr[0..name_len], Value.fromString(dup_val)) catch return 1;
    return 0;
}

pub export fn engage_register_num_fn(
    handle: ?*EngageVM,
    name_ptr: [*]const u8,
    name_len: usize,
    callback: EngageHostNumFn,
    userdata: ?*anyopaque,
) i32 {
    const h = handle orelse return -1;
    const alloc = h.allocator();
    const ctx = alloc.create(CHostCallbackCtx) catch return 1;
    ctx.* = .{ .func = callback, .userdata = userdata };
    h.registerFn(name_ptr[0..name_len], cHostTrampoline, ctx) catch return 1;
    return 0;
}

pub export fn engage_call_num1(handle: ?*EngageVM, fn_ptr: [*]const u8, fn_len: usize, arg0: f64) f64 {
    const h = handle orelse return 0.0;
    const res = h.call(fn_ptr[0..fn_len], &.{Value.fromNumber(arg0)}) catch return 0.0;
    return res.asNumber();
}

pub export fn engage_call_num0(handle: ?*EngageVM, fn_ptr: [*]const u8, fn_len: usize) f64 {
    const h = handle orelse return 0.0;
    const res = h.call(fn_ptr[0..fn_len], &.{}) catch return 0.0;
    return res.asNumber();
}

// ============================================================================
// Tests
// ============================================================================

test {
    _ = lexer;
    _ = parser;
}

test "VM executes fibonacci, tables, vectors, records, and Result error unwinding" {
    var evm = EngageVM.init(std.testing.allocator, std.testing.io);
    defer evm.deinit();

    var captured: std.ArrayList(u8) = .empty;
    evm.rt.output_capture = &captured;

    _ = try evm.eval(
        \\let cache be Table.
        \\
        \\define a record named Counter:
        \\    let count be 0.
        \\    to add with delta:
        \\        set self.count to self.count plus delta.
        \\        return self.count.
        \\    end
        \\    to current:
        \\        return self.count.
        \\    end
        \\end
        \\
        \\to safe_div with a, b:
        \\    if b is equal to 0 then
        \\        return Error with "division by zero".
        \\    end
        \\    return Ok with (a divided by b).
        \\end
        \\
        \\to compute_ratio with x, y:
        \\    let q be (safe_div with x, y) or return error.
        \\    return Ok with (q times 10).
        \\end
        \\
        \\let c be new Counter with count: 5.
        \\let updated be c.add with 7.
        \\print with "counter=" concatenated with (to_string with c.current).
        \\
        \\let r1 be compute_ratio with 20, 4.
        \\if r1 is an Ok then
        \\    print with "r1=" concatenated with (to_string with (the ok value of r1)).
        \\end
        \\
        \\let r2 be compute_ratio with 20, 0.
        \\if r2 is an Error then
        \\    print with "r2_err=" concatenated with (the error message of r2).
        \\end
    );

    try std.testing.expectEqualStrings(
        "counter=12\nr1=50\nr2_err=division by zero\n",
        captured.items,
    );
}

test "VM supports fibers and channels" {
    var evm = EngageVM.init(std.testing.allocator, std.testing.io);
    defer evm.deinit();

    var captured: std.ArrayList(u8) = .empty;
    evm.rt.output_capture = &captured;

    _ = try evm.eval(
        \\define a fiber named ticker:
        \\    yield with 10.
        \\    yield with 20.
        \\    return 30.
        \\end
        \\
        \\let a be call ticker.
        \\let b be call ticker.
        \\let c be call ticker.
        \\print with a, b, c.
        \\
        \\create a channel named jobs.
        \\send "task_alpha" through jobs.
        \\let msg be receive from jobs.
        \\print with msg.
    );

    try std.testing.expectEqualStrings(
        "10 20 30\ntask_alpha\n",
        captured.items,
    );
}

test "Embeddable scripting API (Zig and C ABI) for game loops" {
    // 1. Native Zig Embedding API
    var evm = EngageVM.init(std.testing.allocator, std.testing.io);
    defer evm.deinit();

    const HostState = struct {
        score_multiplier: f64 = 3.0,
        fn boostScore(_: *Runtime, args: []const Value, ud: ?*anyopaque) anyerror!Value {
            const self_state: *const @This() = @ptrCast(@alignCast(ud.?));
            const base = if (args.len > 0) args[0].asNumber() else 0.0;
            return Value.fromNumber(base * self_state.score_multiplier);
        }
    };
    var host_state = HostState{};
    try evm.registerFn("boost_score", HostState.boostScore, &host_state);
    try evm.setGlobal("player_x", Value.fromNumber(10.0));

    _ = try evm.eval(
        \\to on_step with dt:
        \\    let bonus be boost_score with dt.
        \\    set player_x to player_x plus bonus.
        \\    return player_x.
        \\end
    );

    const new_x = try evm.call("on_step", &.{Value.fromNumber(5.0)});
    try std.testing.expectEqual(@as(f64, 25.0), new_x.asNumber());
    try std.testing.expectEqual(@as(f64, 25.0), evm.getGlobal("player_x").?.asNumber());

    // 2. C ABI Embedding test
    const c_vm = engage_vm_new();
    defer engage_vm_free(c_vm);
    const script = "to double_it with v:\n return v times 2.\nend";
    try std.testing.expectEqual(@as(i32, 0), engage_eval(c_vm, script.ptr, script.len));
    const fn_name = "double_it";
    try std.testing.expectEqual(@as(f64, 42.0), engage_call_num1(c_vm, fn_name.ptr, fn_name.len, 21.0));
}

test "Zig codegen produces valid Zig output for Engage programs" {
    var arena = std.heap.ArenaAllocator.init(std.testing.allocator);
    defer arena.deinit();

    const prog = try parser.parseSource(
        arena.allocator(),
        \\to add with a, b:
        \\    return a plus b.
        \\end
        \\define a fiber named counter:
        \\    yield 10.
        \\    yield 20.
        \\    return 30.
        \\end
        \\print with (add with 20, 22).
        \\let step1 be call counter.
    );
    const zig_code = try codegen.generateZigSource(arena.allocator(), prog);
    try std.testing.expect(std.mem.indexOf(u8, zig_code, "fn engage_fn_add(") != null);
    try std.testing.expect(std.mem.indexOf(u8, zig_code, "fn engage_fiber_counter(") != null);
    try std.testing.expect(std.mem.indexOf(u8, zig_code, "stepFiber") != null);
    try std.testing.expect(std.mem.indexOf(u8, zig_code, "pub fn main(init: std.process.Init) !void") != null);
}

test "Switch statement desugaring, sparse vector padding, table size, and fiber loops" {
    var evm = EngageVM.init(std.testing.allocator, std.testing.io);
    defer evm.deinit();

    // 1. Switch statement test
    const switch_res = try evm.eval(
        \\to test_switch with code:
        \\    switch on code:
        \\        case 1:
        \\            return "ONE".
        \\        case 2:
        \\            return "TWO".
        \\        otherwise:
        \\            return "OTHER".
        \\    end
        \\end
        \\let r1 be test_switch with 1.
        \\let r2 be test_switch with 2.
        \\let r3 be test_switch with 99.
    );
    _ = switch_res;
    try std.testing.expectEqualStrings("ONE", evm.getGlobal("r1").?.string);
    try std.testing.expectEqualStrings("TWO", evm.getGlobal("r2").?.string);
    try std.testing.expectEqualStrings("OTHER", evm.getGlobal("r3").?.string);

    // 2. Sparse vector indexing and .length/.size member properties
    _ = try evm.eval(
        \\let sparse_vec be Vector.
        \\set sparse_vec[2] to "item2".
        \\let v_len be sparse_vec.length.
        \\let v_slot0 be sparse_vec[0].
        \\let v_slot2 be sparse_vec[2].
        \\let tbl be Table.
        \\set tbl["key1"] to "val1".
        \\set tbl["key2"] to "val2".
        \\let tbl_sz be tbl.size.
    );
    try std.testing.expectEqual(@as(f64, 3.0), evm.getGlobal("v_len").?.asNumber());
    try std.testing.expect(evm.getGlobal("v_slot0").? == .none);
    try std.testing.expectEqualStrings("item2", evm.getGlobal("v_slot2").?.string);
    try std.testing.expectEqual(@as(f64, 2.0), evm.getGlobal("tbl_sz").?.asNumber());

    // 3. Top-level variable update inside while loop
    _ = try evm.eval(
        \\let counter be 0.
        \\while counter is less than 5:
        \\    let counter be counter plus 1.
        \\end
    );
    try std.testing.expectEqual(@as(f64, 5.0), evm.getGlobal("counter").?.asNumber());

    // 4. Input queue and random_int
    try evm.rt.queueInput("PlayerOne");
    _ = try evm.eval(
        \\let user_name be input with "Enter name: ".
        \\let rnd be random_int with 10, 20.
    );
    try std.testing.expectEqualStrings("PlayerOne", evm.getGlobal("user_name").?.string);
    const rnd_val = evm.getGlobal("rnd").?.asNumber();
    try std.testing.expect(rnd_val >= 10.0 and rnd_val <= 20.0);
}

test "Zig FFI comptime reflection and callZigFn" {
    var arena = std.heap.ArenaAllocator.init(std.testing.allocator);
    defer arena.deinit();
    var rt = Runtime.init(arena.allocator(), null);

    const TestModule = struct {
        pub fn lerp(a: f64, b: f64, t: f64) f64 {
            return a + (b - a) * t;
        }
        pub fn addInts(x: i64, y: i64) i64 {
            return x + y;
        }
        pub fn greet(name: []const u8) []const u8 {
            return name;
        }
        pub fn isEven(n: i64) bool {
            return @mod(n, 2) == 0;
        }
        pub fn safeDiv(a: f64, b: f64) !f64 {
            if (b == 0.0) return error.DivisionByZero;
            return a / b;
        }
        pub fn getPtr(p: ?*anyopaque) ?*anyopaque {
            return p;
        }
    };

    // 1. Float lerp
    const r1 = try runtime.callZigFn(TestModule.lerp, &rt, &.{ Value.fromNumber(10.0), Value.fromNumber(20.0), Value.fromNumber(0.5) });
    try std.testing.expectEqual(@as(f64, 15.0), r1.asNumber());

    // 2. Ints
    const r2 = try runtime.callZigFn(TestModule.addInts, &rt, &.{ Value.fromNumber(40.0), Value.fromNumber(2.0) });
    try std.testing.expectEqual(@as(f64, 42.0), r2.asNumber());

    // 3. String
    const r3 = try runtime.callZigFn(TestModule.greet, &rt, &.{ Value.fromString("Engage") });
    try std.testing.expectEqualStrings("Engage", r3.string);

    // 4. Bool
    const r4 = try runtime.callZigFn(TestModule.isEven, &rt, &.{ Value.fromNumber(4.0) });
    try std.testing.expect(r4.isTruthy());

    // 5. Error union
    const r5_ok = try runtime.callZigFn(TestModule.safeDiv, &rt, &.{ Value.fromNumber(10.0), Value.fromNumber(2.0) });
    try std.testing.expect(r5_ok == .result and r5_ok.result.is_ok);
    try std.testing.expectEqual(@as(f64, 5.0), r5_ok.result.payload.asNumber());

    const r5_err = try runtime.callZigFn(TestModule.safeDiv, &rt, &.{ Value.fromNumber(10.0), Value.fromNumber(0.0) });
    try std.testing.expect(r5_err == .result and !r5_err.result.is_ok);
    try std.testing.expectEqualStrings("DivisionByZero", r5_err.result.payload.string);

    // 6. Pointer
    var dummy: u32 = 123;
    const r6 = try runtime.callZigFn(TestModule.getPtr, &rt, &.{ Value.fromPointer(&dummy) });
    try std.testing.expectEqual(@as(?*anyopaque, &dummy), r6.asPointer());
}

test "Extern declarations and codegen for Zig and C libraries" {
    var arena = std.heap.ArenaAllocator.init(std.testing.allocator);
    defer arena.deinit();

    const prog = try parser.parseSource(
        arena.allocator(),
        \\from "custom_math.zig" import fast_lerp, fib_zig.
        \\extern from "native_physics.c" to calc_velocity with mass: Number, force: Number returns Number.
        \\let v be calc_velocity with 10, 50.
        \\let l be fast_lerp with 0, 100, 0.25.
    );

    try std.testing.expectEqual(@as(usize, 4), prog.statements.len);

    const bundled = try parser.parseAndBundle(arena.allocator(), null,
        \\from "custom_math.zig" import fast_lerp, fib_zig.
        \\extern from "native_physics.c" to calc_velocity with mass: Number, force: Number returns Number.
        \\let v be calc_velocity with 10, 50.
        \\let l be fast_lerp with 0, 100, 0.25.
    , ".");

    const zig_code = try codegen.generateZigSource(arena.allocator(), bundled);
    try std.testing.expect(std.mem.indexOf(u8, zig_code, "@import(\"./custom_math.zig\")") != null);
    try std.testing.expect(std.mem.indexOf(u8, zig_code, "fn engage_fn_fast_lerp(") != null);
    try std.testing.expect(std.mem.indexOf(u8, zig_code, "callZigFn(") != null);
    try std.testing.expect(std.mem.indexOf(u8, zig_code, "extern \"c\" fn calc_velocity(") != null);
    try std.testing.expect(std.mem.indexOf(u8, zig_code, "fn engage_fn_calc_velocity(") != null);
}
