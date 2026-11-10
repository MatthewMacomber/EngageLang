const std = @import("std");
const lexer = @import("lexer.zig");
const ast = @import("ast.zig");

const Token = lexer.Token;
const TokenType = lexer.TokenType;
const Expr = ast.Expr;
const Stmt = ast.Stmt;

pub const ParseError = error{
    UnexpectedToken,
    OutOfMemory,
};

pub const Parser = struct {
    allocator: std.mem.Allocator,
    tokens: []const Token,
    pos: usize = 0,

    pub fn init(allocator: std.mem.Allocator, tokens: []const Token) Parser {
        return .{
            .allocator = allocator,
            .tokens = tokens,
            .pos = 0,
        };
    }

    fn cur(self: *const Parser) Token {
        if (self.pos < self.tokens.len) return self.tokens[self.pos];
        return self.tokens[self.tokens.len - 1];
    }

    fn peek(self: *const Parser, offset: usize) Token {
        const idx = self.pos + offset;
        if (idx < self.tokens.len) return self.tokens[idx];
        return self.tokens[self.tokens.len - 1];
    }

    fn advance(self: *Parser) Token {
        const t = self.cur();
        if (self.pos + 1 < self.tokens.len) self.pos += 1;
        return t;
    }

    fn skipEols(self: *Parser) void {
        while (self.cur().kind == .eol) {
            _ = self.advance();
        }
    }

    fn consumePeriod(self: *Parser) void {
        self.skipEols();
        const t = self.cur();
        if (t.kind == .punctuation and std.mem.eql(u8, t.lexeme, ".")) {
            _ = self.advance();
        }
    }

    fn allocExpr(self: *Parser, e: Expr) !*const Expr {
        const ptr = try self.allocator.create(Expr);
        ptr.* = e;
        return ptr;
    }

    fn isNameToken(t: Token) bool {
        if (t.kind == .identifier) return true;
        if (t.kind == .keyword or t.kind == .operator) {
            const disallowed = [_][]const u8{
                "if",   "then",      "otherwise", "end",    "let",    "be",
                "to",   "with",      "return",    "while",  "define", "new",
                "set",  "repeat",    "for",       "import", "export", "extern",
                "switch", "on",      "case",      "default",
            };
            for (disallowed) |d| {
                if (std.mem.eql(u8, t.lexeme, d)) return false;
            }
            return true;
        }
        return false;
    }

    fn parseFfiType(t: Token) ast.FfiType {
        if (std.ascii.eqlIgnoreCase(t.lexeme, "number") or std.ascii.eqlIgnoreCase(t.lexeme, "float") or std.ascii.eqlIgnoreCase(t.lexeme, "double") or std.ascii.eqlIgnoreCase(t.lexeme, "f64") or std.ascii.eqlIgnoreCase(t.lexeme, "f32")) return .number;
        if (std.ascii.eqlIgnoreCase(t.lexeme, "int") or std.ascii.eqlIgnoreCase(t.lexeme, "integer") or std.ascii.eqlIgnoreCase(t.lexeme, "i64") or std.ascii.eqlIgnoreCase(t.lexeme, "i32") or std.ascii.eqlIgnoreCase(t.lexeme, "usize")) return .int;
        if (std.ascii.eqlIgnoreCase(t.lexeme, "string") or std.ascii.eqlIgnoreCase(t.lexeme, "str") or std.ascii.eqlIgnoreCase(t.lexeme, "cstring")) return .string;
        if (std.ascii.eqlIgnoreCase(t.lexeme, "bool") or std.ascii.eqlIgnoreCase(t.lexeme, "boolean")) return .bool_type;
        if (std.ascii.eqlIgnoreCase(t.lexeme, "pointer") or std.ascii.eqlIgnoreCase(t.lexeme, "ptr") or std.ascii.eqlIgnoreCase(t.lexeme, "handle")) return .pointer;
        if (std.ascii.eqlIgnoreCase(t.lexeme, "void") or std.ascii.eqlIgnoreCase(t.lexeme, "none")) return .void_type;
        return .auto;
    }

    fn isValidExprToken(t: Token) bool {
        if (t.kind == .eol or t.kind == .eof) return false;
        if (t.kind == .keyword) {
            const stops = [_][]const u8{
                "then",   "otherwise", "end",    "let",      "set",
                "if",     "while",     "return", "to",       "through",
                "in",     "as",        "repeat", "for",      "break",
                "continue", "case",    "default", "returns", "extern",
            };
            for (stops) |s| {
                if (std.mem.eql(u8, t.lexeme, s)) return false;
            }
        }
        return true;
    }

    fn tokenPrec(self: *const Parser, t: Token) i32 {
        if (t.kind == .eol) return -1;
        if (t.kind == .keyword and std.mem.eql(u8, t.lexeme, "with")) return 8;
        if (t.kind == .punctuation and std.mem.eql(u8, t.lexeme, ".")) {
            if (isNameToken(self.peek(1))) return 9;
            return 0;
        }
        if (t.kind == .punctuation and std.mem.eql(u8, t.lexeme, "[")) return 10;
        if (t.kind != .operator) return 0;

        const v = t.lexeme;
        if (std.mem.eql(u8, v, "or") or std.mem.eql(u8, v, "or return error")) return 1;
        if (std.mem.eql(u8, v, "and")) return 2;
        if (std.mem.eql(u8, v, "is") or std.mem.eql(u8, v, "is equal to") or std.mem.eql(u8, v, "==") or
            std.mem.eql(u8, v, "is not") or std.mem.eql(u8, v, "is not equal to") or std.mem.eql(u8, v, "!=") or
            std.mem.eql(u8, v, "is greater than") or std.mem.eql(u8, v, ">") or
            std.mem.eql(u8, v, "is less than") or std.mem.eql(u8, v, "<") or
            std.mem.eql(u8, v, "is greater than or equal to") or std.mem.eql(u8, v, ">=") or
            std.mem.eql(u8, v, "is less than or equal to") or std.mem.eql(u8, v, "<=") or
            std.mem.eql(u8, v, "is an") or std.mem.eql(u8, v, "is a"))
        {
            return 3;
        }
        if (std.mem.eql(u8, v, "concatenated with"))
        {
            return 4;
        }
        if (std.mem.eql(u8, v, "plus") or std.mem.eql(u8, v, "+") or
            std.mem.eql(u8, v, "minus") or std.mem.eql(u8, v, "-"))
        {
            return 5;
        }
        if (std.mem.eql(u8, v, "times") or std.mem.eql(u8, v, "*") or
            std.mem.eql(u8, v, "divided by") or std.mem.eql(u8, v, "/") or
            std.mem.eql(u8, v, "modulo") or std.mem.eql(u8, v, "%"))
        {
            return 6;
        }
        return 0;
    }

    pub fn parseAtom(self: *Parser) ParseError!*const Expr {
        const tok = self.cur();

        if (tok.kind == .number) {
            _ = self.advance();
            const val = std.fmt.parseFloat(f64, tok.lexeme) catch 0.0;
            return self.allocExpr(.{ .number = val });
        }

        if (tok.kind == .string) {
            _ = self.advance();
            return self.allocExpr(.{ .string = tok.lexeme });
        }

        if (tok.kind == .keyword and std.mem.eql(u8, tok.lexeme, "Vector")) {
            _ = self.advance();
            return self.allocExpr(.vector_lit);
        }

        if (tok.kind == .keyword and std.mem.eql(u8, tok.lexeme, "Table")) {
            _ = self.advance();
            return self.allocExpr(.table_lit);
        }

        if (tok.kind == .keyword and std.mem.eql(u8, tok.lexeme, "self")) {
            _ = self.advance();
            return self.allocExpr(.self_expr);
        }

        if (tok.kind == .keyword and std.mem.eql(u8, tok.lexeme, "receive")) {
            _ = self.advance();
            if (std.mem.eql(u8, self.cur().lexeme, "from")) {
                _ = self.advance();
            }
            const ch_expr = try self.parseExpr(0, false);
            return self.allocExpr(.{ .receive_expr = .{ .channel = ch_expr } });
        }

        if (tok.kind == .keyword and (std.ascii.eqlIgnoreCase(tok.lexeme, "ok") or std.ascii.eqlIgnoreCase(tok.lexeme, "error"))) {
            _ = self.advance();
            const is_ok = std.ascii.eqlIgnoreCase(tok.lexeme, "ok");
            var val_expr: ?*const Expr = null;
            if (std.mem.eql(u8, self.cur().lexeme, "with")) {
                _ = self.advance();
                val_expr = try self.parseExpr(0, false);
            }
            return self.allocExpr(.{ .result_lit = .{ .is_ok = is_ok, .value = val_expr } });
        }

        if (tok.kind == .keyword and std.mem.eql(u8, tok.lexeme, "new")) {
            _ = self.advance();
            const name_tok = self.advance();
            if (std.mem.eql(u8, name_tok.lexeme, "Vector")) return self.allocExpr(.vector_lit);
            if (std.mem.eql(u8, name_tok.lexeme, "Table")) return self.allocExpr(.table_lit);

            var props: std.ArrayList(ast.PropInit) = .empty;
            if (std.mem.eql(u8, self.cur().lexeme, "with")) {
                _ = self.advance();
                while (self.cur().kind != .eof and !std.mem.eql(u8, self.cur().lexeme, ".")) {
                    const pname_tok = self.advance();
                    if (self.cur().kind == .punctuation and std.mem.eql(u8, self.cur().lexeme, ":")) {
                        _ = self.advance();
                    }
                    const pval = try self.parseExpr(0, true);
                    try props.append(self.allocator, .{
                        .name = pname_tok.lexeme,
                        .value = pval,
                    });
                    if (self.cur().kind == .punctuation and std.mem.eql(u8, self.cur().lexeme, ",")) {
                        _ = self.advance();
                    } else {
                        break;
                    }
                }
            }
            return self.allocExpr(.{
                .new_instance = .{
                    .record_name = name_tok.lexeme,
                    .props = try props.toOwnedSlice(self.allocator),
                },
            });
        }

        if (tok.kind == .punctuation and std.mem.eql(u8, tok.lexeme, "(")) {
            _ = self.advance();
            const inner = try self.parseExpr(0, false);
            if (self.cur().kind == .punctuation and std.mem.eql(u8, self.cur().lexeme, ")")) {
                _ = self.advance();
            }
            return inner;
        }

        if (tok.kind == .operator and (std.mem.eql(u8, tok.lexeme, "not") or
            std.mem.eql(u8, tok.lexeme, "-") or
            std.mem.eql(u8, tok.lexeme, "minus") or
            std.mem.eql(u8, tok.lexeme, "call") or
            std.mem.eql(u8, tok.lexeme, "the ok value of") or
            std.mem.eql(u8, tok.lexeme, "the error message of")))
        {
            _ = self.advance();
            const operand = try self.parseExpr(7, false);
            return self.allocExpr(.{
                .unary_op = .{
                    .op = tok.lexeme,
                    .operand = operand,
                },
            });
        }

        _ = self.advance();
        if (std.mem.eql(u8, tok.lexeme, "None") or std.mem.eql(u8, tok.lexeme, "none")) {
            return self.allocExpr(.none_expr);
        }
        if (std.mem.eql(u8, tok.lexeme, "true")) {
            return self.allocExpr(.{ .number = 1.0 });
        }
        if (std.mem.eql(u8, tok.lexeme, "false")) {
            return self.allocExpr(.{ .number = 0.0 });
        }
        return self.allocExpr(.{ .ident = tok.lexeme });
    }

    fn parseFuncCall(self: *Parser, callee: *const Expr, caller_min_prec: i32) ParseError!*const Expr {
        _ = self.advance(); // consume 'with'
        var args: std.ArrayList(*const Expr) = .empty;
        const c = self.cur();
        const is_punct_stop = (c.kind == .punctuation and (std.mem.eql(u8, c.lexeme, ".") or std.mem.eql(u8, c.lexeme, ":")));
        const arg_prec = @max(2, caller_min_prec);
        if (isValidExprToken(c) and !is_punct_stop) {
            while (true) {
                const arg_expr = try self.parseExpr(arg_prec, true);
                try args.append(self.allocator, arg_expr);
                const nxt = self.cur();
                if (nxt.kind == .eol) break;
                if (nxt.kind == .punctuation and std.mem.eql(u8, nxt.lexeme, ",")) {
                    _ = self.advance();
                    if (!isValidExprToken(self.cur())) break;
                } else {
                    break;
                }
            }
        }
        return self.allocExpr(.{
            .func_call = .{
                .callee = callee,
                .args = try args.toOwnedSlice(self.allocator),
            },
        });
    }

    pub fn parseExpr(self: *Parser, min_prec: i32, in_args: bool) ParseError!*const Expr {
        var left = try self.parseAtom();

        while (true) {
            var c = self.cur();
            if (c.kind == .eol) {
                const saved_pos = self.pos;
                self.skipEols();
                const after_eol = self.cur();
                const next_prec = self.tokenPrec(after_eol);
                if (after_eol.kind != .eof and isValidExprToken(after_eol) and min_prec < next_prec) {
                    c = after_eol;
                } else {
                    self.pos = saved_pos;
                    break;
                }
            }

            c = self.cur();
            const prec = self.tokenPrec(c);
            if (c.kind == .eof or !isValidExprToken(c) or min_prec >= prec) break;
            if (c.kind == .punctuation and (std.mem.eql(u8, c.lexeme, ":") or
                std.mem.eql(u8, c.lexeme, ")") or
                std.mem.eql(u8, c.lexeme, "]") or
                std.mem.eql(u8, c.lexeme, ",")))
            {
                break;
            }

            if (c.kind == .punctuation and std.mem.eql(u8, c.lexeme, ".")) {
                if (isNameToken(self.peek(1))) {
                    _ = self.advance(); // consume '.'
                    const m_tok = self.advance();
                    left = try self.allocExpr(.{
                        .member_access = .{
                            .object = left,
                            .member = m_tok.lexeme,
                        },
                    });
                    continue;
                } else {
                    break;
                }
            }

            if (c.kind == .punctuation and std.mem.eql(u8, c.lexeme, "[")) {
                _ = self.advance(); // consume '['
                const idx_expr = try self.parseExpr(0, false);
                if (self.cur().kind == .punctuation and std.mem.eql(u8, self.cur().lexeme, "]")) {
                    _ = self.advance();
                }
                left = try self.allocExpr(.{
                    .index_access = .{
                        .object = left,
                        .index = idx_expr,
                    },
                });
                continue;
            }

            if (c.kind == .keyword and std.mem.eql(u8, c.lexeme, "with")) {
                left = try self.parseFuncCall(left, min_prec);
                continue;
            }

            if (c.kind == .operator and std.mem.eql(u8, c.lexeme, "or return error")) {
                _ = self.advance();
                left = try self.allocExpr(.{
                    .bin_op = .{
                        .op = "or return error",
                        .left = left,
                        .right = null,
                    },
                });
                continue;
            }

            const op_val = c.lexeme;
            const op_prec = self.tokenPrec(c);
            _ = self.advance();
            self.skipEols();

            if (std.mem.eql(u8, op_val, "is an") or std.mem.eql(u8, op_val, "is a")) {
                const rtok = self.cur();
                if (std.ascii.eqlIgnoreCase(rtok.lexeme, "error") or std.ascii.eqlIgnoreCase(rtok.lexeme, "ok")) {
                    _ = self.advance();
                    const combined_op = if (std.ascii.eqlIgnoreCase(rtok.lexeme, "error")) "is an Error" else "is an Ok";
                    left = try self.allocExpr(.{
                        .bin_op = .{
                            .op = combined_op,
                            .left = left,
                            .right = null,
                        },
                    });
                    continue;
                }
            }

            const right = try self.parseExpr(op_prec, in_args);
            left = try self.allocExpr(.{
                .bin_op = .{
                    .op = op_val,
                    .left = left,
                    .right = right,
                },
            });
        }

        return left;
    }

    fn parseStmtListUntil(self: *Parser, stops: []const []const u8) ParseError![]const Stmt {
        var stmts: std.ArrayList(Stmt) = .empty;
        self.skipEols();
        while (self.cur().kind != .eof) {
            const t = self.cur();
            if (t.kind == .keyword) {
                for (stops) |s| {
                    if (std.mem.eql(u8, t.lexeme, s)) return stmts.toOwnedSlice(self.allocator);
                }
            }
            if (try self.parseStatement()) |st| {
                try stmts.append(self.allocator, st);
            }
            self.skipEols();
        }
        return stmts.toOwnedSlice(self.allocator);
    }

    fn parseStmtList(self: *Parser, stop_a: []const u8, stop_b: []const u8) ParseError![]const Stmt {
        var stmts: std.ArrayList(Stmt) = .empty;
        self.skipEols();
        while (self.cur().kind != .eof) {
            const t = self.cur();
            if (t.kind == .keyword and (std.mem.eql(u8, t.lexeme, stop_a) or std.mem.eql(u8, t.lexeme, stop_b))) {
                break;
            }
            if (try self.parseStatement()) |st| {
                try stmts.append(self.allocator, st);
            }
            self.skipEols();
        }
        return stmts.toOwnedSlice(self.allocator);
    }

    fn parseSwitchStmt(self: *Parser) ParseError!Stmt {
        _ = self.advance(); // consume 'switch'
        if (std.mem.eql(u8, self.cur().lexeme, "on")) _ = self.advance();
        const target_expr = try self.parseExpr(0, false);
        if (std.mem.eql(u8, self.cur().lexeme, ":") or std.mem.eql(u8, self.cur().lexeme, "then")) {
            _ = self.advance();
        }
        self.skipEols();

        var branches: std.ArrayList(ast.IfBranch) = .empty;
        var else_body: []const Stmt = &.{};

        while (self.cur().kind == .keyword and std.mem.eql(u8, self.cur().lexeme, "case")) {
            _ = self.advance(); // consume 'case'
            const case_val = try self.parseExpr(0, false);
            if (std.mem.eql(u8, self.cur().lexeme, ":") or std.mem.eql(u8, self.cur().lexeme, "then")) {
                _ = self.advance();
            }
            self.skipEols();
            const body = try self.parseStmtListUntil(&.{ "case", "default", "otherwise", "end" });
            const cond = try self.allocExpr(.{
                .bin_op = .{
                    .op = "is equal to",
                    .left = target_expr,
                    .right = case_val,
                },
            });
            try branches.append(self.allocator, .{ .condition = cond, .body = body });
        }

        if (self.cur().kind == .keyword and (std.mem.eql(u8, self.cur().lexeme, "default") or std.mem.eql(u8, self.cur().lexeme, "otherwise"))) {
            _ = self.advance(); // consume 'default' / 'otherwise'
            if (std.mem.eql(u8, self.cur().lexeme, ":")) _ = self.advance();
            self.skipEols();
            else_body = try self.parseStmtList("end", "end");
        }

        if (std.mem.eql(u8, self.cur().lexeme, "end")) {
            _ = self.advance();
        }

        return .{
            .if_stmt = .{
                .branches = try branches.toOwnedSlice(self.allocator),
                .else_body = else_body,
            },
        };
    }

    fn parseIfStmt(self: *Parser) ParseError!Stmt {
        _ = self.advance(); // consume 'if'
        var branches: std.ArrayList(ast.IfBranch) = .empty;
        var else_body: []const Stmt = &.{};

        const cond = try self.parseExpr(0, false);
        self.skipEols();
        if (std.mem.eql(u8, self.cur().lexeme, "then") or std.mem.eql(u8, self.cur().lexeme, ":")) {
            _ = self.advance();
            if (std.mem.eql(u8, self.cur().lexeme, ":")) _ = self.advance();
        }
        self.skipEols();
        const first_body = try self.parseStmtList("otherwise", "end");
        try branches.append(self.allocator, .{ .condition = cond, .body = first_body });

        while (self.cur().kind == .keyword and std.mem.eql(u8, self.cur().lexeme, "otherwise")) {
            _ = self.advance();
            if (self.cur().kind == .keyword and std.mem.eql(u8, self.cur().lexeme, "if")) {
                _ = self.advance();
                const econd = try self.parseExpr(0, false);
                self.skipEols();
                if (std.mem.eql(u8, self.cur().lexeme, "then") or std.mem.eql(u8, self.cur().lexeme, ":")) {
                    _ = self.advance();
                    if (std.mem.eql(u8, self.cur().lexeme, ":")) _ = self.advance();
                }
                self.skipEols();
                const ebody = try self.parseStmtList("otherwise", "end");
                try branches.append(self.allocator, .{ .condition = econd, .body = ebody });
            } else {
                if (std.mem.eql(u8, self.cur().lexeme, ":")) _ = self.advance();
                self.skipEols();
                else_body = try self.parseStmtList("end", "end");
                break;
            }
        }

        if (std.mem.eql(u8, self.cur().lexeme, "end")) {
            _ = self.advance();
        }

        return .{
            .if_stmt = .{
                .branches = try branches.toOwnedSlice(self.allocator),
                .else_body = else_body,
            },
        };
    }

    fn parseWhileStmt(self: *Parser) ParseError!Stmt {
        _ = self.advance(); // consume 'while'
        const cond = try self.parseExpr(0, false);
        if (std.mem.eql(u8, self.cur().lexeme, ":") or std.mem.eql(u8, self.cur().lexeme, "then")) {
            _ = self.advance();
        }
        self.skipEols();
        const body = try self.parseStmtList("end", "end");
        if (std.mem.eql(u8, self.cur().lexeme, "end")) _ = self.advance();
        return .{
            .while_stmt = .{
                .condition = cond,
                .body = body,
            },
        };
    }

    fn parseRepeatStmt(self: *Parser) ParseError!Stmt {
        _ = self.advance(); // consume 'repeat'
        // Parse count expression at precedence 6 so 'times' is left as the loop keyword
        const count_expr = try self.parseExpr(6, false);
        if (std.mem.eql(u8, self.cur().lexeme, "times")) {
            _ = self.advance();
        }
        if (std.mem.eql(u8, self.cur().lexeme, ":")) {
            _ = self.advance();
        }
        self.skipEols();
        const body = try self.parseStmtList("end", "end");
        if (std.mem.eql(u8, self.cur().lexeme, "end")) _ = self.advance();
        return .{
            .repeat_stmt = .{
                .count = count_expr,
                .body = body,
            },
        };
    }

    fn parseForEachStmt(self: *Parser) ParseError!Stmt {
        _ = self.advance(); // consume 'for'
        if (std.mem.eql(u8, self.cur().lexeme, "each")) _ = self.advance();
        const item_tok = self.advance();
        if (std.mem.eql(u8, self.cur().lexeme, "in")) _ = self.advance();
        const iterable = try self.parseExpr(0, false);
        if (std.mem.eql(u8, self.cur().lexeme, ":")) _ = self.advance();
        self.skipEols();
        const body = try self.parseStmtList("end", "end");
        if (std.mem.eql(u8, self.cur().lexeme, "end")) _ = self.advance();
        return .{
            .for_each_stmt = .{
                .item_name = item_tok.lexeme,
                .iterable = iterable,
                .body = body,
            },
        };
    }

    fn parseDefineBody(self: *Parser) ParseError!Stmt {
        if (std.mem.eql(u8, self.cur().lexeme, "a")) _ = self.advance();
        if (std.mem.eql(u8, self.cur().lexeme, "fiber")) {
            _ = self.advance();
            if (std.mem.eql(u8, self.cur().lexeme, "named")) _ = self.advance();
            const fname_tok = self.advance();
            if (std.mem.eql(u8, self.cur().lexeme, ":")) _ = self.advance();
            self.skipEols();
            const body = try self.parseStmtList("end", "end");
            if (std.mem.eql(u8, self.cur().lexeme, "end")) _ = self.advance();
            return .{
                .fiber_def = .{
                    .name = fname_tok.lexeme,
                    .body = body,
                },
            };
        }

        if (std.mem.eql(u8, self.cur().lexeme, "record")) _ = self.advance();
        if (std.mem.eql(u8, self.cur().lexeme, "named")) _ = self.advance();
        const rname_tok = self.advance();
        if (std.mem.eql(u8, self.cur().lexeme, ":")) _ = self.advance();
        self.skipEols();

        var props: std.ArrayList(ast.PropertyDef) = .empty;
        var methods: std.ArrayList(ast.FuncDef) = .empty;

        while (self.cur().kind != .eof and !std.mem.eql(u8, self.cur().lexeme, "end")) {
            self.skipEols();
            const mtok = self.cur();
            if (mtok.kind == .eof or std.mem.eql(u8, mtok.lexeme, "end")) break;

            if (std.mem.eql(u8, mtok.lexeme, "property") or std.mem.eql(u8, mtok.lexeme, "let")) {
                _ = self.advance();
                const pname_tok = self.advance();
                var pval: ?*const Expr = null;
                if (std.mem.eql(u8, self.cur().lexeme, "with") or std.mem.eql(u8, self.cur().lexeme, "be")) {
                    _ = self.advance();
                    if (!std.mem.eql(u8, self.cur().lexeme, ".") and self.cur().kind != .eol) {
                        pval = try self.parseExpr(0, false);
                    }
                }
                self.consumePeriod();
                try props.append(self.allocator, .{
                    .name = pname_tok.lexeme,
                    .default_value = pval,
                });
            } else if (std.mem.eql(u8, mtok.lexeme, "to")) {
                const st = try self.parseFuncOrRecord();
                if (st == .func_def) {
                    try methods.append(self.allocator, st.func_def);
                }
            } else {
                _ = try self.parseStatement();
            }
        }

        if (std.mem.eql(u8, self.cur().lexeme, "end")) _ = self.advance();
        return .{
            .record_def = .{
                .name = rname_tok.lexeme,
                .properties = try props.toOwnedSlice(self.allocator),
                .methods = try methods.toOwnedSlice(self.allocator),
            },
        };
    }

    fn parseFuncOrRecord(self: *Parser) ParseError!Stmt {
        _ = self.advance(); // consume 'to'
        if (std.mem.eql(u8, self.cur().lexeme, "export")) _ = self.advance();
        if (std.mem.eql(u8, self.cur().lexeme, "define")) {
            _ = self.advance();
            return self.parseDefineBody();
        }

        const fname_tok = self.advance();
        var params: std.ArrayList([]const u8) = .empty;
        if (std.mem.eql(u8, self.cur().lexeme, "with")) {
            _ = self.advance();
            while (isNameToken(self.cur())) {
                try params.append(self.allocator, self.advance().lexeme);
                if (std.mem.eql(u8, self.cur().lexeme, ",")) {
                    _ = self.advance();
                } else {
                    break;
                }
            }
        }
        if (std.mem.eql(u8, self.cur().lexeme, ":")) _ = self.advance();
        self.skipEols();
        const body = try self.parseStmtList("end", "end");
        if (std.mem.eql(u8, self.cur().lexeme, "end")) _ = self.advance();

        return .{
            .func_def = .{
                .name = fname_tok.lexeme,
                .params = try params.toOwnedSlice(self.allocator),
                .body = body,
            },
        };
    }

    pub fn parseStatement(self: *Parser) ParseError!?Stmt {
        self.skipEols();
        var tok = self.cur();
        if (tok.kind == .eof) return null;

        if (tok.kind == .keyword) {
            if (std.mem.eql(u8, tok.lexeme, "export")) {
                _ = self.advance();
                tok = self.cur();
            }

            if (std.mem.eql(u8, tok.lexeme, "let")) {
                _ = self.advance();
                const name_tok = self.advance();
                if (std.mem.eql(u8, self.cur().lexeme, "be")) _ = self.advance();
                const val_expr = try self.parseExpr(0, false);
                self.consumePeriod();
                return .{
                    .var_assign = .{
                        .name = name_tok.lexeme,
                        .value = val_expr,
                    },
                };
            }

            if (std.mem.eql(u8, tok.lexeme, "create")) {
                _ = self.advance();
                if (std.mem.eql(u8, self.cur().lexeme, "a")) _ = self.advance();
                if (std.mem.eql(u8, self.cur().lexeme, "channel")) {
                    _ = self.advance();
                    if (std.mem.eql(u8, self.cur().lexeme, "named")) _ = self.advance();
                    const ch_name = self.advance().lexeme;
                    self.consumePeriod();
                    return .{ .channel_decl = .{ .name = ch_name } };
                }
                const name_tok = self.advance();
                if (std.mem.eql(u8, self.cur().lexeme, "with")) _ = self.advance();
                if (std.mem.eql(u8, self.cur().lexeme, "the")) _ = self.advance();
                if (std.mem.eql(u8, self.cur().lexeme, "value")) _ = self.advance();
                const val_expr = try self.parseExpr(0, false);
                self.consumePeriod();
                return .{
                    .var_assign = .{
                        .name = name_tok.lexeme,
                        .value = val_expr,
                    },
                };
            }

            if (std.mem.eql(u8, tok.lexeme, "set")) {
                _ = self.advance();
                const target_expr = try self.parseExpr(0, false);
                if (std.mem.eql(u8, self.cur().lexeme, "to")) _ = self.advance();
                const val_expr = try self.parseExpr(0, false);
                self.consumePeriod();
                if (target_expr.* == .index_access) {
                    return .{
                        .index_assign = .{
                            .object = target_expr.index_access.object,
                            .index = target_expr.index_access.index,
                            .value = val_expr,
                        },
                    };
                }
                return .{
                    .set_stmt = .{
                        .target = target_expr,
                        .value = val_expr,
                    },
                };
            }

            if (std.mem.eql(u8, tok.lexeme, "to")) {
                return try self.parseFuncOrRecord();
            }

            if (std.mem.eql(u8, tok.lexeme, "define")) {
                _ = self.advance();
                return try self.parseDefineBody();
            }

            if (std.mem.eql(u8, tok.lexeme, "if")) {
                return try self.parseIfStmt();
            }

            if (std.mem.eql(u8, tok.lexeme, "switch")) {
                return try self.parseSwitchStmt();
            }

            if (std.mem.eql(u8, tok.lexeme, "while")) {
                return try self.parseWhileStmt();
            }

            if (std.mem.eql(u8, tok.lexeme, "repeat")) {
                return try self.parseRepeatStmt();
            }

            if (std.mem.eql(u8, tok.lexeme, "for")) {
                return try self.parseForEachStmt();
            }

            if (std.mem.eql(u8, tok.lexeme, "run")) {
                _ = self.advance();
                if (std.mem.eql(u8, self.cur().lexeme, "concurrently")) _ = self.advance();
                if (std.mem.eql(u8, self.cur().lexeme, ":")) _ = self.advance();
                self.skipEols();
                const body = try self.parseStmtList("end", "end");
                if (std.mem.eql(u8, self.cur().lexeme, "end")) _ = self.advance();
                return .{ .task_stmt = .{ .body = body } };
            }

            if (std.mem.eql(u8, tok.lexeme, "send")) {
                _ = self.advance();
                const val_expr = try self.parseExpr(0, false);
                if (std.mem.eql(u8, self.cur().lexeme, "through")) _ = self.advance();
                const ch_expr = try self.parseExpr(0, false);
                self.consumePeriod();
                return .{
                    .send_stmt = .{
                        .value = val_expr,
                        .channel = ch_expr,
                    },
                };
            }

            if (std.mem.eql(u8, tok.lexeme, "yield")) {
                _ = self.advance();
                var val_expr: ?*const Expr = null;
                if (std.mem.eql(u8, self.cur().lexeme, "with")) _ = self.advance();
                if (!std.mem.eql(u8, self.cur().lexeme, ".") and self.cur().kind != .eol) {
                    val_expr = try self.parseExpr(0, false);
                }
                self.consumePeriod();
                return .{ .yield_stmt = .{ .value = val_expr } };
            }

            if (std.mem.eql(u8, tok.lexeme, "return")) {
                _ = self.advance();
                if (std.mem.eql(u8, self.cur().lexeme, ".") or self.cur().kind == .eol) {
                    self.consumePeriod();
                    return .{ .return_stmt = .{ .value = null } };
                }
                const val_expr = try self.parseExpr(0, false);
                self.consumePeriod();
                return .{ .return_stmt = .{ .value = val_expr } };
            }

            if (std.mem.eql(u8, tok.lexeme, "break")) {
                _ = self.advance();
                self.consumePeriod();
                return .break_stmt;
            }

            if (std.mem.eql(u8, tok.lexeme, "continue")) {
                _ = self.advance();
                self.consumePeriod();
                return .continue_stmt;
            }

            if (std.mem.eql(u8, tok.lexeme, "import")) {
                _ = self.advance();
                const mod_tok = self.advance();
                var alias: ?[]const u8 = null;
                if (std.mem.eql(u8, self.cur().lexeme, "as")) {
                    _ = self.advance();
                    alias = self.advance().lexeme;
                }
                self.consumePeriod();
                return .{
                    .import_stmt = .{
                        .module_path = mod_tok.lexeme,
                        .alias = alias,
                    },
                };
            }

            if (std.mem.eql(u8, tok.lexeme, "extern")) {
                _ = self.advance();
                self.skipEols();
                if (std.mem.eql(u8, self.cur().lexeme, "from")) _ = self.advance();
                self.skipEols();
                const lib_tok = self.advance();
                self.skipEols();
                if (std.mem.eql(u8, self.cur().lexeme, "to")) _ = self.advance();
                self.skipEols();
                const fn_tok = self.advance();
                self.skipEols();
                var alias: ?[]const u8 = null;
                if (std.mem.eql(u8, self.cur().lexeme, "as")) {
                    _ = self.advance();
                    self.skipEols();
                    alias = self.advance().lexeme;
                    self.skipEols();
                }
                var params: std.ArrayList(ast.ExternParam) = .empty;
                var has_explicit_sig = false;
                if (std.mem.eql(u8, self.cur().lexeme, "with")) {
                    _ = self.advance();
                    self.skipEols();
                    has_explicit_sig = true;
                    while (isNameToken(self.cur())) {
                        const pname = self.advance().lexeme;
                        self.skipEols();
                        var ptype: ast.FfiType = .auto;
                        if (self.cur().kind == .punctuation and std.mem.eql(u8, self.cur().lexeme, ":")) {
                            _ = self.advance();
                            self.skipEols();
                            ptype = parseFfiType(self.advance());
                            self.skipEols();
                        }
                        try params.append(self.allocator, .{ .name = pname, .ffi_type = ptype });
                        self.skipEols();
                        if (std.mem.eql(u8, self.cur().lexeme, ",")) {
                            _ = self.advance();
                            self.skipEols();
                        } else {
                            break;
                        }
                    }
                }
                var ret_type: ast.FfiType = .auto;
                self.skipEols();
                if (std.mem.eql(u8, self.cur().lexeme, "returns")) {
                    _ = self.advance();
                    self.skipEols();
                    has_explicit_sig = true;
                    ret_type = parseFfiType(self.advance());
                    self.skipEols();
                }
                self.consumePeriod();
                return .{
                    .extern_fn_def = .{
                        .library = lib_tok.lexeme,
                        .name = fn_tok.lexeme,
                        .alias = alias,
                        .params = try params.toOwnedSlice(self.allocator),
                        .ret_type = ret_type,
                        .has_explicit_sig = has_explicit_sig,
                    },
                };
            }

            if (std.mem.eql(u8, tok.lexeme, "from")) {
                _ = self.advance();
                self.skipEols();
                const mod_tok = self.advance();
                self.skipEols();
                if (std.mem.eql(u8, self.cur().lexeme, "import")) _ = self.advance();
                self.skipEols();
                var syms: std.ArrayList(ast.ImportSymbol) = .empty;
                while (self.cur().kind != .eof and !std.mem.eql(u8, self.cur().lexeme, ".")) {
                    self.skipEols();
                    if (self.cur().kind == .eof or std.mem.eql(u8, self.cur().lexeme, ".")) break;
                    const sname = self.advance().lexeme;
                    self.skipEols();
                    var salias: ?[]const u8 = null;
                    if (std.mem.eql(u8, self.cur().lexeme, "as")) {
                        _ = self.advance();
                        self.skipEols();
                        salias = self.advance().lexeme;
                        self.skipEols();
                    }
                    var sparams: ?[]const ast.ExternParam = null;
                    if (std.mem.eql(u8, self.cur().lexeme, "with")) {
                        _ = self.advance();
                        self.skipEols();
                        var plist: std.ArrayList(ast.ExternParam) = .empty;
                        while (isNameToken(self.cur())) {
                            const pname = self.advance().lexeme;
                            self.skipEols();
                            var ptype: ast.FfiType = .auto;
                            if (self.cur().kind == .punctuation and std.mem.eql(u8, self.cur().lexeme, ":")) {
                                _ = self.advance();
                                self.skipEols();
                                ptype = parseFfiType(self.advance());
                                self.skipEols();
                            }
                            try plist.append(self.allocator, .{ .name = pname, .ffi_type = ptype });
                            self.skipEols();
                            if (std.mem.eql(u8, self.cur().lexeme, ",")) {
                                _ = self.advance();
                                self.skipEols();
                            } else {
                                break;
                            }
                        }
                        sparams = try plist.toOwnedSlice(self.allocator);
                    }
                    var sret: ast.FfiType = .auto;
                    self.skipEols();
                    if (std.mem.eql(u8, self.cur().lexeme, "returns")) {
                        _ = self.advance();
                        self.skipEols();
                        sret = parseFfiType(self.advance());
                        self.skipEols();
                    }
                    try syms.append(self.allocator, .{
                        .name = sname,
                        .alias = salias,
                        .params = sparams,
                        .ret_type = sret,
                    });
                    self.skipEols();
                    if (std.mem.eql(u8, self.cur().lexeme, ",")) {
                        _ = self.advance();
                        self.skipEols();
                    } else {
                        break;
                    }
                }
                self.skipEols();
                self.consumePeriod();
                return .{
                    .from_import_stmt = .{
                        .module_path = mod_tok.lexeme,
                        .symbols = try syms.toOwnedSlice(self.allocator),
                    },
                };
            }
        }

        const expr = try self.parseExpr(0, false);
        self.consumePeriod();
        if (expr.* == .ident or expr.* == .member_access) {
            const call_expr = try self.allocExpr(.{
                .func_call = .{
                    .callee = expr,
                    .args = &.{},
                },
            });
            return .{ .expr_stmt = call_expr };
        }
        return .{ .expr_stmt = expr };
    }

    pub fn parseProgram(self: *Parser) ParseError!ast.Program {
        const stmts = try self.parseStmtList("", "");
        return .{ .statements = stmts };
    }
};

pub fn parseSource(allocator: std.mem.Allocator, src: []const u8) !ast.Program {
    const tokens = try lexer.tokenize(allocator, src);
    var parser = Parser.init(allocator, tokens);
    return parser.parseProgram();
}

fn isBuiltinModuleName(name: []const u8) bool {
    const builtins = [_][]const u8{ "strings", "math", "files", "collections", "types" };
    for (builtins) |b| {
        if (std.mem.eql(u8, name, b)) return true;
    }
    return false;
}

pub fn isExternalLibraryPath(path: []const u8) bool {
    const exts = [_][]const u8{
        ".zig", ".c", ".cpp", ".cc", ".cxx", ".dll", ".so", ".dylib", ".lib", ".a", ".h", ".hpp",
    };
    for (exts) |ext| {
        if (std.mem.endsWith(u8, path, ext)) return true;
    }
    const sys = [_][]const u8{ "c", "libc", "m", "msvcrt", "kernel32", "user32", "gdi32" };
    for (sys) |s| {
        if (std.mem.eql(u8, path, s)) return true;
    }
    return false;
}

fn bundleStatements(
    allocator: std.mem.Allocator,
    io: ?std.Io,
    stmts: []const Stmt,
    base_dir: []const u8,
    visited: *std.StringArrayHashMapUnmanaged(void),
    out: *std.ArrayList(Stmt),
) anyerror!void {
    for (stmts) |st| {
        switch (st) {
            .import_stmt => |is| {
                if (isExternalLibraryPath(is.module_path)) {
                    try out.append(allocator, st);
                } else {
                    if (!isBuiltinModuleName(is.module_path)) {
                        try loadAndSpliceModule(allocator, io, is.module_path, base_dir, visited, out);
                    }
                    try out.append(allocator, st);
                }
            },
            .from_import_stmt => |fis| {
                if (isExternalLibraryPath(fis.module_path)) {
                    try out.append(allocator, st);
                } else {
                    if (!isBuiltinModuleName(fis.module_path)) {
                        try loadAndSpliceModule(allocator, io, fis.module_path, base_dir, visited, out);
                    }
                }
            },
            else => try out.append(allocator, st),
        }
    }
}

fn loadAndSpliceModule(
    allocator: std.mem.Allocator,
    io_opt: ?std.Io,
    raw_mod: []const u8,
    base_dir: []const u8,
    visited: *std.StringArrayHashMapUnmanaged(void),
    out: *std.ArrayList(Stmt),
) anyerror!void {
    if (isExternalLibraryPath(raw_mod)) return;
    const io = io_opt orelse return;
    if (visited.contains(raw_mod)) return;
    try visited.put(allocator, raw_mod, {});

    const filename = if (std.mem.endsWith(u8, raw_mod, ".engage"))
        raw_mod
    else
        try std.fmt.allocPrint(allocator, "{s}.engage", .{raw_mod});

    const rel_path = if (std.mem.eql(u8, base_dir, ".") or base_dir.len == 0)
        filename
    else
        try std.fmt.allocPrint(allocator, "{s}/{s}", .{ base_dir, filename });

    const mod_src = std.Io.Dir.cwd().readFileAlloc(io, rel_path, allocator, .limited(16 * 1024 * 1024)) catch blk: {
        break :blk std.Io.Dir.cwd().readFileAlloc(io, filename, allocator, .limited(16 * 1024 * 1024)) catch return;
    };

    const mod_prog = try parseSource(allocator, mod_src);
    try bundleStatements(allocator, io_opt, mod_prog.statements, base_dir, visited, out);
}

pub fn parseAndBundle(
    allocator: std.mem.Allocator,
    io: ?std.Io,
    src: []const u8,
    base_dir: []const u8,
) !ast.Program {
    const prog = try parseSource(allocator, src);
    var visited: std.StringArrayHashMapUnmanaged(void) = .empty;
    var bundled: std.ArrayList(Stmt) = .empty;
    try bundleStatements(allocator, io, prog.statements, base_dir, &visited, &bundled);
    return .{ .statements = try bundled.toOwnedSlice(allocator) };
}

test "parser builds AST for functions, records, and control flow" {
    var arena = std.heap.ArenaAllocator.init(std.testing.allocator);
    defer arena.deinit();
    const prog = try parseSource(arena.allocator(),
        \\define a record named Vec2:
        \\    let x be 0.
        \\    to scale with f:
        \\        set self.x to self.x times f.
        \\    end
        \\end
        \\let v be new Vec2 with x: 5.
        \\v.scale with 3.
    );
    try std.testing.expectEqual(@as(usize, 3), prog.statements.len);
    try std.testing.expect(prog.statements[0] == .record_def);
    try std.testing.expectEqualStrings("Vec2", prog.statements[0].record_def.name);
}
