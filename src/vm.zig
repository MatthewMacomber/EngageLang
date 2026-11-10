const std = @import("std");
const builtin = @import("builtin");
const ast = @import("ast.zig");
const parser = @import("parser.zig");
pub const runtime = @import("runtime.zig");

const embedded_runtime_src = @embedFile("runtime.zig");

pub const Value = runtime.Value;
pub const Runtime = runtime.Runtime;

pub const HostFn = *const fn (rt: *Runtime, args: []const Value, userdata: ?*anyopaque) anyerror!Value;

pub const HostBinding = struct {
    callback: HostFn,
    userdata: ?*anyopaque = null,
};

const DynamicFnBinding = struct {
    bridge_fn: runtime.BridgeFn,
};

fn dynamicBridgeTrampoline(rt: *Runtime, args: []const Value, userdata: ?*anyopaque) anyerror!Value {
    const binding: *DynamicFnBinding = @ptrCast(@alignCast(userdata.?));
    const alloc = rt.allocator;
    var c_args: std.ArrayList(runtime.CValue) = .empty;
    for (args) |arg| {
        try c_args.append(alloc, runtime.CValue.fromValue(alloc, arg));
    }
    var out: runtime.CValue = .{};
    binding.bridge_fn(rt, c_args.items.ptr, c_args.items.len, &out);
    return out.toValue(alloc);
}

const FiberState = struct {
    body: []const ast.Stmt,
    scope: *Scope,
    ip: usize = 0,
    done: bool = false,
};

pub const Scope = struct {
    vars: std.StringArrayHashMapUnmanaged(Value) = .empty,
    parent: ?*Scope = null,
    is_fn_boundary: bool = false,

    pub fn get(self: *const Scope, name: []const u8) ?Value {
        if (self.vars.get(name)) |v| return v;
        if (self.parent) |p| return p.get(name);
        return null;
    }

    pub fn setExisting(self: *Scope, allocator: std.mem.Allocator, name: []const u8, val: Value) !bool {
        if (self.vars.contains(name)) {
            try self.vars.put(allocator, name, val);
            return true;
        }
        if (self.parent) |p| {
            return p.setExisting(allocator, name, val);
        }
        return false;
    }

    pub fn setInCurrentFunction(self: *Scope, allocator: std.mem.Allocator, name: []const u8, val: Value) !bool {
        if (self.vars.contains(name)) {
            try self.vars.put(allocator, name, val);
            return true;
        }
        if (self.is_fn_boundary) {
            return false;
        }
        if (self.parent) |p| {
            return p.setInCurrentFunction(allocator, name, val);
        }
        return false;
    }

    pub fn define(self: *Scope, allocator: std.mem.Allocator, name: []const u8, val: Value) !void {
        try self.vars.put(allocator, name, val);
    }
};

const ExecSignal = union(enum) {
    normal: Value,
    ret: Value,
    yield_val: Value,
    brk,
    cont,
};

pub const EngageVM = struct {
    arena: std.heap.ArenaAllocator,
    rt: Runtime,
    global_scope: Scope = .{},
    functions: std.StringArrayHashMapUnmanaged(ast.FuncDef) = .empty,
    records: std.StringArrayHashMapUnmanaged(ast.RecordDef) = .empty,
    host_fns: std.StringArrayHashMapUnmanaged(HostBinding) = .empty,
    loaded_modules: std.StringArrayHashMapUnmanaged(*runtime.Table) = .empty,
    loaded_shared_libs: std.StringArrayHashMapUnmanaged(runtime.SharedLib) = .empty,
    base_dir: []const u8 = ".",

    pub fn init(backing_allocator: std.mem.Allocator, io: ?std.Io) EngageVM {
        var arena = std.heap.ArenaAllocator.init(backing_allocator);
        const alloc = arena.allocator();
        return .{
            .arena = arena,
            .rt = Runtime.init(alloc, io),
        };
    }

    pub fn deinit(self: *EngageVM) void {
        var slit = self.loaded_shared_libs.iterator();
        while (slit.next()) |entry| {
            entry.value_ptr.close();
        }
        self.arena.deinit();
    }

    pub fn allocator(self: *EngageVM) std.mem.Allocator {
        return self.arena.allocator();
    }

    pub fn registerFn(self: *EngageVM, name: []const u8, callback: HostFn, userdata: ?*anyopaque) !void {
        const alloc = self.allocator();
        const dup_name = try alloc.dupe(u8, name);
        try self.host_fns.put(alloc, dup_name, .{ .callback = callback, .userdata = userdata });
    }

    pub fn setGlobal(self: *EngageVM, name: []const u8, val: Value) !void {
        const alloc = self.allocator();
        const dup_name = try alloc.dupe(u8, name);
        try self.global_scope.define(alloc, dup_name, val);
    }

    pub fn getGlobal(self: *const EngageVM, name: []const u8) ?Value {
        return self.global_scope.get(name);
    }

    pub fn eval(self: *EngageVM, source: []const u8) !Value {
        const alloc = self.allocator();
        self.rt.allocator = alloc;
        const prog = try parser.parseSource(alloc, source);
        return self.evalProgram(prog);
    }

    fn preloadExternalLibraries(self: *EngageVM, stmts: []const ast.Stmt, scope: *Scope) anyerror!void {
        const alloc = self.allocator();
        var lib_map: std.StringArrayHashMapUnmanaged(std.ArrayList(ast.ExternFnDef)) = .empty;

        for (stmts) |st| {
            switch (st) {
                .from_import_stmt => |fis| {
                    if (parser.isExternalLibraryPath(fis.module_path)) {
                        const entry = try lib_map.getOrPut(alloc, fis.module_path);
                        if (!entry.found_existing) entry.value_ptr.* = .empty;
                        for (fis.symbols) |sym| {
                            try entry.value_ptr.append(alloc, .{
                                .library = fis.module_path,
                                .name = sym.name,
                                .alias = sym.alias,
                                .params = sym.params orelse &.{},
                                .ret_type = sym.ret_type,
                                .has_explicit_sig = (sym.params != null or sym.ret_type != .auto),
                            });
                        }
                    }
                },
                .extern_fn_def => |efd| {
                    const entry = try lib_map.getOrPut(alloc, efd.library);
                    if (!entry.found_existing) entry.value_ptr.* = .empty;
                    try entry.value_ptr.append(alloc, efd);
                },
                else => {},
            }
        }

        var it = lib_map.iterator();
        while (it.next()) |entry| {
            try self.loadExternalLibrary(entry.key_ptr.*, entry.value_ptr.items, scope);
        }
    }

    pub fn evalProgram(self: *EngageVM, prog: ast.Program) !Value {
        const alloc = self.allocator();
        self.rt.allocator = alloc;
        try self.preloadExternalLibraries(prog.statements, &self.global_scope);
        const sig = try self.execStmts(prog.statements, &self.global_scope);
        return switch (sig) {
            .normal, .ret, .yield_val => |v| v,
            .brk, .cont => .none,
        };
    }

    pub fn call(self: *EngageVM, func_name: []const u8, args: []const Value) !Value {
        const alloc = self.allocator();
        self.rt.allocator = alloc;
        if (self.functions.get(func_name)) |fn_def| {
            return self.invokeUserFn(fn_def, args, null);
        }
        if (self.host_fns.get(func_name)) |hb| {
            return hb.callback(&self.rt, args, hb.userdata);
        }
        if (Runtime.isStdlibFn(func_name)) {
            return self.rt.callStdlib(func_name, args);
        }
        return error.UndefinedFunction;
    }

    fn invokeUserFn(self: *EngageVM, fn_def: ast.FuncDef, args: []const Value, self_instance: ?Value) anyerror!Value {
        const alloc = self.allocator();
        var fn_scope = Scope{ .parent = &self.global_scope, .is_fn_boundary = true };
        if (self_instance) |inst| {
            try fn_scope.define(alloc, "self", inst);
        }
        for (fn_def.params, 0..) |pname, idx| {
            const aval = if (idx < args.len) args[idx] else Value.none;
            try fn_scope.define(alloc, pname, aval);
        }
        const sig = try self.execStmts(fn_def.body, &fn_scope);
        return switch (sig) {
            .ret, .normal, .yield_val => |v| v,
            .brk, .cont => .none,
        };
    }

    fn execStmts(self: *EngageVM, stmts: []const ast.Stmt, scope: *Scope) anyerror!ExecSignal {
        var last: Value = .none;
        for (stmts) |st| {
            const sig = try self.execStmt(st, scope);
            switch (sig) {
                .normal => |v| last = v,
                .ret, .yield_val, .brk, .cont => return sig,
            }
        }
        return .{ .normal = last };
    }

    fn execStmt(self: *EngageVM, st: ast.Stmt, scope: *Scope) anyerror!ExecSignal {
        const alloc = self.allocator();
        switch (st) {
            .var_assign => |va| {
                var early_ret: ?Value = null;
                const val = try self.evalExpr(va.value, scope, &early_ret);
                if (early_ret) |er| return .{ .ret = er };
                if (!(try scope.setInCurrentFunction(alloc, va.name, val))) {
                    try scope.define(alloc, va.name, val);
                }
                return .{ .normal = val };
            },
            .set_stmt => |ss| {
                var early_ret: ?Value = null;
                const val = try self.evalExpr(ss.value, scope, &early_ret);
                if (early_ret) |er| return .{ .ret = er };

                switch (ss.target.*) {
                    .ident => |name| {
                        if (!(try scope.setExisting(alloc, name, val))) {
                            try scope.define(alloc, name, val);
                        }
                    },
                    .member_access => |ma| {
                        const obj = try self.evalExpr(ma.object, scope, &early_ret);
                        if (early_ret) |er| return .{ .ret = er };
                        try self.rt.memberSet(obj, ma.member, val);
                    },
                    else => {},
                }
                return .{ .normal = val };
            },
            .index_assign => |ia| {
                var early_ret: ?Value = null;
                const obj = try self.evalExpr(ia.object, scope, &early_ret);
                if (early_ret) |er| return .{ .ret = er };
                const idx = try self.evalExpr(ia.index, scope, &early_ret);
                if (early_ret) |er| return .{ .ret = er };
                const val = try self.evalExpr(ia.value, scope, &early_ret);
                if (early_ret) |er| return .{ .ret = er };
                try self.rt.indexSet(obj, idx, val);
                return .{ .normal = val };
            },
            .func_def => |fd| {
                try self.functions.put(alloc, fd.name, fd);
                return .{ .normal = .none };
            },
            .record_def => |rd| {
                try self.records.put(alloc, rd.name, rd);
                return .{ .normal = .none };
            },
            .if_stmt => |ifs| {
                for (ifs.branches) |b| {
                    var early_ret: ?Value = null;
                    const cond = try self.evalExpr(b.condition, scope, &early_ret);
                    if (early_ret) |er| return .{ .ret = er };
                    if (cond.isTruthy()) {
                        var child_scope = Scope{ .parent = scope };
                        return self.execStmts(b.body, &child_scope);
                    }
                }
                if (ifs.else_body.len > 0) {
                    var else_scope = Scope{ .parent = scope };
                    return self.execStmts(ifs.else_body, &else_scope);
                }
                return .{ .normal = .none };
            },
            .while_stmt => |ws| {
                var last: Value = .none;
                while (true) {
                    var early_ret: ?Value = null;
                    const cond = try self.evalExpr(ws.condition, scope, &early_ret);
                    if (early_ret) |er| return .{ .ret = er };
                    if (!cond.isTruthy()) break;

                    var loop_scope = Scope{ .parent = scope };
                    const sig = try self.execStmts(ws.body, &loop_scope);
                    switch (sig) {
                        .normal => |v| last = v,
                        .ret, .yield_val => return sig,
                        .brk => break,
                        .cont => continue,
                    }
                }
                return .{ .normal = last };
            },
            .repeat_stmt => |rs| {
                var early_ret: ?Value = null;
                const count_val = try self.evalExpr(rs.count, scope, &early_ret);
                if (early_ret) |er| return .{ .ret = er };
                const n: isize = @intFromFloat(count_val.asNumber());
                var i: isize = 0;
                var last: Value = .none;
                while (i < n) : (i += 1) {
                    var loop_scope = Scope{ .parent = scope };
                    const sig = try self.execStmts(rs.body, &loop_scope);
                    switch (sig) {
                        .normal => |v| last = v,
                        .ret, .yield_val => return sig,
                        .brk => break,
                        .cont => continue,
                    }
                }
                return .{ .normal = last };
            },
            .for_each_stmt => |fs| {
                var early_ret: ?Value = null;
                const iter_val = try self.evalExpr(fs.iterable, scope, &early_ret);
                if (early_ret) |er| return .{ .ret = er };
                var last: Value = .none;
                if (iter_val == .vector) {
                    for (iter_val.vector.items.items) |item| {
                        var loop_scope = Scope{ .parent = scope };
                        try loop_scope.define(alloc, fs.item_name, item);
                        const sig = try self.execStmts(fs.body, &loop_scope);
                        switch (sig) {
                            .normal => |v| last = v,
                            .ret, .yield_val => return sig,
                            .brk => break,
                            .cont => continue,
                        }
                    }
                }
                return .{ .normal = last };
            },
            .return_stmt => |ret| {
                if (ret.value) |vexpr| {
                    var early_ret: ?Value = null;
                    const v = try self.evalExpr(vexpr, scope, &early_ret);
                    if (early_ret) |er| return .{ .ret = er };
                    return .{ .ret = v };
                }
                return .{ .ret = .none };
            },
            .break_stmt => return .brk,
            .continue_stmt => return .cont,
            .channel_decl => |cd| {
                const ch = try self.rt.makeChannel(cd.name);
                try scope.define(alloc, cd.name, ch);
                return .{ .normal = ch };
            },
            .send_stmt => |ss| {
                var early_ret: ?Value = null;
                const val = try self.evalExpr(ss.value, scope, &early_ret);
                if (early_ret) |er| return .{ .ret = er };
                const ch_val = try self.evalExpr(ss.channel, scope, &early_ret);
                if (early_ret) |er| return .{ .ret = er };
                if (ch_val == .channel) {
                    try ch_val.channel.queue.append(alloc, val);
                }
                return .{ .normal = val };
            },
            .fiber_def => |fd| {
                const f_scope = try alloc.create(Scope);
                f_scope.* = .{ .parent = scope, .is_fn_boundary = true };
                const f_state = try alloc.create(FiberState);
                f_state.* = .{
                    .body = fd.body,
                    .scope = f_scope,
                    .ip = 0,
                    .done = false,
                };
                const fib = try alloc.create(runtime.Fiber);
                fib.* = .{
                    .name = fd.name,
                    .user_data = f_state,
                };
                const val: Value = .{ .fiber = fib };
                try scope.define(alloc, fd.name, val);
                return .{ .normal = val };
            },
            .yield_stmt => |ys| {
                if (ys.value) |vexpr| {
                    var early_ret: ?Value = null;
                    const v = try self.evalExpr(vexpr, scope, &early_ret);
                    if (early_ret) |er| return .{ .ret = er };
                    return .{ .yield_val = v };
                }
                return .{ .yield_val = .none };
            },
            .task_stmt => |ts| {
                var task_scope = Scope{ .parent = scope, .is_fn_boundary = true };
                _ = try self.execStmts(ts.body, &task_scope);
                return .{ .normal = .none };
            },
            .import_stmt => |is| {
                if (parser.isExternalLibraryPath(is.module_path)) {
                    try self.loadExternalLibrary(is.module_path, &.{}, scope);
                    return .{ .normal = .none };
                }
                try self.loadModule(is.module_path, is.alias, null, scope);
                return .{ .normal = .none };
            },
            .from_import_stmt => |fis| {
                if (parser.isExternalLibraryPath(fis.module_path)) {
                    var defs: std.ArrayList(ast.ExternFnDef) = .empty;
                    for (fis.symbols) |sym| {
                        try defs.append(alloc, .{
                            .library = fis.module_path,
                            .name = sym.name,
                            .alias = sym.alias,
                            .params = sym.params orelse &.{},
                            .ret_type = sym.ret_type,
                            .has_explicit_sig = (sym.params != null or sym.ret_type != .auto),
                        });
                    }
                    try self.loadExternalLibrary(fis.module_path, defs.items, scope);
                    return .{ .normal = .none };
                }
                try self.loadModule(fis.module_path, null, fis.symbols, scope);
                return .{ .normal = .none };
            },
            .extern_fn_def => |efd| {
                try self.loadExternalLibrary(efd.library, &.{efd}, scope);
                return .{ .normal = .none };
            },
            .expr_stmt => |e| {
                var early_ret: ?Value = null;
                const v = try self.evalExpr(e, scope, &early_ret);
                if (early_ret) |er| return .{ .ret = er };
                return .{ .normal = v };
            },
        }
    }

    fn stepFiber(self: *EngageVM, fib: *runtime.Fiber) anyerror!Value {
        if (fib.done or fib.user_data == null) return .none;
        const state: *FiberState = @ptrCast(@alignCast(fib.user_data.?));
        if (state.done or state.ip >= state.body.len) {
            fib.done = true;
            return .none;
        }
        var last: Value = .none;
        while (state.ip < state.body.len) {
            const st = state.body[state.ip];
            state.ip += 1;
            const sig = try self.execStmt(st, state.scope);
            switch (sig) {
                .normal => |v| last = v,
                .yield_val => |v| return v,
                .ret => |v| {
                    state.done = true;
                    fib.done = true;
                    return v;
                },
                .brk, .cont => break,
            }
        }
        state.done = true;
        fib.done = true;
        return last;
    }

    fn loadModule(
        self: *EngageVM,
        raw_path: []const u8,
        alias: ?[]const u8,
        symbols: ?[]const ast.ImportSymbol,
        scope: *Scope,
    ) anyerror!void {
        const alloc = self.allocator();
        if (parser.isExternalLibraryPath(raw_path)) {
            if (symbols) |syms| {
                var defs: std.ArrayList(ast.ExternFnDef) = .empty;
                for (syms) |sym| {
                    try defs.append(alloc, .{
                        .library = raw_path,
                        .name = sym.name,
                        .alias = sym.alias,
                        .params = sym.params orelse &.{},
                        .ret_type = sym.ret_type,
                        .has_explicit_sig = (sym.params != null or sym.ret_type != .auto),
                    });
                }
                return self.loadExternalLibrary(raw_path, defs.items, scope);
            }
            return;
        }

        // If it's a built-in stdlib module name (strings, math, files, collections, types), create a namespace table
        const builtins = [_][]const u8{ "strings", "math", "files", "collections", "types" };
        for (builtins) |bname| {
            if (std.mem.eql(u8, raw_path, bname)) {
                const mod_tbl = try self.rt.makeTable();
                const bind_name = alias orelse raw_path;
                try scope.define(alloc, bind_name, mod_tbl);
                return;
            }
        }

        const filename = if (std.mem.endsWith(u8, raw_path, ".engage"))
            raw_path
        else
            try std.fmt.allocPrint(alloc, "{s}.engage", .{raw_path});

        const full_path = if (std.mem.eql(u8, self.base_dir, "."))
            filename
        else
            try std.fmt.allocPrint(alloc, "{s}/{s}", .{ self.base_dir, filename });

        if (self.rt.io) |io| {
            const src = std.Io.Dir.cwd().readFileAlloc(io, full_path, alloc, .limited(16 * 1024 * 1024)) catch blk: {
                break :blk std.Io.Dir.cwd().readFileAlloc(io, filename, alloc, .limited(16 * 1024 * 1024)) catch return;
            };
            const mod_prog = try parser.parseSource(alloc, src);
            var mod_scope = Scope{ .parent = &self.global_scope };
            _ = try self.execStmts(mod_prog.statements, &mod_scope);

            const mod_tbl = try self.rt.makeTable();
            var it = mod_scope.vars.iterator();
            while (it.next()) |e| {
                try mod_tbl.table.map.put(alloc, e.key_ptr.*, e.value_ptr.*);
            }

            if (symbols) |syms| {
                for (syms) |sym| {
                    const target_name = sym.alias orelse sym.name;
                    if (mod_scope.get(sym.name)) |v| {
                        try scope.define(alloc, target_name, v);
                    }
                }
            } else {
                const bind_name = alias orelse raw_path;
                try scope.define(alloc, bind_name, mod_tbl);
            }
        }
    }

    fn cTypeStr(ffi_type: ast.FfiType) []const u8 {
        return switch (ffi_type) {
            .number, .auto => "f64",
            .int => "i64",
            .string => "[*:0]const u8",
            .bool_type => "bool",
            .pointer => "?*anyopaque",
            .void_type => "void",
        };
    }

    pub fn loadExternalLibrary(
        self: *EngageVM,
        raw_lib_path: []const u8,
        symbols: []const ast.ExternFnDef,
        scope: *Scope,
    ) anyerror!void {
        const alloc = self.allocator();
        _ = scope;

        const is_sys = std.mem.eql(u8, raw_lib_path, "c") or
            std.mem.eql(u8, raw_lib_path, "libc") or
            std.mem.eql(u8, raw_lib_path, "m") or
            std.mem.eql(u8, raw_lib_path, "kernel32") or
            std.mem.eql(u8, raw_lib_path, "user32");

        const is_precompiled = is_sys or
            std.mem.endsWith(u8, raw_lib_path, ".dll") or
            std.mem.endsWith(u8, raw_lib_path, ".so") or
            std.mem.endsWith(u8, raw_lib_path, ".dylib");

        const full_lib_path = if (is_sys or std.mem.eql(u8, self.base_dir, ".") or self.base_dir.len == 0 or std.Io.Dir.path.isAbsolute(raw_lib_path))
            raw_lib_path
        else
            try std.fmt.allocPrint(alloc, "{s}/{s}", .{ self.base_dir, raw_lib_path });

        var lib: runtime.SharedLib = undefined;
        if (self.loaded_shared_libs.get(raw_lib_path)) |existing| {
            lib = existing;
        } else if (is_precompiled) {
            const actual_path = if (is_sys and builtin.os.tag == .windows) "msvcrt.dll" else full_lib_path;
            lib = runtime.SharedLib.open(actual_path, alloc) catch |err| blk: {
                if (is_sys and builtin.os.tag == .windows) {
                    break :blk try runtime.SharedLib.open("ucrtbase.dll", alloc);
                } else return err;
            };
            try self.loaded_shared_libs.put(alloc, raw_lib_path, lib);
        } else {
            // Source file: .zig, .c, .cpp, .cc
            const io = self.rt.io orelse return error.IoRequiredForExternalCompilation;
            std.Io.Dir.cwd().createDirPath(io, ".engage-cache") catch {};

            var clean_id_buf: std.ArrayList(u8) = .empty;
            for (raw_lib_path) |ch| {
                if ((ch >= 'a' and ch <= 'z') or (ch >= 'A' and ch <= 'Z') or (ch >= '0' and ch <= '9')) {
                    try clean_id_buf.append(alloc, ch);
                } else {
                    try clean_id_buf.append(alloc, '_');
                }
            }
            const clean_id = clean_id_buf.items;

            const dll_ext = switch (builtin.os.tag) {
                .windows => ".dll",
                .macos, .ios, .watchos, .tvos, .visionos => ".dylib",
                else => ".so",
            };

            const bridge_zig_path = try std.fmt.allocPrint(alloc, "._engage_bridge_{s}.zig", .{clean_id});
            const out_dll_path = try std.fmt.allocPrint(alloc, ".engage-cache/bridge_{s}{s}", .{ clean_id, dll_ext });

            // Generate bridge zig file
            var bridge_src: std.ArrayList(u8) = .empty;
            try bridge_src.appendSlice(alloc, "// Auto-generated Engage FFI bridge\n");
            try bridge_src.appendSlice(alloc, embedded_runtime_src);
            try bridge_src.appendSlice(alloc, "\n");

            const is_zig = std.mem.endsWith(u8, raw_lib_path, ".zig");
            if (is_zig) {
                const fwd_path = try alloc.dupe(u8, full_lib_path);
                for (fwd_path) |*ch| {
                    if (ch.* == '\\') ch.* = '/';
                }
                const import_path = fwd_path;

                const imp_line = try std.fmt.allocPrint(alloc, "const target_mod = @import(\"{s}\");\n\n", .{import_path});
                try bridge_src.appendSlice(alloc, imp_line);

                for (symbols) |sym| {
                    const fn_decl = try std.fmt.allocPrint(
                        alloc,
                        \\pub export fn engage_bridge_{s}(rt_opaque: ?*anyopaque, in_args: [*]const CValue, num_args: usize, out: *CValue) callconv(.c) void {{
                        \\    var dummy_arena = std.heap.ArenaAllocator.init(std.heap.smp_allocator);
                        \\    defer dummy_arena.deinit();
                        \\    var dummy_rt = Runtime.init(dummy_arena.allocator(), null);
                        \\    const rt_ptr: *Runtime = if (rt_opaque) |r| @ptrCast(@alignCast(r)) else &dummy_rt;
                        \\    var v_args: [16]Value = undefined;
                        \\    const count = @min(num_args, 16);
                        \\    for (0..count) |i| {{
                        \\        v_args[i] = in_args[i].toValue(rt_ptr.allocator);
                        \\    }}
                        \\    const res = callZigFn(target_mod.{s}, rt_ptr, v_args[0..count]) catch |err| {{
                        \\        out.* = CValue.fromValue(rt_ptr.allocator, Value.fromString(@errorName(err)));
                        \\        return;
                        \\    }};
                        \\    out.* = CValue.fromValue(rt_ptr.allocator, res);
                        \\}}
                        \\
                    ,
                        .{ sym.name, sym.name },
                    );
                    try bridge_src.appendSlice(alloc, fn_decl);
                }
            } else {
                // C or C++ source file
                for (symbols) |sym| {
                    const c_ret = cTypeStr(sym.ret_type);
                    var c_params: std.ArrayList(u8) = .empty;
                    for (sym.params, 0..) |p, i| {
                        if (i > 0) try c_params.appendSlice(alloc, ", ");
                        const pt = cTypeStr(p.ffi_type);
                        const pdecl = try std.fmt.allocPrint(alloc, "p{d}: {s}", .{ i, pt });
                        try c_params.appendSlice(alloc, pdecl);
                    }
                    const extern_decl = try std.fmt.allocPrint(alloc, "extern \"c\" fn {s}({s}) callconv(.c) {s};\n", .{ sym.name, c_params.items, c_ret });
                    try bridge_src.appendSlice(alloc, extern_decl);

                    var call_args: std.ArrayList(u8) = .empty;
                    for (sym.params, 0..) |p, i| {
                        if (i > 0) try call_args.appendSlice(alloc, ", ");
                        const arg_cast = switch (p.ffi_type) {
                            .number, .auto => try std.fmt.allocPrint(alloc, "if (num_args > {d}) in_args[{d}].num else 0.0", .{ i, i }),
                            .int => try std.fmt.allocPrint(alloc, "if (num_args > {d}) @as(i64, @intFromFloat(in_args[{d}].num)) else 0", .{ i, i }),
                            .string => try std.fmt.allocPrint(alloc, "if (num_args > {d}) @as([*:0]const u8, @ptrCast(in_args[{d}].str_ptr)) else \"\"", .{ i, i }),
                            .bool_type => try std.fmt.allocPrint(alloc, "if (num_args > {d}) (in_args[{d}].num != 0.0) else false", .{ i, i }),
                            .pointer => try std.fmt.allocPrint(alloc, "if (num_args > {d}) in_args[{d}].ptr else null", .{ i, i }),
                            .void_type => "{}",
                        };
                        try call_args.appendSlice(alloc, arg_cast);
                    }
                    const is_void = sym.ret_type == .void_type;
                    const call_stmt = if (is_void)
                        try std.fmt.allocPrint(alloc, "{s}({s});\n", .{ sym.name, call_args.items })
                    else
                        try std.fmt.allocPrint(alloc, "const c_res = {s}({s});\n", .{ sym.name, call_args.items });
                    const ret_assign = switch (sym.ret_type) {
                        .number, .auto => "out.* = .{ .tag = .number, .num = c_res };",
                        .int => "out.* = .{ .tag = .number, .num = @floatFromInt(c_res) };",
                        .string => "out.* = .{ .tag = .string, .str_ptr = c_res, .str_len = std.mem.span(c_res).len };",
                        .bool_type => "out.* = .{ .tag = .number, .num = if (c_res) 1.0 else 0.0 };",
                        .pointer => "out.* = .{ .tag = .pointer, .ptr = c_res };",
                        .void_type => "out.* = .{ .tag = .none };",
                    };
                    const bridge_fn = try std.fmt.allocPrint(
                        alloc,
                        \\pub export fn engage_bridge_{s}(rt_opaque: ?*anyopaque, in_args: [*]const CValue, num_args: usize, out: *CValue) callconv(.c) void {{
                        \\    _ = rt_opaque;
                        \\    {s}
                        \\    {s}
                        \\}}
                        \\
                    ,
                        .{ sym.name, call_stmt, ret_assign },
                    );
                    try bridge_src.appendSlice(alloc, bridge_fn);
                }
            }

            try std.Io.Dir.cwd().writeFile(io, .{ .sub_path = bridge_zig_path, .data = bridge_src.items });

            var argv: std.ArrayList([]const u8) = .empty;
            try argv.append(alloc, "zig");
            try argv.append(alloc, "build-lib");
            try argv.append(alloc, "-dynamic");
            try argv.append(alloc, bridge_zig_path);
            if (!is_zig) {
                try argv.append(alloc, full_lib_path);
                try argv.append(alloc, "-lc");
                if (std.mem.endsWith(u8, full_lib_path, ".cpp") or std.mem.endsWith(u8, full_lib_path, ".cc") or std.mem.endsWith(u8, full_lib_path, ".cxx")) {
                    try argv.append(alloc, "-lc++");
                }
            }
            const emit_flag = try std.fmt.allocPrint(alloc, "-femit-bin={s}", .{out_dll_path});
            try argv.append(alloc, emit_flag);

            var child = try std.process.spawn(io, .{ .argv = argv.items });
            const term = try child.wait(io);
            _ = std.Io.Dir.cwd().deleteFile(io, bridge_zig_path) catch {};
            switch (term) {
                .exited => |code| {
                    if (code != 0) return error.ExternalLibraryCompilationFailed;
                },
                else => return error.ExternalLibraryCompilationFailed,
            }

            lib = try runtime.SharedLib.open(out_dll_path, alloc);
            try self.loaded_shared_libs.put(alloc, raw_lib_path, lib);
        }

        // Bind each symbol in host_fns
        for (symbols) |sym| {
            const sym_name = try std.fmt.allocPrint(alloc, "engage_bridge_{s}", .{sym.name});
            const sym_z = try runtime.dupeZ(alloc, sym_name);
            defer alloc.free(sym_z);

            if (lib.lookup(runtime.BridgeFn, sym_z)) |bridge_fn| {
                const binding = try alloc.create(DynamicFnBinding);
                binding.* = .{ .bridge_fn = bridge_fn };
                const bind_name = sym.alias orelse sym.name;
                try self.registerFn(bind_name, dynamicBridgeTrampoline, binding);
            } else {
                const raw_z = try runtime.dupeZ(alloc, sym.name);
                defer alloc.free(raw_z);
                if (lib.lookup(*anyopaque, raw_z)) |_| {
                    // Raw C symbol found
                }
            }
        }
    }

    fn evalExpr(self: *EngageVM, expr: *const ast.Expr, scope: *Scope, early_ret: *?Value) anyerror!Value {
        const alloc = self.allocator();
        switch (expr.*) {
            .number => |n| return Value.fromNumber(n),
            .string => |s| return Value.fromString(s),
            .self_expr => return scope.get("self") orelse .none,
            .none_expr => return .none,
            .vector_lit => return self.rt.makeVector(),
            .table_lit => return self.rt.makeTable(),
            .ident => |name| {
                if (scope.get(name)) |v| return v;
                // Auto-call zero-argument user functions or zero-arg builtins
                if (self.functions.get(name)) |fd| {
                    if (fd.params.len == 0) {
                        return self.invokeUserFn(fd, &.{}, scope.get("self"));
                    }
                }
                if (std.mem.eql(u8, name, "create_panel") or std.mem.eql(u8, name, "get_args") or std.mem.eql(u8, name, "random")) {
                    return self.rt.callStdlib(name, &.{});
                }
                return .none;
            },
            .result_lit => |rl| {
                const payload = if (rl.value) |ve| try self.evalExpr(ve, scope, early_ret) else Value.none;
                if (early_ret.* != null) return .none;
                return self.rt.makeResult(rl.is_ok, payload);
            },
            .new_instance => |ni| {
                const rec = try self.rt.makeRecord(ni.record_name);
                if (self.records.get(ni.record_name)) |rdef| {
                    for (rdef.properties) |prop| {
                        const def_val = if (prop.default_value) |de| try self.evalExpr(de, scope, early_ret) else Value.none;
                        if (early_ret.* != null) return .none;
                        try rec.fields.put(alloc, prop.name, def_val);
                    }
                }
                for (ni.props) |pi| {
                    const pval = try self.evalExpr(pi.value, scope, early_ret);
                    if (early_ret.* != null) return .none;
                    try rec.fields.put(alloc, pi.name, pval);
                }
                return .{ .record = rec };
            },
            .member_access => |ma| {
                const obj = try self.evalExpr(ma.object, scope, early_ret);
                if (early_ret.* != null) return .none;
                if (obj == .record) {
                    if (obj.record.fields.get(ma.member)) |fval| return fval;
                    if (self.records.get(obj.record.type_name)) |rdef| {
                        for (rdef.methods) |m| {
                            if (std.mem.eql(u8, m.name, ma.member) and m.params.len == 0) {
                                return self.invokeUserFn(m, &.{}, obj);
                            }
                        }
                    }
                }
                return Runtime.memberGet(obj, ma.member);
            },
            .index_access => |ia| {
                const obj = try self.evalExpr(ia.object, scope, early_ret);
                if (early_ret.* != null) return .none;
                const idx = try self.evalExpr(ia.index, scope, early_ret);
                if (early_ret.* != null) return .none;
                return self.rt.indexGet(obj, idx);
            },
            .receive_expr => |re| {
                const ch_val = try self.evalExpr(re.channel, scope, early_ret);
                if (early_ret.* != null) return .none;
                if (ch_val == .channel and ch_val.channel.queue.items.len > 0) {
                    return ch_val.channel.queue.orderedRemove(0);
                }
                return .none;
            },
            .unary_op => |uo| {
                if (std.mem.eql(u8, uo.op, "call")) {
                    if (uo.operand.* == .ident) {
                        const name = uo.operand.ident;
                        if (scope.get(name)) |v| {
                            if (v == .fiber) return self.stepFiber(v.fiber);
                        }
                        return self.call(name, &.{}) catch .none;
                    }
                    const target = try self.evalExpr(uo.operand, scope, early_ret);
                    if (target == .fiber) return self.stepFiber(target.fiber);
                    return target;
                }
                const operand = try self.evalExpr(uo.operand, scope, early_ret);
                if (early_ret.* != null) return .none;
                if (std.mem.eql(u8, uo.op, "not")) return Runtime.logicalNot(operand);
                if (std.mem.eql(u8, uo.op, "-") or std.mem.eql(u8, uo.op, "minus")) return Runtime.neg(operand);
                if (std.mem.eql(u8, uo.op, "the ok value of")) return Runtime.okValueOf(operand);
                if (std.mem.eql(u8, uo.op, "the error message of")) return Runtime.errorMessageOf(operand);
                return operand;
            },
            .bin_op => |bo| {
                const left = try self.evalExpr(bo.left, scope, early_ret);
                if (early_ret.* != null) return .none;

                if (std.mem.eql(u8, bo.op, "or return error")) {
                    if (left == .result and !left.result.is_ok) {
                        early_ret.* = left;
                        return left;
                    }
                    return Runtime.okValueOf(left);
                }
                if (std.mem.eql(u8, bo.op, "is an Ok")) return Runtime.isAnOk(left);
                if (std.mem.eql(u8, bo.op, "is an Error")) return Runtime.isAnError(left);

                // Short-circuit logical operators
                if (std.mem.eql(u8, bo.op, "and")) {
                    if (!left.isTruthy()) return Value.fromNumber(0);
                    const right = try self.evalExpr(bo.right.?, scope, early_ret);
                    if (early_ret.* != null) return .none;
                    return Value.fromBool(right.isTruthy());
                }
                if (std.mem.eql(u8, bo.op, "or")) {
                    if (left.isTruthy()) return Value.fromNumber(1);
                    const right = try self.evalExpr(bo.right.?, scope, early_ret);
                    if (early_ret.* != null) return .none;
                    return Value.fromBool(right.isTruthy());
                }

                const right = if (bo.right) |re| try self.evalExpr(re, scope, early_ret) else Value.none;
                if (early_ret.* != null) return .none;

                if (std.mem.eql(u8, bo.op, "plus") or std.mem.eql(u8, bo.op, "+")) return self.rt.add(left, right);
                if (std.mem.eql(u8, bo.op, "concatenated with")) return self.rt.concat(left, right);
                if (std.mem.eql(u8, bo.op, "minus") or std.mem.eql(u8, bo.op, "-")) return Runtime.sub(left, right);
                if (std.mem.eql(u8, bo.op, "times") or std.mem.eql(u8, bo.op, "*")) return Runtime.mul(left, right);
                if (std.mem.eql(u8, bo.op, "divided by") or std.mem.eql(u8, bo.op, "/")) return Runtime.div(left, right);
                if (std.mem.eql(u8, bo.op, "modulo") or std.mem.eql(u8, bo.op, "%")) return Runtime.mod(left, right);
                if (std.mem.eql(u8, bo.op, "is") or std.mem.eql(u8, bo.op, "is equal to") or std.mem.eql(u8, bo.op, "==")) return Runtime.eql(left, right);
                if (std.mem.eql(u8, bo.op, "is not") or std.mem.eql(u8, bo.op, "is not equal to") or std.mem.eql(u8, bo.op, "!=")) return Runtime.neq(left, right);
                if (std.mem.eql(u8, bo.op, "is greater than") or std.mem.eql(u8, bo.op, ">")) return Runtime.gt(left, right);
                if (std.mem.eql(u8, bo.op, "is less than") or std.mem.eql(u8, bo.op, "<")) return Runtime.lt(left, right);
                if (std.mem.eql(u8, bo.op, "is greater than or equal to") or std.mem.eql(u8, bo.op, ">=")) return Runtime.gte(left, right);
                if (std.mem.eql(u8, bo.op, "is less than or equal to") or std.mem.eql(u8, bo.op, "<=")) return Runtime.lte(left, right);
                return .none;
            },
            .func_call => |fc| {
                var eval_args: std.ArrayList(Value) = .empty;
                for (fc.args) |ae| {
                    const av = try self.evalExpr(ae, scope, early_ret);
                    if (early_ret.* != null) return .none;
                    try eval_args.append(alloc, av);
                }

                if (fc.callee.* == .member_access) {
                    const ma = fc.callee.member_access;
                    const obj = try self.evalExpr(ma.object, scope, early_ret);
                    if (early_ret.* != null) return .none;
                    if (obj == .record) {
                        if (self.records.get(obj.record.type_name)) |rdef| {
                            for (rdef.methods) |m| {
                                if (std.mem.eql(u8, m.name, ma.member)) {
                                    return self.invokeUserFn(m, eval_args.items, obj);
                                }
                            }
                        }
                        if (obj.record.fields.get(ma.member)) |fval| {
                            return fval;
                        }
                    }
                    // Module or built-in method call (e.g. strings.trim, vec.push, table.keys)
                    if (Runtime.isStdlibFn(ma.member)) {
                        if (obj == .vector or obj == .table) {
                            var full_args: std.ArrayList(Value) = .empty;
                            try full_args.append(alloc, obj);
                            try full_args.appendSlice(alloc, eval_args.items);
                            return self.rt.callStdlib(ma.member, full_args.items);
                        }
                        return self.rt.callStdlib(ma.member, eval_args.items);
                    }
                    return .none;
                }

                if (fc.callee.* == .ident) {
                    const fname = fc.callee.ident;
                    if (self.functions.get(fname)) |fd| {
                        return self.invokeUserFn(fd, eval_args.items, scope.get("self"));
                    }
                    if (self.host_fns.get(fname)) |hb| {
                        return hb.callback(&self.rt, eval_args.items, hb.userdata);
                    }
                    if (Runtime.isStdlibFn(fname)) {
                        return self.rt.callStdlib(fname, eval_args.items);
                    }
                    if (scope.get(fname)) |v| {
                        if (v == .fiber) return self.stepFiber(v.fiber);
                        return v;
                    }
                }

                return .none;
            },
        }
    }
};
