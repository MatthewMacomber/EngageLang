const std = @import("std");
const ast = @import("ast.zig");
const parser = @import("parser.zig");
const runtime = @import("runtime.zig");

const embedded_runtime_src = @embedFile("runtime.zig");

pub const Codegen = struct {
    allocator: std.mem.Allocator,
    lines: std.ArrayList([]const u8) = .empty,
    globals: std.StringArrayHashMapUnmanaged(void) = .empty,
    functions: std.StringArrayHashMapUnmanaged(usize) = .empty, // name -> arity
    records: std.StringArrayHashMapUnmanaged(ast.RecordDef) = .empty,
    fibers: std.StringArrayHashMapUnmanaged(ast.FiberDef) = .empty,
    extern_fns: std.StringArrayHashMapUnmanaged(ast.ExternFnDef) = .empty,
    extern_modules: std.StringArrayHashMapUnmanaged(usize) = .empty,
    temp_counter: usize = 0,

    pub fn init(allocator: std.mem.Allocator) Codegen {
        return .{ .allocator = allocator };
    }

    fn emitLine(self: *Codegen, indent: usize, comptime fmt_str: []const u8, args: anytype) !void {
        var pad_buf: std.ArrayList(u8) = .empty;
        for (0..indent) |_| {
            try pad_buf.appendSlice(self.allocator, "    ");
        }
        const content = try std.fmt.allocPrint(self.allocator, fmt_str, args);
        try pad_buf.appendSlice(self.allocator, content);
        try self.lines.append(self.allocator, try pad_buf.toOwnedSlice(self.allocator));
    }

    fn escapeZigString(self: *Codegen, s: []const u8) ![]const u8 {
        var out: std.ArrayList(u8) = .empty;
        try out.append(self.allocator, '"');
        for (s) |c| {
            switch (c) {
                '\\' => try out.appendSlice(self.allocator, "\\\\"),
                '"' => try out.appendSlice(self.allocator, "\\\""),
                '\n' => try out.appendSlice(self.allocator, "\\n"),
                '\r' => try out.appendSlice(self.allocator, "\\r"),
                '\t' => try out.appendSlice(self.allocator, "\\t"),
                else => {
                    if (c < 32 or c >= 127) {
                        const hex = try std.fmt.allocPrint(self.allocator, "\\x{x:0>2}", .{c});
                        try out.appendSlice(self.allocator, hex);
                    } else {
                        try out.append(self.allocator, c);
                    }
                },
            }
        }
        try out.append(self.allocator, '"');
        return out.toOwnedSlice(self.allocator);
    }

    fn varRef(
        self: *Codegen,
        name: []const u8,
        local_scope: *const std.StringArrayHashMapUnmanaged(void),
    ) ![]const u8 {
        if (local_scope.contains(name)) {
            return std.fmt.allocPrint(self.allocator, "v_{s}", .{name});
        }
        if (self.globals.contains(name)) {
            return std.fmt.allocPrint(self.allocator, "g_{s}", .{name});
        }
        if (self.functions.get(name)) |arity| {
            if (arity == 0) {
                return std.fmt.allocPrint(self.allocator, "(try engage_fn_{s}(rt))", .{name});
            }
        }
        if (std.mem.eql(u8, name, "create_panel") or std.mem.eql(u8, name, "get_args") or std.mem.eql(u8, name, "random")) {
            const esc = try self.escapeZigString(name);
            return std.fmt.allocPrint(self.allocator, "(try rt.callStdlib({s}, &.{{}}))", .{esc});
        }
        return std.fmt.allocPrint(self.allocator, "Value.none", .{});
    }

    fn emitExpr(
        self: *Codegen,
        expr: *const ast.Expr,
        local_scope: *const std.StringArrayHashMapUnmanaged(void),
    ) anyerror![]const u8 {
        switch (expr.*) {
            .number => |n| {
                const as_i64: i64 = @intFromFloat(n);
                if (@as(f64, @floatFromInt(as_i64)) == n and @abs(n) < 9e15) {
                    return std.fmt.allocPrint(self.allocator, "Value.fromNumber({d}.0)", .{as_i64});
                }
                return std.fmt.allocPrint(self.allocator, "Value.fromNumber({d})", .{n});
            },
            .string => |s| {
                const esc = try self.escapeZigString(s);
                return std.fmt.allocPrint(self.allocator, "Value.fromString({s})", .{esc});
            },
            .self_expr => return "v_self",
            .none_expr => return "Value.none",
            .vector_lit => return "(try rt.makeVector())",
            .table_lit => return "(try rt.makeTable())",
            .ident => |name| return self.varRef(name, local_scope),
            .result_lit => |rl| {
                const val_code = if (rl.value) |ve| try self.emitExpr(ve, local_scope) else "Value.none";
                const bool_lit = if (rl.is_ok) "true" else "false";
                return std.fmt.allocPrint(self.allocator, "(try rt.makeResult({s}, {s}))", .{ bool_lit, val_code });
            },
            .new_instance => |ni| {
                var props_buf: std.ArrayList(u8) = .empty;
                for (ni.props, 0..) |p, idx| {
                    if (idx > 0) try props_buf.appendSlice(self.allocator, ", ");
                    const esc_name = try self.escapeZigString(p.name);
                    const pval_code = try self.emitExpr(p.value, local_scope);
                    const entry = try std.fmt.allocPrint(
                        self.allocator,
                        ".{{ .name = {s}, .val = {s} }}",
                        .{ esc_name, pval_code },
                    );
                    try props_buf.appendSlice(self.allocator, entry);
                }
                if (self.records.contains(ni.record_name)) {
                    return std.fmt.allocPrint(
                        self.allocator,
                        "(try engage_new_{s}(rt, &.{{{s}}}))",
                        .{ ni.record_name, props_buf.items },
                    );
                }
                const esc_rname = try self.escapeZigString(ni.record_name);
                return std.fmt.allocPrint(
                    self.allocator,
                    "(try engage_new_generic(rt, {s}, &.{{{s}}}))",
                    .{ esc_rname, props_buf.items },
                );
            },
            .member_access => |ma| {
                const obj_code = try self.emitExpr(ma.object, local_scope);
                const esc_mem = try self.escapeZigString(ma.member);
                return std.fmt.allocPrint(
                    self.allocator,
                    "(try engage_get_member(rt, {s}, {s}))",
                    .{ obj_code, esc_mem },
                );
            },
            .index_access => |ia| {
                const obj_code = try self.emitExpr(ia.object, local_scope);
                const idx_code = try self.emitExpr(ia.index, local_scope);
                return std.fmt.allocPrint(
                    self.allocator,
                    "(try rt.indexGet({s}, {s}))",
                    .{ obj_code, idx_code },
                );
            },
            .receive_expr => |re| {
                const ch_code = try self.emitExpr(re.channel, local_scope);
                return std.fmt.allocPrint(self.allocator, "engage_channel_receive({s})", .{ch_code});
            },
            .unary_op => |uo| {
                if (std.mem.eql(u8, uo.op, "call")) {
                    if (uo.operand.* == .ident) {
                        const fn_name = uo.operand.ident;
                        if (self.functions.contains(fn_name)) {
                            return std.fmt.allocPrint(self.allocator, "(try engage_fn_{s}(rt))", .{fn_name});
                        }
                        if (runtime.Runtime.isStdlibFn(fn_name)) {
                            const esc = try self.escapeZigString(fn_name);
                            return std.fmt.allocPrint(self.allocator, "(try rt.callStdlib({s}, &.{{}}))", .{esc});
                        }
                    }
                    const rand_code = try self.emitExpr(uo.operand, local_scope);
                    return std.fmt.allocPrint(self.allocator, "(if ({s} == .fiber) try rt.stepFiber({s}) else {s})", .{ rand_code, rand_code, rand_code });
                }
                const rand_code = try self.emitExpr(uo.operand, local_scope);
                if (std.mem.eql(u8, uo.op, "not")) {
                    return std.fmt.allocPrint(self.allocator, "Runtime.logicalNot({s})", .{rand_code});
                }
                if (std.mem.eql(u8, uo.op, "-") or std.mem.eql(u8, uo.op, "minus")) {
                    return std.fmt.allocPrint(self.allocator, "Runtime.neg({s})", .{rand_code});
                }
                if (std.mem.eql(u8, uo.op, "the ok value of")) {
                    return std.fmt.allocPrint(self.allocator, "Runtime.okValueOf({s})", .{rand_code});
                }
                if (std.mem.eql(u8, uo.op, "the error message of")) {
                    return std.fmt.allocPrint(self.allocator, "Runtime.errorMessageOf({s})", .{rand_code});
                }
                return rand_code;
            },
            .bin_op => |bo| {
                const l_code = try self.emitExpr(bo.left, local_scope);
                if (std.mem.eql(u8, bo.op, "or return error")) {
                    return std.fmt.allocPrint(self.allocator, "(try rt.unwrapOrReturnError({s}))", .{l_code});
                }
                if (std.mem.eql(u8, bo.op, "is an Ok")) {
                    return std.fmt.allocPrint(self.allocator, "Runtime.isAnOk({s})", .{l_code});
                }
                if (std.mem.eql(u8, bo.op, "is an Error")) {
                    return std.fmt.allocPrint(self.allocator, "Runtime.isAnError({s})", .{l_code});
                }
                const r_code = if (bo.right) |re| try self.emitExpr(re, local_scope) else "Value.none";

                if (std.mem.eql(u8, bo.op, "plus") or std.mem.eql(u8, bo.op, "+")) {
                    return std.fmt.allocPrint(self.allocator, "(try rt.add({s}, {s}))", .{ l_code, r_code });
                }
                if (std.mem.eql(u8, bo.op, "concatenated with")) {
                    return std.fmt.allocPrint(self.allocator, "(try rt.concat({s}, {s}))", .{ l_code, r_code });
                }
                if (std.mem.eql(u8, bo.op, "minus") or std.mem.eql(u8, bo.op, "-")) {
                    return std.fmt.allocPrint(self.allocator, "Runtime.sub({s}, {s})", .{ l_code, r_code });
                }
                if (std.mem.eql(u8, bo.op, "times") or std.mem.eql(u8, bo.op, "*")) {
                    return std.fmt.allocPrint(self.allocator, "Runtime.mul({s}, {s})", .{ l_code, r_code });
                }
                if (std.mem.eql(u8, bo.op, "divided by") or std.mem.eql(u8, bo.op, "/")) {
                    return std.fmt.allocPrint(self.allocator, "Runtime.div({s}, {s})", .{ l_code, r_code });
                }
                if (std.mem.eql(u8, bo.op, "modulo") or std.mem.eql(u8, bo.op, "%")) {
                    return std.fmt.allocPrint(self.allocator, "Runtime.mod({s}, {s})", .{ l_code, r_code });
                }
                if (std.mem.eql(u8, bo.op, "is") or std.mem.eql(u8, bo.op, "is equal to") or std.mem.eql(u8, bo.op, "==")) {
                    return std.fmt.allocPrint(self.allocator, "Runtime.eql({s}, {s})", .{ l_code, r_code });
                }
                if (std.mem.eql(u8, bo.op, "is not") or std.mem.eql(u8, bo.op, "is not equal to") or std.mem.eql(u8, bo.op, "!=")) {
                    return std.fmt.allocPrint(self.allocator, "Runtime.neq({s}, {s})", .{ l_code, r_code });
                }
                if (std.mem.eql(u8, bo.op, "is greater than") or std.mem.eql(u8, bo.op, ">")) {
                    return std.fmt.allocPrint(self.allocator, "Runtime.gt({s}, {s})", .{ l_code, r_code });
                }
                if (std.mem.eql(u8, bo.op, "is less than") or std.mem.eql(u8, bo.op, "<")) {
                    return std.fmt.allocPrint(self.allocator, "Runtime.lt({s}, {s})", .{ l_code, r_code });
                }
                if (std.mem.eql(u8, bo.op, "is greater than or equal to") or std.mem.eql(u8, bo.op, ">=")) {
                    return std.fmt.allocPrint(self.allocator, "Runtime.gte({s}, {s})", .{ l_code, r_code });
                }
                if (std.mem.eql(u8, bo.op, "is less than or equal to") or std.mem.eql(u8, bo.op, "<=")) {
                    return std.fmt.allocPrint(self.allocator, "Runtime.lte({s}, {s})", .{ l_code, r_code });
                }
                if (std.mem.eql(u8, bo.op, "and")) {
                    return std.fmt.allocPrint(self.allocator, "Value.fromBool(({s}).isTruthy() and ({s}).isTruthy())", .{ l_code, r_code });
                }
                if (std.mem.eql(u8, bo.op, "or")) {
                    return std.fmt.allocPrint(self.allocator, "Value.fromBool(({s}).isTruthy() or ({s}).isTruthy())", .{ l_code, r_code });
                }
                return "Value.none";
            },
            .func_call => |fc| {
                var args_slice_buf: std.ArrayList(u8) = .empty;
                for (fc.args, 0..) |arg_expr, idx| {
                    if (idx > 0) try args_slice_buf.appendSlice(self.allocator, ", ");
                    const acode = try self.emitExpr(arg_expr, local_scope);
                    try args_slice_buf.appendSlice(self.allocator, acode);
                }

                if (fc.callee.* == .member_access) {
                    const ma = fc.callee.member_access;
                    const obj_code = try self.emitExpr(ma.object, local_scope);
                    const esc_mem = try self.escapeZigString(ma.member);
                    return std.fmt.allocPrint(
                        self.allocator,
                        "(try engage_call_method(rt, {s}, {s}, &.{{{s}}}))",
                        .{ obj_code, esc_mem, args_slice_buf.items },
                    );
                }

                if (fc.callee.* == .ident) {
                    const fname = fc.callee.ident;
                    if (self.extern_fns.get(fname)) |efd| {
                        if (std.mem.endsWith(u8, efd.library, ".zig")) {
                            return std.fmt.allocPrint(
                                self.allocator,
                                "(try engage_fn_{s}(rt, &.{{{s}}}))",
                                .{ fname, args_slice_buf.items },
                            );
                        }
                    }
                    if (self.functions.get(fname)) |arity| {
                        var call_buf: std.ArrayList(u8) = .empty;
                        try call_buf.appendSlice(self.allocator, "rt");
                        for (0..arity) |i| {
                            try call_buf.appendSlice(self.allocator, ", ");
                            if (i < fc.args.len) {
                                try call_buf.appendSlice(self.allocator, try self.emitExpr(fc.args[i], local_scope));
                            } else {
                                try call_buf.appendSlice(self.allocator, "Value.none");
                            }
                        }
                        return std.fmt.allocPrint(
                            self.allocator,
                            "(try engage_fn_{s}({s}))",
                            .{ fname, call_buf.items },
                        );
                    }
                    if (runtime.Runtime.isStdlibFn(fname)) {
                        const esc_fn = try self.escapeZigString(fname);
                        return std.fmt.allocPrint(
                            self.allocator,
                            "(try rt.callStdlib({s}, &.{{{s}}}))",
                            .{ esc_fn, args_slice_buf.items },
                        );
                    }
                    // Could be a zero-arg variable access or a fiber call
                    const vcode = try self.varRef(fname, local_scope);
                    return std.fmt.allocPrint(self.allocator, "(if ({s} == .fiber) try rt.stepFiber({s}) else {s})", .{ vcode, vcode, vcode });
                }

                const target_code = try self.emitExpr(fc.callee, local_scope);
                return std.fmt.allocPrint(self.allocator, "(if ({s} == .fiber) try rt.stepFiber({s}) else {s})", .{ target_code, target_code, target_code });
            },
        }
    }

    fn emitStmt(
        self: *Codegen,
        st: ast.Stmt,
        indent: usize,
        local_scope: *std.StringArrayHashMapUnmanaged(void),
        is_top_level: bool,
    ) anyerror!void {
        switch (st) {
            .var_assign => |va| {
                const vcode = try self.emitExpr(va.value, local_scope);
                if (is_top_level and self.globals.contains(va.name)) {
                    try self.emitLine(indent, "g_{s} = {s};", .{ va.name, vcode });
                } else if (local_scope.contains(va.name)) {
                    try self.emitLine(indent, "v_{s} = {s};", .{ va.name, vcode });
                } else {
                    try local_scope.put(self.allocator, va.name, {});
                    try self.emitLine(indent, "var v_{s}: Value = {s}; _ = &v_{s};", .{ va.name, vcode, va.name });
                }
            },
            .set_stmt => |ss| {
                const vcode = try self.emitExpr(ss.value, local_scope);
                switch (ss.target.*) {
                    .ident => |name| {
                        if (local_scope.contains(name)) {
                            try self.emitLine(indent, "v_{s} = {s};", .{ name, vcode });
                        } else if (self.globals.contains(name)) {
                            try self.emitLine(indent, "g_{s} = {s};", .{ name, vcode });
                        } else {
                            try local_scope.put(self.allocator, name, {});
                            try self.emitLine(indent, "var v_{s}: Value = {s}; _ = &v_{s};", .{ name, vcode, name });
                        }
                    },
                    .member_access => |ma| {
                        const obj_code = try self.emitExpr(ma.object, local_scope);
                        const esc_mem = try self.escapeZigString(ma.member);
                        try self.emitLine(indent, "try rt.memberSet({s}, {s}, {s});", .{ obj_code, esc_mem, vcode });
                    },
                    else => {},
                }
            },
            .index_assign => |ia| {
                const ocode = try self.emitExpr(ia.object, local_scope);
                const icode = try self.emitExpr(ia.index, local_scope);
                const vcode = try self.emitExpr(ia.value, local_scope);
                try self.emitLine(indent, "try rt.indexSet({s}, {s}, {s});", .{ ocode, icode, vcode });
            },
            .return_stmt => |ret| {
                if (ret.value) |ve| {
                    const vcode = try self.emitExpr(ve, local_scope);
                    try self.emitLine(indent, "return {s};", .{vcode});
                } else {
                    try self.emitLine(indent, "return Value.none;", .{});
                }
            },
            .break_stmt => try self.emitLine(indent, "break;", .{}),
            .continue_stmt => try self.emitLine(indent, "continue;", .{}),
            .if_stmt => |ifs| {
                for (ifs.branches, 0..) |b, idx| {
                    const ccode = try self.emitExpr(b.condition, local_scope);
                    if (idx == 0) {
                        try self.emitLine(indent, "if (({s}).isTruthy()) {{", .{ccode});
                    } else {
                        try self.emitLine(indent, "}} else if (({s}).isTruthy()) {{", .{ccode});
                    }
                    var branch_scope = try local_scope.clone(self.allocator);
                    for (b.body) |bst| {
                        try self.emitStmt(bst, indent + 1, &branch_scope, is_top_level);
                    }
                }
                if (ifs.else_body.len > 0) {
                    try self.emitLine(indent, "}} else {{", .{});
                    var else_scope = try local_scope.clone(self.allocator);
                    for (ifs.else_body) |est| {
                        try self.emitStmt(est, indent + 1, &else_scope, is_top_level);
                    }
                }
                try self.emitLine(indent, "}}", .{});
            },
            .while_stmt => |ws| {
                const ccode = try self.emitExpr(ws.condition, local_scope);
                try self.emitLine(indent, "while (({s}).isTruthy()) {{", .{ccode});
                var loop_scope = try local_scope.clone(self.allocator);
                for (ws.body) |bst| {
                    try self.emitStmt(bst, indent + 1, &loop_scope, is_top_level);
                }
                try self.emitLine(indent, "}}", .{});
            },
            .repeat_stmt => |rs| {
                const ccode = try self.emitExpr(rs.count, local_scope);
                const tid = self.temp_counter;
                self.temp_counter += 1;
                try self.emitLine(indent, "{{", .{});
                try self.emitLine(indent + 1, "const _rep_n_{d}: usize = @intFromFloat(@max(0.0, ({s}).asNumber()));", .{ tid, ccode });
                try self.emitLine(indent + 1, "var _rep_i_{d}: usize = 0;", .{tid});
                try self.emitLine(indent + 1, "while (_rep_i_{d} < _rep_n_{d}) : (_rep_i_{d} += 1) {{", .{ tid, tid, tid });
                var loop_scope = try local_scope.clone(self.allocator);
                for (rs.body) |bst| {
                    try self.emitStmt(bst, indent + 2, &loop_scope, is_top_level);
                }
                try self.emitLine(indent + 1, "}}", .{});
                try self.emitLine(indent, "}}", .{});
            },
            .for_each_stmt => |fs| {
                const icode = try self.emitExpr(fs.iterable, local_scope);
                const tid = self.temp_counter;
                self.temp_counter += 1;
                try self.emitLine(indent, "{{", .{});
                try self.emitLine(indent + 1, "const _iter_{d} = {s};", .{ tid, icode });
                try self.emitLine(indent + 1, "if (_iter_{d} == .vector) {{", .{tid});
                try self.emitLine(indent + 2, "for (_iter_{d}.vector.items.items) |_item_{d}| {{", .{ tid, tid });
                var loop_scope = try local_scope.clone(self.allocator);
                try loop_scope.put(self.allocator, fs.item_name, {});
                try self.emitLine(indent + 3, "var v_{s}: Value = _item_{d}; _ = &v_{s};", .{ fs.item_name, tid, fs.item_name });
                for (fs.body) |bst| {
                    try self.emitStmt(bst, indent + 3, &loop_scope, is_top_level);
                }
                try self.emitLine(indent + 2, "}}", .{});
                try self.emitLine(indent + 1, "}}", .{});
                try self.emitLine(indent, "}}", .{});
            },
            .channel_decl => |cd| {
                const esc_name = try self.escapeZigString(cd.name);
                if (is_top_level and self.globals.contains(cd.name)) {
                    try self.emitLine(indent, "g_{s} = try rt.makeChannel({s});", .{ cd.name, esc_name });
                } else {
                    try local_scope.put(self.allocator, cd.name, {});
                    try self.emitLine(indent, "var v_{s}: Value = try rt.makeChannel({s}); _ = &v_{s};", .{ cd.name, esc_name, cd.name });
                }
            },
            .send_stmt => |ss| {
                const vcode = try self.emitExpr(ss.value, local_scope);
                const ch_code = try self.emitExpr(ss.channel, local_scope);
                try self.emitLine(indent, "try engage_channel_send(rt, {s}, {s});", .{ ch_code, vcode });
            },
            .fiber_def => |fd| {
                const esc_name = try self.escapeZigString(fd.name);
                if (is_top_level and self.globals.contains(fd.name)) {
                    try self.emitLine(indent, "g_{s} = try rt.makeFiber({s}, engage_fiber_{s});", .{ fd.name, esc_name, fd.name });
                } else {
                    try local_scope.put(self.allocator, fd.name, {});
                    try self.emitLine(indent, "var v_{s}: Value = try rt.makeFiber({s}, engage_fiber_{s}); _ = &v_{s};", .{ fd.name, esc_name, fd.name, fd.name });
                }
            },
            .task_stmt => |ts| {
                var task_scope = try local_scope.clone(self.allocator);
                for (ts.body) |bst| {
                    try self.emitStmt(bst, indent, &task_scope, is_top_level);
                }
            },
            .expr_stmt => |e| {
                const ecode = try self.emitExpr(e, local_scope);
                try self.emitLine(indent, "_ = {s};", .{ecode});
            },
            .func_def, .record_def, .yield_stmt, .import_stmt, .from_import_stmt, .extern_fn_def => {},
        }
    }

    fn collectFiberLocals(self: *Codegen, stmts: []const ast.Stmt, out: *std.StringArrayHashMapUnmanaged(void)) !void {
        for (stmts) |st| {
            switch (st) {
                .var_assign => |va| try out.put(self.allocator, va.name, {}),
                .for_each_stmt => |fs| {
                    try out.put(self.allocator, fs.item_name, {});
                    try self.collectFiberLocals(fs.body, out);
                },
                .if_stmt => |ifs| {
                    for (ifs.branches) |b| try self.collectFiberLocals(b.body, out);
                    try self.collectFiberLocals(ifs.else_body, out);
                },
                .while_stmt => |ws| try self.collectFiberLocals(ws.body, out),
                .repeat_stmt => |rs| try self.collectFiberLocals(rs.body, out),
                else => {},
            }
        }
    }

    fn emitFiberDef(self: *Codegen, fd: ast.FiberDef) !void {
        var fiber_locals: std.StringArrayHashMapUnmanaged(void) = .empty;
        try self.collectFiberLocals(fd.body, &fiber_locals);

        try self.emitLine(0, "fn engage_fiber_{s}(rt: *Runtime, fib: *Fiber) anyerror!Value {{", .{fd.name});
        try self.emitLine(1, "rt.touch();", .{});
        try self.emitLine(1, "if (fib.done) return Value.none;", .{});
        try self.emitLine(1, "const state: usize = @intCast(@intFromPtr(fib.user_data));", .{});

        var lit = fiber_locals.iterator();
        while (lit.next()) |entry| {
            const esc_vname = try self.escapeZigString(entry.key_ptr.*);
            try self.emitLine(1, "var v_{s}: Value = fib.locals.get({s}) orelse Value.none; _ = &v_{s};", .{ entry.key_ptr.*, esc_vname, entry.key_ptr.* });
        }

        try self.emitLine(1, "switch (state) {{", .{});

        var current_state: usize = 0;
        var state_terminated: bool = false;
        try self.emitLine(2, "{d} => {{", .{current_state});

        var local_scope = try fiber_locals.clone(self.allocator);

        for (fd.body) |st| {
            switch (st) {
                .yield_stmt => |ys| {
                    var sit = fiber_locals.iterator();
                    while (sit.next()) |entry| {
                        const esc_vname = try self.escapeZigString(entry.key_ptr.*);
                        try self.emitLine(3, "try fib.locals.put(rt.allocator, {s}, v_{s});", .{ esc_vname, entry.key_ptr.* });
                    }
                    current_state += 1;
                    try self.emitLine(3, "fib.user_data = @ptrFromInt({d});", .{current_state});
                    if (ys.value) |ve| {
                        const vcode = try self.emitExpr(ve, &local_scope);
                        try self.emitLine(3, "return {s};", .{vcode});
                    } else {
                        try self.emitLine(3, "return Value.none;", .{});
                    }
                    try self.emitLine(2, "}},", .{});
                    try self.emitLine(2, "{d} => {{", .{current_state});
                    state_terminated = false;
                },
                .return_stmt => |rs| {
                    try self.emitLine(3, "fib.done = true;", .{});
                    if (rs.value) |ve| {
                        const vcode = try self.emitExpr(ve, &local_scope);
                        try self.emitLine(3, "return {s};", .{vcode});
                    } else {
                        try self.emitLine(3, "return Value.none;", .{});
                    }
                    state_terminated = true;
                },
                else => {
                    try self.emitStmt(st, 3, &local_scope, false);
                },
            }
        }

        if (!state_terminated) {
            try self.emitLine(3, "fib.done = true;", .{});
            try self.emitLine(3, "return Value.none;", .{});
        }
        try self.emitLine(2, "}},", .{});
        try self.emitLine(2, "else => {{", .{});
        try self.emitLine(3, "fib.done = true;", .{});
        try self.emitLine(3, "return Value.none;", .{});
        try self.emitLine(2, "}},", .{});
        try self.emitLine(1, "}}", .{});
        try self.emitLine(0, "}}", .{});
        try self.emitLine(0, "", .{});
    }

    fn emitFuncDef(self: *Codegen, fn_def: ast.FuncDef, rec_name: ?[]const u8) !void {
        var param_sig: std.ArrayList(u8) = .empty;
        var forward_args: std.ArrayList(u8) = .empty;
        try param_sig.appendSlice(self.allocator, "rt: *Runtime");
        try forward_args.appendSlice(self.allocator, "rt");

        var local_scope: std.StringArrayHashMapUnmanaged(void) = .empty;
        if (rec_name != null) {
            try param_sig.appendSlice(self.allocator, ", p_self: Value");
            try forward_args.appendSlice(self.allocator, ", p_self");
        }
        for (fn_def.params) |pname| {
            const pdecl = try std.fmt.allocPrint(self.allocator, ", p_{s}: Value", .{pname});
            try param_sig.appendSlice(self.allocator, pdecl);
            const pfwd = try std.fmt.allocPrint(self.allocator, ", p_{s}", .{pname});
            try forward_args.appendSlice(self.allocator, pfwd);
            try local_scope.put(self.allocator, pname, {});
        }

        const full_name = if (rec_name) |rn|
            try std.fmt.allocPrint(self.allocator, "engage_method_{s}_{s}", .{ rn, fn_def.name })
        else
            try std.fmt.allocPrint(self.allocator, "engage_fn_{s}", .{fn_def.name});

        try self.emitLine(0, "fn {s}_impl({s}) anyerror!Value {{", .{ full_name, param_sig.items });
        try self.emitLine(1, "rt.touch();", .{});
        if (rec_name != null) {
            try self.emitLine(1, "var v_self: Value = p_self; _ = &v_self;", .{});
        }
        for (fn_def.params) |pname| {
            try self.emitLine(1, "var v_{s}: Value = p_{s}; _ = &v_{s};", .{ pname, pname, pname });
        }
        for (fn_def.body) |st| {
            try self.emitStmt(st, 1, &local_scope, false);
        }
        if (fn_def.body.len == 0 or fn_def.body[fn_def.body.len - 1] != .return_stmt) {
            try self.emitLine(1, "return Value.none;", .{});
        }
        try self.emitLine(0, "}}", .{});

        try self.emitLine(0, "fn {s}({s}) anyerror!Value {{", .{ full_name, param_sig.items });
        try self.emitLine(1, "return {s}_impl({s}) catch |err| switch (err) {{", .{ full_name, forward_args.items });
        try self.emitLine(2, "error.EngagePropagateError => return rt.propagated_error,", .{});
        try self.emitLine(2, "else => return err,", .{});
        try self.emitLine(1, "}};", .{});
        try self.emitLine(0, "}}", .{});
        try self.emitLine(0, "", .{});
    }

    fn collectTopLevel(self: *Codegen, stmts: []const ast.Stmt) !void {
        for (stmts) |st| {
            switch (st) {
                .var_assign => |va| try self.globals.put(self.allocator, va.name, {}),
                .channel_decl => |cd| try self.globals.put(self.allocator, cd.name, {}),
                .fiber_def => |fd| {
                    try self.globals.put(self.allocator, fd.name, {});
                    try self.fibers.put(self.allocator, fd.name, fd);
                },
                .func_def => |fd| try self.functions.put(self.allocator, fd.name, fd.params.len),
                .record_def => |rd| try self.records.put(self.allocator, rd.name, rd),
                .extern_fn_def => |efd| {
                    const bind_name = efd.alias orelse efd.name;
                    if (!std.mem.endsWith(u8, efd.library, ".zig")) {
                        try self.functions.put(self.allocator, bind_name, efd.params.len);
                    }
                    try self.extern_fns.put(self.allocator, bind_name, efd);
                    if (!self.extern_modules.contains(efd.library)) {
                        try self.extern_modules.put(self.allocator, efd.library, self.extern_modules.count());
                    }
                },
                .from_import_stmt => |fis| {
                    if (parser.isExternalLibraryPath(fis.module_path)) {
                        for (fis.symbols) |sym| {
                            const bind_name = sym.alias orelse sym.name;
                            const params = sym.params orelse &.{};
                            if (!std.mem.endsWith(u8, fis.module_path, ".zig")) {
                                try self.functions.put(self.allocator, bind_name, params.len);
                            }
                            try self.extern_fns.put(self.allocator, bind_name, .{
                                .library = fis.module_path,
                                .name = sym.name,
                                .alias = sym.alias,
                                .params = params,
                                .ret_type = sym.ret_type,
                                .has_explicit_sig = (sym.params != null or sym.ret_type != .auto),
                            });
                            if (!self.extern_modules.contains(fis.module_path)) {
                                try self.extern_modules.put(self.allocator, fis.module_path, self.extern_modules.count());
                            }
                        }
                    }
                },
                .if_stmt => |ifs| {
                    for (ifs.branches) |b| try self.collectTopLevel(b.body);
                    try self.collectTopLevel(ifs.else_body);
                },
                .while_stmt => |ws| try self.collectTopLevel(ws.body),
                .repeat_stmt => |rs| try self.collectTopLevel(rs.body),
                .for_each_stmt => |fs| try self.collectTopLevel(fs.body),
                .task_stmt => |ts| try self.collectTopLevel(ts.body),
                else => {},
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

    fn cConvertExpr(self: *Codegen, pval: []const u8, ffi_type: ast.FfiType) ![]const u8 {
        return switch (ffi_type) {
            .number, .auto => std.fmt.allocPrint(self.allocator, "({s}).asNumber()", .{pval}),
            .int => std.fmt.allocPrint(self.allocator, "@as(i64, @intFromFloat(({s}).asNumber()))", .{pval}),
            .string => std.fmt.allocPrint(self.allocator, "(try dupeZ(rt.allocator, try ({s}).toString(rt.allocator))).ptr", .{pval}),
            .bool_type => std.fmt.allocPrint(self.allocator, "({s}).isTruthy()", .{pval}),
            .pointer => std.fmt.allocPrint(self.allocator, "({s}).asPointer()", .{pval}),
            .void_type => "Value.none",
        };
    }

    fn cConvertResult(self: *Codegen, call_expr: []const u8, ffi_type: ast.FfiType) ![]const u8 {
        return switch (ffi_type) {
            .number, .auto => std.fmt.allocPrint(self.allocator, "Value.fromNumber({s})", .{call_expr}),
            .int => std.fmt.allocPrint(self.allocator, "Value.fromNumber(@floatFromInt({s}))", .{call_expr}),
            .string => std.fmt.allocPrint(self.allocator, "Value.fromString(std.mem.span({s}))", .{call_expr}),
            .bool_type => std.fmt.allocPrint(self.allocator, "Value.fromBool({s})", .{call_expr}),
            .pointer => std.fmt.allocPrint(self.allocator, "Value.fromPointer({s})", .{call_expr}),
            .void_type => std.fmt.allocPrint(self.allocator, "blk: {{ {s}; break :blk Value.none; }}", .{call_expr}),
        };
    }

    pub fn generate(self: *Codegen, prog: ast.Program) ![]const u8 {
        // Pass 0: Collect globals, functions, records, and fibers
        try self.collectTopLevel(prog.statements);

        // Emit embedded runtime
        try self.emitLine(0, "// Generated by Engage Zig Compiler (Engage v3)", .{});
        try self.emitLine(0, "{s}", .{embedded_runtime_src});
        try self.emitLine(0, "", .{});

        // Emit external Zig module imports
        var mod_it = self.extern_modules.iterator();
        while (mod_it.next()) |entry| {
            const mod_path = entry.key_ptr.*;
            if (std.mem.endsWith(u8, mod_path, ".zig")) {
                const fwd_path = try self.allocator.dupe(u8, mod_path);
                for (fwd_path) |*ch| {
                    if (ch.* == '\\') ch.* = '/';
                }
                const zig_imp = if (!std.mem.startsWith(u8, fwd_path, ".") and !std.mem.startsWith(u8, fwd_path, "/"))
                    try std.fmt.allocPrint(self.allocator, "./{s}", .{fwd_path})
                else
                    fwd_path;
                const esc_path = try self.escapeZigString(zig_imp);
                try self.emitLine(0, "const _ext_zig_{d} = @import({s});", .{ entry.value_ptr.*, esc_path });
            }
        }
        try self.emitLine(0, "", .{});

        // Emit external function wrappers
        var ext_it = self.extern_fns.iterator();
        while (ext_it.next()) |entry| {
            const bind_name = entry.key_ptr.*;
            const efd = entry.value_ptr.*;
            if (std.mem.endsWith(u8, efd.library, ".zig")) {
                const mod_id = self.extern_modules.get(efd.library).?;
                try self.emitLine(0, "fn engage_fn_{s}(rt: *Runtime, args: []const Value) anyerror!Value {{", .{bind_name});
                try self.emitLine(1, "return callZigFn(_ext_zig_{d}.{s}, rt, args);", .{ mod_id, efd.name });
                try self.emitLine(0, "}}", .{});
                try self.emitLine(0, "", .{});
            } else {
                // C / C++ extern
                const c_ret = cTypeStr(efd.ret_type);
                var c_params: std.ArrayList(u8) = .empty;
                for (efd.params, 0..) |p, i| {
                    if (i > 0) try c_params.appendSlice(self.allocator, ", ");
                    const pt = cTypeStr(p.ffi_type);
                    const pdecl = try std.fmt.allocPrint(self.allocator, "p_{d}: {s}", .{ i, pt });
                    try c_params.appendSlice(self.allocator, pdecl);
                }
                try self.emitLine(0, "extern \"c\" fn {s}({s}) callconv(.c) {s};", .{ efd.name, c_params.items, c_ret });

                var param_sig: std.ArrayList(u8) = .empty;
                var c_call_args: std.ArrayList(u8) = .empty;
                try param_sig.appendSlice(self.allocator, "rt: *Runtime");
                for (efd.params, 0..) |p, i| {
                    const pdecl = try std.fmt.allocPrint(self.allocator, ", p_{d}: Value", .{i});
                    try param_sig.appendSlice(self.allocator, pdecl);
                    if (i > 0) try c_call_args.appendSlice(self.allocator, ", ");
                    const p_name = try std.fmt.allocPrint(self.allocator, "p_{d}", .{i});
                    const converted = try self.cConvertExpr(p_name, p.ffi_type);
                    try c_call_args.appendSlice(self.allocator, converted);
                }
                const call_expr = try std.fmt.allocPrint(self.allocator, "{s}({s})", .{ efd.name, c_call_args.items });
                const wrapped = try self.cConvertResult(call_expr, efd.ret_type);
                try self.emitLine(0, "fn engage_fn_{s}({s}) anyerror!Value {{", .{ bind_name, param_sig.items });
                try self.emitLine(1, "_ = rt;", .{});
                try self.emitLine(1, "return {s};", .{wrapped});
                try self.emitLine(0, "}}", .{});
                try self.emitLine(0, "", .{});
            }
        }
        try self.emitLine(0, "const PropKV = struct {{ name: []const u8, val: Value }};", .{});
        try self.emitLine(0, "", .{});
        try self.emitLine(0, "fn engage_new_generic(rt: *Runtime, type_name: []const u8, props: []const PropKV) anyerror!Value {{", .{});
        try self.emitLine(1, "const rec = try rt.makeRecord(type_name);", .{});
        try self.emitLine(1, "for (props) |p| try rec.fields.put(rt.allocator, p.name, p.val);", .{});
        try self.emitLine(1, "return .{{ .record = rec }};", .{});
        try self.emitLine(0, "}}", .{});
        try self.emitLine(0, "", .{});
        try self.emitLine(0, "fn engage_channel_send(rt: *Runtime, ch: Value, val: Value) !void {{", .{});
        try self.emitLine(1, "if (ch == .channel) try ch.channel.queue.append(rt.allocator, val);", .{});
        try self.emitLine(0, "}}", .{});
        try self.emitLine(0, "fn engage_channel_receive(ch: Value) Value {{", .{});
        try self.emitLine(1, "if (ch == .channel and ch.channel.queue.items.len > 0) return ch.channel.queue.orderedRemove(0);", .{});
        try self.emitLine(1, "return Value.none;", .{});
        try self.emitLine(0, "}}", .{});
        try self.emitLine(0, "", .{});

        // Emit global variables
        var git = self.globals.iterator();
        while (git.next()) |entry| {
            try self.emitLine(0, "var g_{s}: Value = .none;", .{entry.key_ptr.*});
        }
        try self.emitLine(0, "", .{});

        // Emit Record constructors and methods
        const empty_scope: std.StringArrayHashMapUnmanaged(void) = .empty;
        var rit = self.records.iterator();
        while (rit.next()) |entry| {
            const rd = entry.value_ptr.*;
            const esc_rname = try self.escapeZigString(rd.name);
            try self.emitLine(0, "fn engage_new_{s}(rt: *Runtime, props: []const PropKV) anyerror!Value {{", .{rd.name});
            try self.emitLine(1, "const rec = try rt.makeRecord({s});", .{esc_rname});
            for (rd.properties) |prop| {
                const esc_pname = try self.escapeZigString(prop.name);
                const def_code = if (prop.default_value) |de| try self.emitExpr(de, &empty_scope) else "Value.none";
                try self.emitLine(1, "try rec.fields.put(rt.allocator, {s}, {s});", .{ esc_pname, def_code });
            }
            try self.emitLine(1, "for (props) |p| try rec.fields.put(rt.allocator, p.name, p.val);", .{});
            try self.emitLine(1, "return .{{ .record = rec }};", .{});
            try self.emitLine(0, "}}", .{});
            try self.emitLine(0, "", .{});

            for (rd.methods) |m| {
                try self.emitFuncDef(m, rd.name);
            }
        }

        // Emit engage_get_member and engage_call_method dispatchers
        try self.emitLine(0, "fn engage_get_member(rt: *Runtime, obj: Value, member: []const u8) anyerror!Value {{", .{});
        try self.emitLine(1, "rt.touch();", .{});
        try self.emitLine(1, "if (obj == .record) {{", .{});
        try self.emitLine(2, "if (obj.record.fields.get(member)) |v| return v;", .{});
        var rit2 = self.records.iterator();
        while (rit2.next()) |entry| {
            const rd = entry.value_ptr.*;
            const esc_rname = try self.escapeZigString(rd.name);
            for (rd.methods) |m| {
                if (m.params.len == 0) {
                    const esc_mname = try self.escapeZigString(m.name);
                    try self.emitLine(
                        2,
                        "if (std.mem.eql(u8, obj.record.type_name, {s}) and std.mem.eql(u8, member, {s})) return engage_method_{s}_{s}(rt, obj);",
                        .{ esc_rname, esc_mname, rd.name, m.name },
                    );
                }
            }
        }
        try self.emitLine(1, "}}", .{});
        try self.emitLine(1, "return Runtime.memberGet(obj, member);", .{});
        try self.emitLine(0, "}}", .{});
        try self.emitLine(0, "", .{});

        try self.emitLine(0, "fn engage_call_method(rt: *Runtime, obj: Value, member: []const u8, args: []const Value) anyerror!Value {{", .{});
        try self.emitLine(1, "if (obj == .record) {{", .{});
        var rit3 = self.records.iterator();
        while (rit3.next()) |entry| {
            const rd = entry.value_ptr.*;
            const esc_rname = try self.escapeZigString(rd.name);
            for (rd.methods) |m| {
                const esc_mname = try self.escapeZigString(m.name);
                var margs: std.ArrayList(u8) = .empty;
                try margs.appendSlice(self.allocator, "rt, obj");
                for (0..m.params.len) |pi| {
                    const arg_extract = try std.fmt.allocPrint(
                        self.allocator,
                        ", if (args.len > {d}) args[{d}] else Value.none",
                        .{ pi, pi },
                    );
                    try margs.appendSlice(self.allocator, arg_extract);
                }
                try self.emitLine(
                    2,
                    "if (std.mem.eql(u8, obj.record.type_name, {s}) and std.mem.eql(u8, member, {s})) return engage_method_{s}_{s}({s});",
                    .{ esc_rname, esc_mname, rd.name, m.name, margs.items },
                );
            }
        }
        try self.emitLine(1, "}}", .{});
        try self.emitLine(1, "if (Runtime.isStdlibFn(member)) {{", .{});
        try self.emitLine(2, "if (obj == .vector or obj == .table) {{", .{});
        try self.emitLine(3, "var full: std.ArrayList(Value) = .empty;", .{});
        try self.emitLine(3, "try full.append(rt.allocator, obj);", .{});
        try self.emitLine(3, "try full.appendSlice(rt.allocator, args);", .{});
        try self.emitLine(3, "return rt.callStdlib(member, full.items);", .{});
        try self.emitLine(2, "}}", .{});
        try self.emitLine(2, "return rt.callStdlib(member, args);", .{});
        try self.emitLine(1, "}}", .{});
        try self.emitLine(1, "return engage_get_member(rt, obj, member);", .{});
        try self.emitLine(0, "}}", .{});
        try self.emitLine(0, "", .{});

        // Emit top-level functions
        for (prog.statements) |st| {
            if (st == .func_def) {
                try self.emitFuncDef(st.func_def, null);
            }
        }

        // Emit fibers
        var fit = self.fibers.iterator();
        while (fit.next()) |entry| {
            try self.emitFiberDef(entry.value_ptr.*);
        }

        // Emit top-level execution and main
        try self.emitLine(0, "fn engage_run_top_level(rt: *Runtime) anyerror!void {{", .{});
        try self.emitLine(1, "rt.touch();", .{});
        var main_scope: std.StringArrayHashMapUnmanaged(void) = .empty;
        for (prog.statements) |st| {
            if (st != .func_def and st != .record_def and st != .extern_fn_def) {
                try self.emitStmt(st, 1, &main_scope, true);
            }
        }
        try self.emitLine(0, "}}", .{});
        try self.emitLine(0, "", .{});
        try self.emitLine(0, "pub fn main(init: std.process.Init) !void {{", .{});
        try self.emitLine(1, "const alloc = init.arena.allocator();", .{});
        try self.emitLine(1, "var rt = Runtime.init(alloc, init.io);", .{});
        try self.emitLine(1, "const raw_args = try init.minimal.args.toSlice(alloc);", .{});
        try self.emitLine(1, "if (raw_args.len > 1) {{", .{});
        try self.emitLine(2, "for (raw_args[1..]) |a| {{", .{});
        try self.emitLine(3, "try rt.cli_args.append(alloc, Value.fromString(a));", .{});
        try self.emitLine(2, "}}", .{});
        try self.emitLine(1, "}}", .{});
        try self.emitLine(1, "engage_run_top_level(&rt) catch |err| switch (err) {{", .{});
        try self.emitLine(2, "error.EngagePropagateError => {{}},", .{});
        try self.emitLine(2, "else => return err,", .{});
        try self.emitLine(1, "}};", .{});
        try self.emitLine(0, "}}", .{});

        var out: std.ArrayList(u8) = .empty;
        for (self.lines.items) |line| {
            try out.appendSlice(self.allocator, line);
            try out.append(self.allocator, '\n');
        }
        return out.toOwnedSlice(self.allocator);
    }
};

pub fn generateZigSource(allocator: std.mem.Allocator, prog: ast.Program) ![]const u8 {
    var cg = Codegen.init(allocator);
    return cg.generate(prog);
}
