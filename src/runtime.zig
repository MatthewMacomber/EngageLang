const std = @import("std");
const builtin = @import("builtin");

// Windows API externs for dynamic library loading
const HMODULE = *anyopaque;
const FARPROC = ?*anyopaque;
extern "kernel32" fn LoadLibraryA(lpLibFileName: [*:0]const u8) callconv(.winapi) ?HMODULE;
extern "kernel32" fn GetProcAddress(hModule: HMODULE, lpProcName: [*:0]const u8) callconv(.winapi) FARPROC;
extern "kernel32" fn FreeLibrary(hModule: HMODULE) callconv(.winapi) c_int;

pub const Vector = struct {
    items: std.ArrayList(Value) = .empty,
};

pub const Table = struct {
    map: std.StringArrayHashMapUnmanaged(Value) = .empty,
};

pub const RecordInstance = struct {
    type_name: []const u8,
    fields: std.StringArrayHashMapUnmanaged(Value) = .empty,
};

pub const Channel = struct {
    name: []const u8,
    queue: std.ArrayList(Value) = .empty,
};

pub const Fiber = struct {
    name: []const u8,
    ip: usize = 0,
    done: bool = false,
    user_data: ?*anyopaque = null,
    step_fn: ?*const fn (rt: *Runtime, fib: *Fiber) anyerror!Value = null,
    locals: std.StringArrayHashMapUnmanaged(Value) = .empty,
};

pub const ResultVal = struct {
    is_ok: bool,
    payload: *Value,
};

pub const Value = union(enum) {
    none,
    number: f64,
    string: []const u8,
    vector: *Vector,
    table: *Table,
    record: *RecordInstance,
    result: ResultVal,
    channel: *Channel,
    fiber: *Fiber,
    pointer: ?*anyopaque,

    pub fn fromNumber(n: f64) Value {
        return .{ .number = n };
    }

    pub fn fromBool(b: bool) Value {
        return .{ .number = if (b) 1.0 else 0.0 };
    }

    pub fn fromString(s: []const u8) Value {
        return .{ .string = s };
    }

    pub fn fromPointer(p: ?*anyopaque) Value {
        return .{ .pointer = p };
    }

    pub fn asPointer(self: Value) ?*anyopaque {
        return switch (self) {
            .pointer => |p| p,
            else => null,
        };
    }

    pub fn isTruthy(self: Value) bool {
        return switch (self) {
            .none => false,
            .number => |n| n != 0.0,
            .string => |s| s.len > 0,
            .vector => |v| v.items.items.len > 0,
            .table => |t| t.map.count() > 0,
            .result => |r| r.is_ok,
            .record, .channel, .fiber => true,
            .pointer => |p| p != null,
        };
    }

    pub fn asNumber(self: Value) f64 {
        return switch (self) {
            .number => |n| n,
            .string => |s| std.fmt.parseFloat(f64, std.mem.trim(u8, s, " \t\r\n")) catch 0.0,
            .result => |r| r.payload.asNumber(),
            else => 0.0,
        };
    }

    pub fn toString(self: Value, allocator: std.mem.Allocator) ![]const u8 {
        return switch (self) {
            .none => "None",
            .string => |s| s,
            .number => |n| blk: {
                const as_i64: i64 = @intFromFloat(n);
                if (@as(f64, @floatFromInt(as_i64)) == n and @abs(n) < 9e15) {
                    break :blk try std.fmt.allocPrint(allocator, "{d}", .{as_i64});
                }
                break :blk try std.fmt.allocPrint(allocator, "{d}", .{n});
            },
            .vector => |v| blk: {
                var out: std.ArrayList(u8) = .empty;
                try out.append(allocator, '[');
                for (v.items.items, 0..) |item, idx| {
                    if (idx > 0) try out.appendSlice(allocator, ", ");
                    try out.appendSlice(allocator, try item.toString(allocator));
                }
                try out.append(allocator, ']');
                break :blk try out.toOwnedSlice(allocator);
            },
            .table => |t| blk: {
                var out: std.ArrayList(u8) = .empty;
                try out.append(allocator, '{');
                var it = t.map.iterator();
                var first = true;
                while (it.next()) |entry| {
                    if (entry.value_ptr.* == .none) continue;
                    if (!first) try out.appendSlice(allocator, ", ");
                    first = false;
                    try out.appendSlice(allocator, entry.key_ptr.*);
                    try out.appendSlice(allocator, ": ");
                    try out.appendSlice(allocator, try entry.value_ptr.toString(allocator));
                }
                try out.append(allocator, '}');
                break :blk try out.toOwnedSlice(allocator);
            },
            .record => |r| try std.fmt.allocPrint(allocator, "<instance of {s}>", .{r.type_name}),
            .result => |r| try std.fmt.allocPrint(
                allocator,
                "{s}({s})",
                .{ if (r.is_ok) "Ok" else "Error", try r.payload.toString(allocator) },
            ),
            .channel => |c| try std.fmt.allocPrint(allocator, "<channel {s}>", .{c.name}),
            .fiber => |f| try std.fmt.allocPrint(allocator, "<fiber {s}>", .{f.name}),
            .pointer => |p| if (p) |addr| try std.fmt.allocPrint(allocator, "<pointer 0x{x}>", .{@intFromPtr(addr)}) else "null",
        };
    }

    pub fn typeName(self: Value) []const u8 {
        return switch (self) {
            .none => "None",
            .number => "Number",
            .string => "String",
            .vector => "Vector",
            .table => "Table",
            .record => |r| r.type_name,
            .result => |r| if (r.is_ok) "Ok" else "Error",
            .channel => "Channel",
            .fiber => "Fiber",
            .pointer => "Pointer",
        };
    }
};

pub const Runtime = struct {
    allocator: std.mem.Allocator,
    io: ?std.Io = null,
    cli_args: std.ArrayList(Value) = .empty,
    output_capture: ?*std.ArrayList(u8) = null,
    input_queue: std.ArrayList([]const u8) = .empty,
    game_objects: std.ArrayList(*RecordInstance) = .empty,
    prng: std.Random.DefaultPrng = std.Random.DefaultPrng.init(0x5eed_cafe_beef_1234),
    propagated_error: Value = .none,

    pub fn init(allocator: std.mem.Allocator, io: ?std.Io) Runtime {
        return .{
            .allocator = allocator,
            .io = io,
        };
    }

    pub fn touch(self: *Runtime) void {
        _ = self;
    }

    pub fn unwrapOrReturnError(self: *Runtime, val: Value) !Value {
        if (val == .result) {
            if (!val.result.is_ok) {
                self.propagated_error = val;
                return error.EngagePropagateError;
            }
            return val.result.payload.*;
        }
        return val;
    }

    pub fn makeVector(self: *Runtime) !Value {
        const v = try self.allocator.create(Vector);
        v.* = .{};
        return .{ .vector = v };
    }

    pub fn makeTable(self: *Runtime) !Value {
        const t = try self.allocator.create(Table);
        t.* = .{};
        return .{ .table = t };
    }

    pub fn makeRecord(self: *Runtime, type_name: []const u8) !*RecordInstance {
        const r = try self.allocator.create(RecordInstance);
        r.* = .{ .type_name = type_name };
        return r;
    }

    pub fn makeChannel(self: *Runtime, name: []const u8) !Value {
        const c = try self.allocator.create(Channel);
        c.* = .{ .name = name };
        return .{ .channel = c };
    }

    pub fn makeResult(self: *Runtime, is_ok: bool, val: Value) !Value {
        const ptr = try self.allocator.create(Value);
        ptr.* = val;
        return .{ .result = .{ .is_ok = is_ok, .payload = ptr } };
    }

    pub fn queueInput(self: *Runtime, text: []const u8) !void {
        try self.input_queue.append(self.allocator, text);
    }

    pub fn makeFiber(self: *Runtime, name: []const u8, step_fn: ?*const fn (rt: *Runtime, fib: *Fiber) anyerror!Value) !Value {
        const f = try self.allocator.create(Fiber);
        f.* = .{
            .name = name,
            .step_fn = step_fn,
        };
        return .{ .fiber = f };
    }

    pub fn stepFiber(self: *Runtime, fib_val: Value) anyerror!Value {
        if (fib_val != .fiber) return .none;
        const fib = fib_val.fiber;
        if (fib.done) return .none;
        if (fib.step_fn) |sfn| {
            return sfn(self, fib);
        }
        return .none;
    }

    // --- Operators ---

    pub fn add(self: *Runtime, a: Value, b: Value) !Value {
        if (a == .string or b == .string) {
            return self.concat(a, b);
        }
        return .{ .number = a.asNumber() + b.asNumber() };
    }

    pub fn sub(a: Value, b: Value) Value {
        return .{ .number = a.asNumber() - b.asNumber() };
    }

    pub fn mul(a: Value, b: Value) Value {
        return .{ .number = a.asNumber() * b.asNumber() };
    }

    pub fn div(a: Value, b: Value) Value {
        const denom = b.asNumber();
        if (denom == 0.0) return .{ .number = 0.0 };
        return .{ .number = a.asNumber() / denom };
    }

    pub fn mod(a: Value, b: Value) Value {
        const denom = b.asNumber();
        if (denom == 0.0) return .{ .number = 0.0 };
        return .{ .number = @rem(a.asNumber(), denom) };
    }

    pub fn neg(a: Value) Value {
        return .{ .number = -a.asNumber() };
    }

    pub fn concat(self: *Runtime, a: Value, b: Value) !Value {
        const sa = try a.toString(self.allocator);
        const sb = try b.toString(self.allocator);
        const joined = try std.fmt.allocPrint(self.allocator, "{s}{s}", .{ sa, sb });
        return .{ .string = joined };
    }

    pub fn eql(a: Value, b: Value) Value {
        return Value.fromBool(valuesEqual(a, b));
    }

    pub fn neq(a: Value, b: Value) Value {
        return Value.fromBool(!valuesEqual(a, b));
    }

    pub fn lt(a: Value, b: Value) Value {
        return Value.fromBool(a.asNumber() < b.asNumber());
    }

    pub fn gt(a: Value, b: Value) Value {
        return Value.fromBool(a.asNumber() > b.asNumber());
    }

    pub fn lte(a: Value, b: Value) Value {
        return Value.fromBool(a.asNumber() <= b.asNumber());
    }

    pub fn gte(a: Value, b: Value) Value {
        return Value.fromBool(a.asNumber() >= b.asNumber());
    }

    pub fn logicalAnd(a: Value, b: Value) Value {
        return Value.fromBool(a.isTruthy() and b.isTruthy());
    }

    pub fn logicalOr(a: Value, b: Value) Value {
        return Value.fromBool(a.isTruthy() or b.isTruthy());
    }

    pub fn logicalNot(a: Value) Value {
        return Value.fromBool(!a.isTruthy());
    }

    pub fn isAnOk(a: Value) Value {
        return switch (a) {
            .result => |r| Value.fromBool(r.is_ok),
            else => Value.fromBool(true),
        };
    }

    pub fn isAnError(a: Value) Value {
        return switch (a) {
            .result => |r| Value.fromBool(!r.is_ok),
            else => Value.fromBool(false),
        };
    }

    pub fn okValueOf(a: Value) Value {
        return switch (a) {
            .result => |r| r.payload.*,
            else => a,
        };
    }

    pub fn errorMessageOf(a: Value) Value {
        return switch (a) {
            .result => |r| r.payload.*,
            else => .none,
        };
    }

    pub fn indexGet(self: *Runtime, obj: Value, idx: Value) !Value {
        return switch (obj) {
            .vector => |v| blk: {
                const i_f = idx.asNumber();
                if (i_f < 0) break :blk .none;
                const i: usize = @intFromFloat(i_f);
                if (i >= v.items.items.len) break :blk .none;
                break :blk v.items.items[i];
            },
            .table => |t| blk: {
                const k = try idx.toString(self.allocator);
                break :blk t.map.get(k) orelse .none;
            },
            .record => |r| blk: {
                const k = try idx.toString(self.allocator);
                break :blk r.fields.get(k) orelse .none;
            },
            .string => |s| blk: {
                const i_f = idx.asNumber();
                if (i_f < 0) break :blk Value.fromString("");
                const i: usize = @intFromFloat(i_f);
                if (i >= s.len) break :blk Value.fromString("");
                break :blk Value.fromString(s[i .. i + 1]);
            },
            else => .none,
        };
    }

    pub fn indexSet(self: *Runtime, obj: Value, idx: Value, val: Value) !void {
        switch (obj) {
            .vector => |v| {
                const i_f = idx.asNumber();
                if (i_f < 0) return;
                const i: usize = @intFromFloat(i_f);
                if (i < v.items.items.len) {
                    v.items.items[i] = val;
                } else if (i == v.items.items.len) {
                    try v.items.append(self.allocator, val);
                } else {
                    while (v.items.items.len < i) {
                        try v.items.append(self.allocator, .none);
                    }
                    try v.items.append(self.allocator, val);
                }
            },
            .table => |t| {
                const k = try idx.toString(self.allocator);
                try t.map.put(self.allocator, k, val);
            },
            .record => |r| {
                const k = try idx.toString(self.allocator);
                try r.fields.put(self.allocator, k, val);
            },
            else => {},
        }
    }

    pub fn memberGet(obj: Value, member: []const u8) Value {
        return switch (obj) {
            .record => |r| r.fields.get(member) orelse .none,
            .table => |t| blk: {
                if (t.map.get(member)) |val| break :blk val;
                if (std.mem.eql(u8, member, "size") or std.mem.eql(u8, member, "length")) {
                    break :blk Value.fromNumber(@floatFromInt(t.map.count()));
                }
                break :blk .none;
            },
            .vector => |v| blk: {
                if (std.mem.eql(u8, member, "length") or std.mem.eql(u8, member, "size")) {
                    break :blk Value.fromNumber(@floatFromInt(v.items.items.len));
                }
                break :blk .none;
            },
            .string => |s| blk: {
                if (std.mem.eql(u8, member, "length") or std.mem.eql(u8, member, "size")) {
                    break :blk Value.fromNumber(@floatFromInt(s.len));
                }
                break :blk .none;
            },
            else => .none,
        };
    }

    pub fn memberSet(self: *Runtime, obj: Value, member: []const u8, val: Value) !void {
        switch (obj) {
            .record => |r| try r.fields.put(self.allocator, member, val),
            .table => |t| try t.map.put(self.allocator, member, val),
            else => {},
        }
    }

    pub fn printValues(self: *Runtime, args: []const Value) !Value {
        var line_buf: std.ArrayList(u8) = .empty;
        for (args, 0..) |arg, i| {
            if (i > 0) try line_buf.append(self.allocator, ' ');
            const s = try arg.toString(self.allocator);
            try line_buf.appendSlice(self.allocator, s);
        }
        try line_buf.append(self.allocator, '\n');

        if (self.output_capture) |cap| {
            try cap.appendSlice(self.allocator, line_buf.items);
        } else if (self.io) |io| {
            try std.Io.File.stdout().writeStreamingAll(io, line_buf.items);
        } else {
            std.debug.print("{s}", .{line_buf.items});
        }
        return Value.fromNumber(0);
    }

    pub fn isStdlibFn(name: []const u8) bool {
        const names = [_][]const u8{
            "print",                    "input",                  "to_string",
            "number",                   "to_number",              "type_of",
            "check_number",             "check_string",           "check_vector",
            "check_table",              "check_record",           "check_pointer",
            "is_none",                  "is_pointer",             "null_pointer",
            "is_number",                "is_string",              "is_vector",
            "is_table",                 "is_record",              "trim",
            "to_upper",                 "to_lower",               "split",
            "join",                     "string_length",          "length",
            "substring",                "slice",                  "char_at",
            "char_code",                "from_char_code",         "starts_with",
            "ends_with",                "contains",               "index_of",
            "concat",                   "replace",                "read_file",
            "write_file",               "file_exists",            "get_args",
            "sqrt",                     "pow",                    "abs",
            "min",                      "max",                    "floor",
            "ceil",                     "round",                  "sin",
            "cos",                      "tan",                    "log",
            "random",                   "random_int",             "sort",
            "keys",                     "values",                 "size",
            "push",                     "pop",                    "insert",
            "remove",                   "has_key",                "create_game_object",
            "get_game_object",          "destroy_game_object",    "game_set_position",
            "game_set_sprite",          "game_add_tag",           "game_check_collision",
            "game_find_objects_by_tag", "find_game_objects_with_tag",
            "create_panel",             "create_button",          "create_label",
            "create_text_input",        "ui_set_property",        "ui_get_property",
            "ui_set_text",              "ui_add_child",
        };
        for (names) |n| {
            if (std.mem.eql(u8, name, n)) return true;
        }
        return false;
    }

    pub fn callStdlib(self: *Runtime, name: []const u8, args: []const Value) !Value {
        const a0 = if (args.len > 0) args[0] else Value.none;
        const a1 = if (args.len > 1) args[1] else Value.none;
        const a2 = if (args.len > 2) args[2] else Value.none;
        const a3 = if (args.len > 3) args[3] else Value.none;
        const a4 = if (args.len > 4) args[4] else Value.none;
        const a5 = if (args.len > 5) args[5] else Value.none;

        if (std.mem.eql(u8, name, "print")) {
            return self.printValues(args);
        }
        if (std.mem.eql(u8, name, "input")) {
            if (self.input_queue.items.len > 0) {
                const item = self.input_queue.orderedRemove(0);
                return Value.fromString(item);
            }
            if (args.len > 0) {
                const prompt_str = try a0.toString(self.allocator);
                if (self.output_capture) |cap| {
                    try cap.appendSlice(self.allocator, prompt_str);
                } else if (self.io) |io| {
                    try std.Io.File.stdout().writeStreamingAll(io, prompt_str);
                } else {
                    std.debug.print("{s}", .{prompt_str});
                }
            }
            if (self.io) |io| {
                var buf: [1024]u8 = undefined;
                var stdin_r = std.Io.File.stdin().reader(io, &buf);
                const line = (try stdin_r.interface.takeDelimiter('\n')) orelse "";
                const trimmed = std.mem.trim(u8, line, " \t\r\n");
                return Value.fromString(try self.allocator.dupe(u8, trimmed));
            }
            return Value.fromString("");
        }
        if (std.mem.eql(u8, name, "to_string")) {
            return Value.fromString(try a0.toString(self.allocator));
        }
        if (std.mem.eql(u8, name, "to_number")) {
            return Value.fromNumber(a0.asNumber());
        }
        if (std.mem.eql(u8, name, "number")) {
            switch (a0) {
                .number => return a0,
                .string => |s| {
                    if (std.fmt.parseFloat(f64, std.mem.trim(u8, s, " \t\r\n"))) |n| {
                        return Value.fromNumber(n);
                    } else |_| {
                        return self.makeResult(false, Value.fromString(try std.fmt.allocPrint(self.allocator, "Cannot convert '{s}' to number", .{s})));
                    }
                },
                else => return self.makeResult(false, Value.fromString("Cannot convert value to number")),
            }
        }
        if (std.mem.eql(u8, name, "type_of")) {
            return Value.fromString(a0.typeName());
        }
        if (std.mem.eql(u8, name, "check_number") or std.mem.eql(u8, name, "is_number")) {
            return Value.fromBool(a0 == .number);
        }
        if (std.mem.eql(u8, name, "check_string") or std.mem.eql(u8, name, "is_string")) {
            return Value.fromBool(a0 == .string);
        }
        if (std.mem.eql(u8, name, "check_vector") or std.mem.eql(u8, name, "is_vector")) {
            return Value.fromBool(a0 == .vector);
        }
        if (std.mem.eql(u8, name, "check_table") or std.mem.eql(u8, name, "is_table")) {
            return Value.fromBool(a0 == .table);
        }
        if (std.mem.eql(u8, name, "check_record") or std.mem.eql(u8, name, "is_record")) {
            return Value.fromBool(a0 == .record);
        }
        if (std.mem.eql(u8, name, "check_pointer") or std.mem.eql(u8, name, "is_pointer")) {
            return Value.fromBool(a0 == .pointer);
        }
        if (std.mem.eql(u8, name, "null_pointer")) {
            return Value.fromPointer(null);
        }
        if (std.mem.eql(u8, name, "is_none")) {
            return Value.fromBool(a0 == .none);
        }

        // --- Strings ---
        if (std.mem.eql(u8, name, "trim")) {
            const s = try a0.toString(self.allocator);
            return Value.fromString(std.mem.trim(u8, s, " \t\r\n"));
        }
        if (std.mem.eql(u8, name, "to_upper")) {
            const s = try a0.toString(self.allocator);
            const buf = try self.allocator.dupe(u8, s);
            for (buf) |*c| c.* = std.ascii.toUpper(c.*);
            return Value.fromString(buf);
        }
        if (std.mem.eql(u8, name, "to_lower")) {
            const s = try a0.toString(self.allocator);
            const buf = try self.allocator.dupe(u8, s);
            for (buf) |*c| c.* = std.ascii.toLower(c.*);
            return Value.fromString(buf);
        }
        if (std.mem.eql(u8, name, "length") or std.mem.eql(u8, name, "string_length")) {
            return switch (a0) {
                .string => |s| Value.fromNumber(@floatFromInt(s.len)),
                .vector => |v| Value.fromNumber(@floatFromInt(v.items.items.len)),
                .table => |t| Value.fromNumber(@floatFromInt(t.map.count())),
                else => Value.fromNumber(0),
            };
        }
        if (std.mem.eql(u8, name, "substring")) {
            const s = try a0.toString(self.allocator);
            const n: isize = @intCast(s.len);
            var st: isize = @intFromFloat(a1.asNumber());
            if (st < 0) st = 0;
            if (st > n) st = n;
            var en: isize = if (args.len >= 3) st + @max(@as(isize, 0), @as(isize, @intFromFloat(a2.asNumber()))) else n;
            if (en > n) en = n;
            return Value.fromString(s[@intCast(st)..@intCast(en)]);
        }
        if (std.mem.eql(u8, name, "slice")) {
            const s = try a0.toString(self.allocator);
            const n: isize = @intCast(s.len);
            var st: isize = @intFromFloat(a1.asNumber());
            if (st < 0) st = 0;
            if (st > n) st = n;
            var en: isize = if (args.len >= 3) @intFromFloat(a2.asNumber()) else n;
            if (en < st) en = st;
            if (en > n) en = n;
            return Value.fromString(s[@intCast(st)..@intCast(en)]);
        }
        if (std.mem.eql(u8, name, "char_at")) {
            const s = try a0.toString(self.allocator);
            const idx: isize = @intFromFloat(a1.asNumber());
            if (idx < 0 or idx >= @as(isize, @intCast(s.len))) return Value.fromString("");
            const u: usize = @intCast(idx);
            return Value.fromString(s[u .. u + 1]);
        }
        if (std.mem.eql(u8, name, "char_code")) {
            const s = try a0.toString(self.allocator);
            if (s.len == 0) return Value.fromNumber(0);
            return Value.fromNumber(@floatFromInt(s[0]));
        }
        if (std.mem.eql(u8, name, "from_char_code")) {
            const code_i: i32 = @intFromFloat(a0.asNumber());
            const byte: u8 = @intCast(@mod(code_i, 256));
            const buf = try self.allocator.alloc(u8, 1);
            buf[0] = byte;
            return Value.fromString(buf);
        }
        if (std.mem.eql(u8, name, "starts_with")) {
            const s = try a0.toString(self.allocator);
            const p = try a1.toString(self.allocator);
            return Value.fromBool(std.mem.startsWith(u8, s, p));
        }
        if (std.mem.eql(u8, name, "ends_with")) {
            const s = try a0.toString(self.allocator);
            const p = try a1.toString(self.allocator);
            return Value.fromBool(std.mem.endsWith(u8, s, p));
        }
        if (std.mem.eql(u8, name, "contains")) {
            const s = try a0.toString(self.allocator);
            const sub_s = try a1.toString(self.allocator);
            return Value.fromBool(std.mem.indexOf(u8, s, sub_s) != null);
        }
        if (std.mem.eql(u8, name, "index_of")) {
            const s = try a0.toString(self.allocator);
            const sub_s = try a1.toString(self.allocator);
            if (std.mem.indexOf(u8, s, sub_s)) |idx| {
                return Value.fromNumber(@floatFromInt(idx));
            }
            return Value.fromNumber(-1);
        }
        if (std.mem.eql(u8, name, "concat")) {
            return self.concat(a0, a1);
        }
        if (std.mem.eql(u8, name, "replace")) {
            const s = try a0.toString(self.allocator);
            const needle = try a1.toString(self.allocator);
            const replacement = try a2.toString(self.allocator);
            if (needle.len == 0) return Value.fromString(s);
            const out = try std.mem.replaceOwned(u8, self.allocator, s, needle, replacement);
            return Value.fromString(out);
        }
        if (std.mem.eql(u8, name, "split")) {
            const s = try a0.toString(self.allocator);
            const delim = try a1.toString(self.allocator);
            const vec_val = try self.makeVector();
            const vec = vec_val.vector;
            if (delim.len == 0) {
                for (s) | idx_ch | {
                    _ = idx_ch;
                }
                var i: usize = 0;
                while (i < s.len) : (i += 1) {
                    try vec.items.append(self.allocator, Value.fromString(s[i .. i + 1]));
                }
            } else {
                var it = std.mem.splitSequence(u8, s, delim);
                while (it.next()) |part| {
                    try vec.items.append(self.allocator, Value.fromString(part));
                }
            }
            return vec_val;
        }
        if (std.mem.eql(u8, name, "join")) {
            if (a0 == .vector) {
                const delim = try a1.toString(self.allocator);
                var out: std.ArrayList(u8) = .empty;
                for (a0.vector.items.items, 0..) |item, idx| {
                    if (idx > 0) try out.appendSlice(self.allocator, delim);
                    try out.appendSlice(self.allocator, try item.toString(self.allocator));
                }
                return Value.fromString(try out.toOwnedSlice(self.allocator));
            }
            const delim = try a0.toString(self.allocator);
            var out: std.ArrayList(u8) = .empty;
            for (args[1..], 0..) |item, idx| {
                if (idx > 0) try out.appendSlice(self.allocator, delim);
                try out.appendSlice(self.allocator, try item.toString(self.allocator));
            }
            return Value.fromString(try out.toOwnedSlice(self.allocator));
        }

        // --- Math ---
        if (std.mem.eql(u8, name, "sqrt")) return Value.fromNumber(@sqrt(a0.asNumber()));
        if (std.mem.eql(u8, name, "pow")) return Value.fromNumber(std.math.pow(f64, a0.asNumber(), a1.asNumber()));
        if (std.mem.eql(u8, name, "abs")) return Value.fromNumber(@abs(a0.asNumber()));
        if (std.mem.eql(u8, name, "min")) return Value.fromNumber(@min(a0.asNumber(), a1.asNumber()));
        if (std.mem.eql(u8, name, "max")) return Value.fromNumber(@max(a0.asNumber(), a1.asNumber()));
        if (std.mem.eql(u8, name, "floor")) return Value.fromNumber(@floor(a0.asNumber()));
        if (std.mem.eql(u8, name, "ceil")) return Value.fromNumber(@ceil(a0.asNumber()));
        if (std.mem.eql(u8, name, "round")) return Value.fromNumber(@round(a0.asNumber()));
        if (std.mem.eql(u8, name, "sin")) return Value.fromNumber(@sin(a0.asNumber()));
        if (std.mem.eql(u8, name, "cos")) return Value.fromNumber(@cos(a0.asNumber()));
        if (std.mem.eql(u8, name, "tan")) return Value.fromNumber(@tan(a0.asNumber()));
        if (std.mem.eql(u8, name, "log")) return Value.fromNumber(@log(a0.asNumber()));
        if (std.mem.eql(u8, name, "random")) return Value.fromNumber(self.prng.random().float(f64));
        if (std.mem.eql(u8, name, "random_int")) {
            const min_val: i64 = @intFromFloat(a0.asNumber());
            const max_val: i64 = @intFromFloat(a1.asNumber());
            if (min_val >= max_val) return Value.fromNumber(@floatFromInt(min_val));
            const diff: u64 = @intCast(max_val - min_val + 1);
            const r = self.prng.random().intRangeLessThan(u64, 0, diff);
            return Value.fromNumber(@floatFromInt(min_val + @as(i64, @intCast(r))));
        }

        // --- Collections ---
        if (std.mem.eql(u8, name, "push")) {
            if (a0 == .vector) {
                try a0.vector.items.append(self.allocator, a1);
                return Value.fromNumber(@floatFromInt(a0.vector.items.items.len));
            }
            return Value.fromNumber(0);
        }
        if (std.mem.eql(u8, name, "pop")) {
            if (a0 == .vector and a0.vector.items.items.len > 0) {
                return a0.vector.items.pop().?;
            }
            return .none;
        }
        if (std.mem.eql(u8, name, "insert")) {
            if (a0 == .vector) {
                const idx: usize = @intFromFloat(@max(0.0, a1.asNumber()));
                const clamped = @min(idx, a0.vector.items.items.len);
                try a0.vector.items.insert(self.allocator, clamped, a2);
                return Value.fromNumber(@floatFromInt(a0.vector.items.items.len));
            }
            return Value.fromNumber(0);
        }
        if (std.mem.eql(u8, name, "remove")) {
            if (a0 == .vector) {
                const idx: usize = @intFromFloat(@max(0.0, a1.asNumber()));
                if (idx < a0.vector.items.items.len) {
                    return a0.vector.items.orderedRemove(idx);
                }
            }
            return .none;
        }
        if (std.mem.eql(u8, name, "size")) {
            if (a0 == .table) return Value.fromNumber(@floatFromInt(a0.table.map.count()));
            if (a0 == .vector) return Value.fromNumber(@floatFromInt(a0.vector.items.items.len));
            return Value.fromNumber(0);
        }
        if (std.mem.eql(u8, name, "has_key")) {
            if (a0 == .table) {
                const k = try a1.toString(self.allocator);
                if (a0.table.map.get(k)) |v| {
                    return Value.fromBool(v != .none);
                }
            }
            return Value.fromBool(false);
        }
        if (std.mem.eql(u8, name, "keys")) {
            const vec_val = try self.makeVector();
            if (a0 == .table) {
                var it = a0.table.map.iterator();
                while (it.next()) |entry| {
                    if (entry.value_ptr.* != .none) {
                        try vec_val.vector.items.append(self.allocator, Value.fromString(entry.key_ptr.*));
                    }
                }
            }
            return vec_val;
        }
        if (std.mem.eql(u8, name, "values")) {
            const vec_val = try self.makeVector();
            if (a0 == .table) {
                var it = a0.table.map.iterator();
                while (it.next()) |entry| {
                    if (entry.value_ptr.* != .none) {
                        try vec_val.vector.items.append(self.allocator, entry.value_ptr.*);
                    }
                }
            }
            return vec_val;
        }
        if (std.mem.eql(u8, name, "sort")) {
            if (a0 == .vector) {
                const vec_val = try self.makeVector();
                try vec_val.vector.items.appendSlice(self.allocator, a0.vector.items.items);
                std.mem.sort(Value, vec_val.vector.items.items, {}, struct {
                    fn lessThan(_: void, lhs: Value, rhs: Value) bool {
                        if (lhs == .string and rhs == .string) {
                            return std.mem.order(u8, lhs.string, rhs.string) == .lt;
                        }
                        return lhs.asNumber() < rhs.asNumber();
                    }
                }.lessThan);
                return vec_val;
            }
            if (a0 == .table) {
                const tbl_val = try self.makeTable();
                const Entry = struct { k: []const u8, v: Value };
                var list: std.ArrayList(Entry) = .empty;
                var it = a0.table.map.iterator();
                while (it.next()) |e| {
                    try list.append(self.allocator, .{ .k = e.key_ptr.*, .v = e.value_ptr.* });
                }
                std.mem.sort(Entry, list.items, {}, struct {
                    fn lessThan(_: void, lhs: Entry, rhs: Entry) bool {
                        return lhs.v.asNumber() < rhs.v.asNumber();
                    }
                }.lessThan);
                for (list.items) |e| {
                    try tbl_val.table.map.put(self.allocator, e.k, e.v);
                }
                return tbl_val;
            }
            return a0;
        }

        // --- Files & CLI Args ---
        if (std.mem.eql(u8, name, "read_file")) {
            const path = try a0.toString(self.allocator);
            if (self.io) |io| {
                const bytes = std.Io.Dir.cwd().readFileAlloc(io, path, self.allocator, .limited(64 * 1024 * 1024)) catch |err| {
                    return self.makeResult(false, Value.fromString(@errorName(err)));
                };
                return Value.fromString(bytes);
            }
            return Value.fromString("");
        }
        if (std.mem.eql(u8, name, "write_file")) {
            const path = try a0.toString(self.allocator);
            const data = try a1.toString(self.allocator);
            if (self.io) |io| {
                std.Io.Dir.cwd().writeFile(io, .{ .sub_path = path, .data = data }) catch {
                    return Value.fromNumber(0);
                };
                return Value.fromNumber(1);
            }
            return Value.fromNumber(0);
        }
        if (std.mem.eql(u8, name, "file_exists")) {
            const path = try a0.toString(self.allocator);
            if (self.io) |io| {
                _ = std.Io.Dir.cwd().statFile(io, path, .{}) catch return Value.fromNumber(0);
                return Value.fromNumber(1);
            }
            return Value.fromNumber(0);
        }
        if (std.mem.eql(u8, name, "get_args")) {
            const vec_val = try self.makeVector();
            try vec_val.vector.items.appendSlice(self.allocator, self.cli_args.items);
            return vec_val;
        }

        // --- Game Object Primitives ---
        if (std.mem.eql(u8, name, "create_game_object")) {
            const obj = try self.makeRecord("GameObject");
            try obj.fields.put(self.allocator, "name", Value.fromString(try a0.toString(self.allocator)));
            const init_x = if (args.len > 1) a1.asNumber() else 0.0;
            const init_y = if (args.len > 2) a2.asNumber() else 0.0;
            const init_w = if (args.len > 4) a4.asNumber() else 32.0;
            const init_h = if (args.len > 5) a5.asNumber() else 32.0;
            try obj.fields.put(self.allocator, "x", Value.fromNumber(init_x));
            try obj.fields.put(self.allocator, "y", Value.fromNumber(init_y));
            try obj.fields.put(self.allocator, "width", Value.fromNumber(init_w));
            try obj.fields.put(self.allocator, "height", Value.fromNumber(init_h));
            const tags_vec = try self.makeVector();
            if (args.len > 3 and a3 != .none) {
                try tags_vec.vector.items.append(self.allocator, a3);
            }
            try obj.fields.put(self.allocator, "tags", tags_vec);
            try self.game_objects.append(self.allocator, obj);
            return .{ .record = obj };
        }
        if (std.mem.eql(u8, name, "game_set_position")) {
            if (a0 == .record) {
                try a0.record.fields.put(self.allocator, "x", Value.fromNumber(a1.asNumber()));
                try a0.record.fields.put(self.allocator, "y", Value.fromNumber(a2.asNumber()));
            }
            return Value.fromNumber(1);
        }
        if (std.mem.eql(u8, name, "game_set_sprite")) {
            if (a0 == .record) {
                try a0.record.fields.put(self.allocator, "sprite", a1);
                try a0.record.fields.put(self.allocator, "width", Value.fromNumber(a2.asNumber()));
                try a0.record.fields.put(self.allocator, "height", Value.fromNumber(a3.asNumber()));
            }
            return Value.fromNumber(1);
        }
        if (std.mem.eql(u8, name, "game_add_tag")) {
            if (a0 == .record) {
                if (a0.record.fields.get("tags")) |tags_val| {
                    if (tags_val == .vector) {
                        try tags_val.vector.items.append(self.allocator, a1);
                    }
                }
            }
            return Value.fromNumber(1);
        }
        if (std.mem.eql(u8, name, "game_check_collision")) {
            if (a0 == .record and a1 == .record) {
                const x1 = (a0.record.fields.get("x") orelse Value.fromNumber(0)).asNumber();
                const y1 = (a0.record.fields.get("y") orelse Value.fromNumber(0)).asNumber();
                const w1 = (a0.record.fields.get("width") orelse Value.fromNumber(0)).asNumber();
                const h1 = (a0.record.fields.get("height") orelse Value.fromNumber(0)).asNumber();

                const x2 = (a1.record.fields.get("x") orelse Value.fromNumber(0)).asNumber();
                const y2 = (a1.record.fields.get("y") orelse Value.fromNumber(0)).asNumber();
                const w2 = (a1.record.fields.get("width") orelse Value.fromNumber(0)).asNumber();
                const h2 = (a1.record.fields.get("height") orelse Value.fromNumber(0)).asNumber();

                const overlap = (x1 < x2 + w2) and (x1 + w1 > x2) and (y1 < y2 + h2) and (y1 + h1 > y2);
                return Value.fromBool(overlap);
            }
            return Value.fromNumber(0);
        }
        if (std.mem.eql(u8, name, "get_game_object")) {
            const target_name = try a0.toString(self.allocator);
            for (self.game_objects.items) |obj| {
                if (obj.fields.get("name")) |n_val| {
                    if (std.mem.eql(u8, try n_val.toString(self.allocator), target_name)) {
                        return .{ .record = obj };
                    }
                }
            }
            return .none;
        }
        if (std.mem.eql(u8, name, "destroy_game_object")) {
            if (a0 == .record) {
                for (self.game_objects.items, 0..) |obj, idx| {
                    if (obj == a0.record) {
                        _ = self.game_objects.orderedRemove(idx);
                        return Value.fromNumber(1);
                    }
                }
            }
            return Value.fromNumber(0);
        }
        if (std.mem.eql(u8, name, "game_find_objects_by_tag") or std.mem.eql(u8, name, "find_game_objects_with_tag")) {
            const target_tag = try a0.toString(self.allocator);
            const found = try self.makeVector();
            for (self.game_objects.items) |obj| {
                if (obj.fields.get("tags")) |tags_val| {
                    if (tags_val == .vector) {
                        for (tags_val.vector.items.items) |t| {
                            if (std.mem.eql(u8, try t.toString(self.allocator), target_tag)) {
                                try found.vector.items.append(self.allocator, .{ .record = obj });
                                break;
                            }
                        }
                    }
                }
            }
            return found;
        }

        // --- UI Component Primitives ---
        if (std.mem.eql(u8, name, "create_panel") or
            std.mem.eql(u8, name, "create_button") or
            std.mem.eql(u8, name, "create_label") or
            std.mem.eql(u8, name, "create_text_input"))
        {
            const comp = try self.makeRecord("UIComponent");
            try comp.fields.put(self.allocator, "kind", Value.fromString(name));
            try comp.fields.put(self.allocator, "text", a0);
            try comp.fields.put(self.allocator, "children", try self.makeVector());
            return .{ .record = comp };
        }
        if (std.mem.eql(u8, name, "ui_set_property")) {
            if (a0 == .record) {
                const prop = try a1.toString(self.allocator);
                try a0.record.fields.put(self.allocator, prop, a2);
            }
            return Value.fromNumber(1);
        }
        if (std.mem.eql(u8, name, "ui_get_property")) {
            if (a0 == .record) {
                const prop = try a1.toString(self.allocator);
                return a0.record.fields.get(prop) orelse .none;
            }
            return .none;
        }
        if (std.mem.eql(u8, name, "ui_set_text")) {
            if (a0 == .record) {
                try a0.record.fields.put(self.allocator, "text", a1);
            }
            return Value.fromNumber(1);
        }
        if (std.mem.eql(u8, name, "ui_add_child")) {
            if (a0 == .record) {
                if (a0.record.fields.get("children")) |ch| {
                    if (ch == .vector) {
                        try ch.vector.items.append(self.allocator, a1);
                    }
                }
            }
            return Value.fromNumber(1);
        }

        return .none;
    }
};

pub fn valuesEqual(a: Value, b: Value) bool {
    if (std.meta.activeTag(a) != std.meta.activeTag(b)) return false;
    return switch (a) {
        .none => true,
        .number => |n| @abs(n - b.number) < 1e-9,
        .string => |s| std.mem.eql(u8, s, b.string),
        .vector => |v| v == b.vector,
        .table => |t| t == b.table,
        .record => |r| r == b.record,
        .result => |r| r.is_ok == b.result.is_ok and valuesEqual(r.payload.*, b.result.payload.*),
        .channel => |c| c == b.channel,
        .fiber => |f| f == b.fiber,
        .pointer => |p| p == b.pointer,
    };
}

pub const CValueTag = enum(u32) {
    none = 0,
    number = 1,
    string = 2,
    pointer = 3,
};

pub const CValue = extern struct {
    tag: CValueTag = .none,
    num: f64 = 0.0,
    str_ptr: [*]const u8 = "",
    str_len: usize = 0,
    ptr: ?*anyopaque = null,

    pub fn fromValue(alloc: std.mem.Allocator, val: Value) CValue {
        switch (val) {
            .none => return .{ .tag = .none, .num = 0, .str_ptr = "", .str_len = 0, .ptr = null },
            .number => |n| return .{ .tag = .number, .num = n, .str_ptr = "", .str_len = 0, .ptr = null },
            .string => |s| {
                const z = dupeZ(alloc, s) catch s;
                return .{ .tag = .string, .num = 0, .str_ptr = z.ptr, .str_len = s.len, .ptr = null };
            },
            .pointer => |p| return .{ .tag = .pointer, .num = 0, .str_ptr = "", .str_len = 0, .ptr = p },
            else => {
                const s = val.toString(alloc) catch "";
                return .{ .tag = .string, .num = val.asNumber(), .str_ptr = s.ptr, .str_len = s.len, .ptr = null };
            },
        }
    }

    pub fn toValue(self: CValue, alloc: std.mem.Allocator) Value {
        switch (self.tag) {
            .none => return .none,
            .number => return Value.fromNumber(self.num),
            .string => {
                if (self.str_len == 0) return Value.fromString("");
                const slice = self.str_ptr[0..self.str_len];
                const dup = alloc.dupe(u8, slice) catch slice;
                return Value.fromString(dup);
            },
            .pointer => return Value.fromPointer(self.ptr),
        }
    }
};

pub const BridgeFn = *const fn (rt_ptr: ?*anyopaque, in_args: [*]const CValue, num_args: usize, out: *CValue) callconv(.c) void;

pub fn dupeZ(alloc: std.mem.Allocator, s: []const u8) ![:0]u8 {
    const buf = try alloc.allocSentinel(u8, s.len, 0);
    @memcpy(buf, s);
    return buf;
}

pub const SharedLib = struct {
    handle: ?*anyopaque = null,

    pub fn open(path: []const u8, alloc: std.mem.Allocator) !SharedLib {
        const path_z = try dupeZ(alloc, path);
        defer alloc.free(path_z);
        if (builtin.os.tag == .windows) {
            const h = LoadLibraryA(path_z) orelse return error.LibraryNotFound;
            return .{ .handle = h };
        } else {
            const h = std.c.dlopen(path_z, .{ .LAZY = true }) orelse return error.LibraryNotFound;
            return .{ .handle = h };
        }
    }

    pub fn lookup(self: SharedLib, comptime T: type, symbol: [:0]const u8) ?T {
        const h = self.handle orelse return null;
        if (builtin.os.tag == .windows) {
            const proc = GetProcAddress(h, symbol.ptr) orelse return null;
            return @as(T, @ptrCast(@alignCast(proc)));
        } else {
            const proc = std.c.dlsym(h, symbol.ptr) orelse return null;
            return @as(T, @ptrCast(@alignCast(proc)));
        }
    }

    pub fn close(self: *SharedLib) void {
        if (self.handle) |h| {
            if (builtin.os.tag == .windows) {
                _ = FreeLibrary(h);
            } else {
                _ = std.c.dlclose(h);
            }
            self.handle = null;
        }
    }
};

pub fn callZigFn(comptime func: anytype, rt: *Runtime, args: []const Value) anyerror!Value {
    const FnInfo = @typeInfo(@TypeOf(func));
    if (FnInfo != .@"fn") @compileError("callZigFn expects a function");
    const param_types = FnInfo.@"fn".param_types;

    var call_args: std.meta.ArgsTuple(@TypeOf(func)) = undefined;
    var val_idx: usize = 0;

    inline for (param_types, 0..) |maybe_pt, i| {
        const PT = maybe_pt orelse @compileError("param type required");
        if (PT == *Runtime or PT == *const Runtime) {
            call_args[i] = rt;
        } else if (PT == Value) {
            call_args[i] = if (val_idx < args.len) args[val_idx] else Value.none;
            val_idx += 1;
        } else if (PT == f64 or PT == f32) {
            const v = if (val_idx < args.len) args[val_idx].asNumber() else 0.0;
            call_args[i] = @floatCast(v);
            val_idx += 1;
        } else if (PT == i64 or PT == i32 or PT == usize or PT == isize or PT == u32 or PT == u64 or PT == c_int) {
            const v = if (val_idx < args.len) args[val_idx].asNumber() else 0.0;
            call_args[i] = @intFromFloat(v);
            val_idx += 1;
        } else if (PT == bool) {
            const v = if (val_idx < args.len) args[val_idx].isTruthy() else false;
            call_args[i] = v;
            val_idx += 1;
        } else if (PT == []const u8) {
            const v = if (val_idx < args.len) try args[val_idx].toString(rt.allocator) else "";
            call_args[i] = v;
            val_idx += 1;
        } else if (PT == [*:0]const u8) {
            const v = if (val_idx < args.len) try args[val_idx].toString(rt.allocator) else "";
            call_args[i] = (try dupeZ(rt.allocator, v)).ptr;
            val_idx += 1;
        } else if (PT == ?*anyopaque or PT == *anyopaque) {
            const v = if (val_idx < args.len) args[val_idx].asPointer() else null;
            call_args[i] = v;
            val_idx += 1;
        } else {
            @compileError("Unsupported parameter type in callZigFn: " ++ @typeName(PT));
        }
    }

    const ResType = FnInfo.@"fn".return_type orelse void;
    if (ResType == void) {
        @call(.auto, func, call_args);
        return Value.none;
    }

    const res = @call(.auto, func, call_args);
    return convertZigResultToValue(rt, res);
}

fn convertZigResultToValue(rt: *Runtime, val: anytype) anyerror!Value {
    const T = @TypeOf(val);
    const info = @typeInfo(T);
    switch (info) {
        .void => return Value.none,
        .bool => return Value.fromBool(val),
        .int, .comptime_int => return Value.fromNumber(@floatFromInt(val)),
        .float, .comptime_float => return Value.fromNumber(@floatCast(val)),
        .pointer => |ptr| {
            if (ptr.size == .slice and ptr.child == u8) {
                return Value.fromString(try rt.allocator.dupe(u8, val));
            }
            if (ptr.size == .one or ptr.size == .many or ptr.size == .c) {
                return Value.fromPointer(@ptrCast(val));
            }
            return Value.none;
        },
        .optional => {
            if (val) |v| return convertZigResultToValue(rt, v);
            return Value.none;
        },
        .error_union => {
            if (val) |v| {
                const sub = try convertZigResultToValue(rt, v);
                return rt.makeResult(true, sub);
            } else |err| {
                return rt.makeResult(false, Value.fromString(@errorName(err)));
            }
        },
        else => {
            if (T == Value) return val;
            return Value.none;
        },
    }
}
