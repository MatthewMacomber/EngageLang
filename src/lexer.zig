const std = @import("std");

pub const TokenType = enum {
    keyword,
    identifier,
    number,
    string,
    operator,
    punctuation,
    eol,
    eof,
};

pub const Token = struct {
    kind: TokenType,
    lexeme: []const u8,
    line: u32,
    column: u32,
};

const multi_word_ops = [_][]const u8{
    "is greater than or equal to",
    "is less than or equal to",
    "the error message of",
    "concatenated with",
    "is not equal to",
    "the ok value of",
    "or return error",
    "is greater than",
    "is less than",
    "is equal to",
    "divided by",
    "is not",
    "is an",
    "is a",
};

fn isAlpha(c: u8) bool {
    return (c >= 'a' and c <= 'z') or (c >= 'A' and c <= 'Z') or c == '_';
}

fn isDigit(c: u8) bool {
    return c >= '0' and c <= '9';
}

fn isAlnum(c: u8) bool {
    return isAlpha(c) or isDigit(c);
}

fn isWordOperator(w: []const u8) bool {
    const ops = [_][]const u8{
        "plus", "minus", "times", "modulo", "is", "and", "or", "not", "call",
    };
    for (ops) |op| {
        if (std.mem.eql(u8, w, op)) return true;
    }
    return false;
}

fn isKeyword(w: []const u8) bool {
    const kws = [_][]const u8{
        "create",      "let",          "be",        "with",      "the",     "value",
        "as",          "set",          "to",        "if",        "then",    "otherwise",
        "end",         "switch",       "on",        "case",      "default", "repeat",
        "while",       "for",          "each",      "in",        "break",   "continue",
        "returns",     "return",       "Ok",        "Error",     "ok",      "error",
        "export",      "import",       "extern",
        "a",           "run",          "concurrently", "channel", "named",  "send",
        "through",     "receive",      "from",      "define",    "fiber",   "yield",
        "record",      "new",          "self",      "Table",     "Vector",  "Record",
        "property",
    };
    for (kws) |kw| {
        if (std.mem.eql(u8, w, kw)) return true;
    }
    return false;
}

fn matchPhraseAt(src: []const u8, pos: usize, phrase: []const u8) bool {
    if (pos + phrase.len > src.len) return false;
    if (!std.mem.eql(u8, src[pos .. pos + phrase.len], phrase)) return false;
    if (pos + phrase.len < src.len and isAlnum(src[pos + phrase.len])) return false;
    return true;
}

pub fn tokenize(allocator: std.mem.Allocator, src: []const u8) ![]Token {
    var tokens: std.ArrayList(Token) = .empty;
    errdefer tokens.deinit(allocator);

    var pos: usize = 0;
    var line: u32 = 1;
    var col: u32 = 1;

    while (pos < src.len) {
        const ch = src[pos];

        // Skip horizontal whitespace
        if (ch == ' ' or ch == '\t' or ch == '\r') {
            pos += 1;
            col += 1;
            continue;
        }

        // Newline -> EOL token
        if (ch == '\n') {
            try tokens.append(allocator, .{ .kind = .eol, .lexeme = "\n", .line = line, .column = col });
            pos += 1;
            line += 1;
            col = 1;
            continue;
        }

        // Single-line comment //
        if (ch == '/' and pos + 1 < src.len and src[pos + 1] == '/') {
            pos += 2;
            col += 2;
            while (pos < src.len and src[pos] != '\n') {
                pos += 1;
                col += 1;
            }
            continue;
        }

        // Multi-line comment /* ... */
        if (ch == '/' and pos + 1 < src.len and src[pos + 1] == '*') {
            pos += 2;
            col += 2;
            while (pos < src.len) {
                if (src[pos] == '\n') {
                    line += 1;
                    col = 1;
                    pos += 1;
                } else if (src[pos] == '*' and pos + 1 < src.len and src[pos + 1] == '/') {
                    pos += 2;
                    col += 2;
                    break;
                } else {
                    pos += 1;
                    col += 1;
                }
            }
            continue;
        }

        // Check multi-word operators first (only when starting at an alpha character)
        if (isAlpha(ch)) {
            var matched_phrase: ?[]const u8 = null;
            for (multi_word_ops) |phrase| {
                if (matchPhraseAt(src, pos, phrase)) {
                    matched_phrase = phrase;
                    break;
                }
            }
            if (matched_phrase) |phrase| {
                try tokens.append(allocator, .{
                    .kind = .operator,
                    .lexeme = phrase,
                    .line = line,
                    .column = col,
                });
                pos += phrase.len;
                col += @intCast(phrase.len);
                continue;
            }
        }

        // Number literals
        if (isDigit(ch)) {
            const start = pos;
            const start_col = col;
            while (pos < src.len and isDigit(src[pos])) {
                pos += 1;
                col += 1;
            }
            if (pos + 1 < src.len and src[pos] == '.' and isDigit(src[pos + 1])) {
                pos += 1;
                col += 1;
                while (pos < src.len and isDigit(src[pos])) {
                    pos += 1;
                    col += 1;
                }
            }
            try tokens.append(allocator, .{
                .kind = .number,
                .lexeme = src[start..pos],
                .line = line,
                .column = start_col,
            });
            continue;
        }

        // String literals (single, double, or triple-quoted)
        if (ch == '"' or ch == '\'') {
            const quote = ch;
            const start_line = line;
            const start_col = col;
            const is_triple = (pos + 2 < src.len and src[pos + 1] == quote and src[pos + 2] == quote);
            if (is_triple) {
                pos += 3;
                col += 3;
            } else {
                pos += 1;
                col += 1;
            }

            var buf: std.ArrayList(u8) = .empty;
            while (pos < src.len) {
                if (is_triple) {
                    if (pos + 2 < src.len and src[pos] == quote and src[pos + 1] == quote and src[pos + 2] == quote) {
                        pos += 3;
                        col += 3;
                        break;
                    }
                } else if (src[pos] == quote) {
                    pos += 1;
                    col += 1;
                    break;
                }

                if (src[pos] == '\\' and pos + 1 < src.len) {
                    pos += 1;
                    col += 1;
                    const esc = src[pos];
                    switch (esc) {
                        'n' => try buf.append(allocator, '\n'),
                        't' => try buf.append(allocator, '\t'),
                        'r' => try buf.append(allocator, '\r'),
                        '\\' => try buf.append(allocator, '\\'),
                        '"' => try buf.append(allocator, '"'),
                        '\'' => try buf.append(allocator, '\''),
                        '0' => try buf.append(allocator, 0),
                        'x' => {
                            if (pos + 2 < src.len) {
                                const hex = src[pos + 1 .. pos + 3];
                                if (std.fmt.parseInt(u8, hex, 16)) |byte| {
                                    try buf.append(allocator, byte);
                                    pos += 2;
                                    col += 2;
                                } else |_| {
                                    try buf.appendSlice(allocator, "\\x");
                                }
                            } else {
                                try buf.appendSlice(allocator, "\\x");
                            }
                        },
                        else => {
                            try buf.append(allocator, '\\');
                            try buf.append(allocator, esc);
                        },
                    }
                    pos += 1;
                    col += 1;
                } else {
                    if (src[pos] == '\n') {
                        line += 1;
                        col = 1;
                    } else {
                        col += 1;
                    }
                    try buf.append(allocator, src[pos]);
                    pos += 1;
                }
            }

            try tokens.append(allocator, .{
                .kind = .string,
                .lexeme = try buf.toOwnedSlice(allocator),
                .line = start_line,
                .column = start_col,
            });
            continue;
        }

        // Identifiers, Keywords, and Single-Word Operators
        if (isAlpha(ch)) {
            const start = pos;
            const start_col = col;
            while (pos < src.len and isAlnum(src[pos])) {
                pos += 1;
                col += 1;
            }
            const word = src[start..pos];
            const kind: TokenType = if (isWordOperator(word))
                .operator
            else if (isKeyword(word))
                .keyword
            else
                .identifier;

            try tokens.append(allocator, .{
                .kind = kind,
                .lexeme = word,
                .line = line,
                .column = start_col,
            });
            continue;
        }

        // Symbolic two-character operators
        if (pos + 1 < src.len) {
            const two = src[pos .. pos + 2];
            if (std.mem.eql(u8, two, "==") or std.mem.eql(u8, two, "!=") or
                std.mem.eql(u8, two, "<=") or std.mem.eql(u8, two, ">="))
            {
                try tokens.append(allocator, .{
                    .kind = .operator,
                    .lexeme = two,
                    .line = line,
                    .column = col,
                });
                pos += 2;
                col += 2;
                continue;
            }
        }

        // Symbolic single-character operators
        if (ch == '+' or ch == '-' or ch == '*' or ch == '/' or ch == '%' or ch == '<' or ch == '>') {
            try tokens.append(allocator, .{
                .kind = .operator,
                .lexeme = src[pos .. pos + 1],
                .line = line,
                .column = col,
            });
            pos += 1;
            col += 1;
            continue;
        }

        // Punctuation (., :, [, ], (, ), {, }, =)
        try tokens.append(allocator, .{
            .kind = .punctuation,
            .lexeme = src[pos .. pos + 1],
            .line = line,
            .column = col,
        });
        pos += 1;
        col += 1;
    }

    try tokens.append(allocator, .{
        .kind = .eof,
        .lexeme = "",
        .line = line,
        .column = col,
    });

    return tokens.toOwnedSlice(allocator);
}

test "lexer tokenizes natural language operators and statements" {
    var arena = std.heap.ArenaAllocator.init(std.testing.allocator);
    defer arena.deinit();
    const toks = try tokenize(arena.allocator(), "let x be 10 plus 20.\nif x is greater than or equal to 30 then\nend");
    try std.testing.expectEqual(TokenType.keyword, toks[0].kind);
    try std.testing.expectEqualStrings("let", toks[0].lexeme);
    try std.testing.expectEqual(TokenType.identifier, toks[1].kind);
    try std.testing.expectEqualStrings("x", toks[1].lexeme);
    try std.testing.expectEqual(TokenType.operator, toks[4].kind);
    try std.testing.expectEqualStrings("plus", toks[4].lexeme);
    try std.testing.expectEqual(TokenType.punctuation, toks[6].kind);
    try std.testing.expectEqualStrings(".", toks[6].lexeme);
    try std.testing.expectEqual(TokenType.operator, toks[10].kind);
    try std.testing.expectEqualStrings("is greater than or equal to", toks[10].lexeme);
}
