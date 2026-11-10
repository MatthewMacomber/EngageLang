const std = @import("std");
const Io = std.Io;
const engage = @import("engage");

fn printUsage(w: *Io.Writer) !void {
    try w.print(
        \\Engage Programming Language (v3 - Zig Implementation)
        \\
        \\Usage:
        \\  engage run <file.engage> [args...]        Execute an Engage program in the VM
        \\  engage build <file.engage> [-o <out.exe>] Compile an Engage program to a native binary via Zig
        \\  engage transpile <file.engage> [-o <zig>] Transpile an Engage program to standalone Zig code
        \\  engage repl                               Start the interactive Engage REPL
        \\  engage <file.engage> [args...]            Shorthand for 'engage run <file.engage>'
        \\
    , .{});
    try w.flush();
}

fn dirNameOrDot(path: []const u8) []const u8 {
    return std.Io.Dir.path.dirname(path) orelse ".";
}

fn stemWithoutExt(allocator: std.mem.Allocator, path: []const u8) ![]const u8 {
    const base = std.Io.Dir.path.basename(path);
    const stem = std.Io.Dir.path.stem(base);
    if (std.Io.Dir.path.dirname(path)) |dir| {
        return std.fmt.allocPrint(allocator, "{s}/{s}", .{ dir, stem });
    }
    return allocator.dupe(u8, stem);
}

fn cmdTranspile(
    allocator: std.mem.Allocator,
    io: Io,
    input_path: []const u8,
    output_path_opt: ?[]const u8,
    stdout: *Io.Writer,
) ![]const u8 {
    const src = try Io.Dir.cwd().readFileAlloc(io, input_path, allocator, .limited(64 * 1024 * 1024));
    const base_dir = dirNameOrDot(input_path);
    const prog = try engage.parser.parseAndBundle(allocator, io, src, base_dir);
    const zig_code = try engage.codegen.generateZigSource(allocator, prog);

    const out_path = if (output_path_opt) |p|
        p
    else blk: {
        const stem = try stemWithoutExt(allocator, input_path);
        break :blk try std.fmt.allocPrint(allocator, "{s}.zig", .{stem});
    };

    try Io.Dir.cwd().writeFile(io, .{ .sub_path = out_path, .data = zig_code });
    try stdout.print("Transpiled {s} -> {s} ({d} bytes)\n", .{ input_path, out_path, zig_code.len });
    try stdout.flush();
    return out_path;
}

fn cmdBuild(
    allocator: std.mem.Allocator,
    io: Io,
    input_path: []const u8,
    output_exe_opt: ?[]const u8,
    stdout: *Io.Writer,
) !void {
    const stem = try stemWithoutExt(allocator, input_path);
    const temp_zig = try std.fmt.allocPrint(allocator, "{s}.zig", .{stem});
    const src = try Io.Dir.cwd().readFileAlloc(io, input_path, allocator, .limited(64 * 1024 * 1024));
    const base_dir = dirNameOrDot(input_path);
    const prog = try engage.parser.parseAndBundle(allocator, io, src, base_dir);
    const zig_code = try engage.codegen.generateZigSource(allocator, prog);
    try Io.Dir.cwd().writeFile(io, .{ .sub_path = temp_zig, .data = zig_code });
    try stdout.print("Transpiled {s} -> {s} ({d} bytes)\n", .{ input_path, temp_zig, zig_code.len });
    try stdout.flush();

    var argv: std.ArrayList([]const u8) = .empty;
    try argv.append(allocator, "zig");
    try argv.append(allocator, "build-exe");
    try argv.append(allocator, temp_zig);

    var has_c = false;
    var has_cpp = false;
    for (prog.statements) |st| {
        const lib_opt: ?[]const u8 = switch (st) {
            .extern_fn_def => |efd| efd.library,
            .from_import_stmt => |fis| if (engage.parser.isExternalLibraryPath(fis.module_path)) fis.module_path else null,
            else => null,
        };
        if (lib_opt) |lib| {
            if (std.mem.endsWith(u8, lib, ".c") or std.mem.endsWith(u8, lib, ".cpp") or std.mem.endsWith(u8, lib, ".cc") or std.mem.endsWith(u8, lib, ".cxx") or std.mem.endsWith(u8, lib, ".lib") or std.mem.endsWith(u8, lib, ".a") or std.mem.endsWith(u8, lib, ".obj") or std.mem.endsWith(u8, lib, ".o")) {
                const full_lib = if (std.mem.eql(u8, base_dir, ".") or std.Io.Dir.path.isAbsolute(lib))
                    lib
                else
                    try std.fmt.allocPrint(allocator, "{s}/{s}", .{ base_dir, lib });
                try argv.append(allocator, full_lib);
                if (std.mem.endsWith(u8, lib, ".c")) has_c = true;
                if (std.mem.endsWith(u8, lib, ".cpp") or std.mem.endsWith(u8, lib, ".cc") or std.mem.endsWith(u8, lib, ".cxx")) has_cpp = true;
            }
        }
    }
    if (has_c or has_cpp) try argv.append(allocator, "-lc");
    if (has_cpp) try argv.append(allocator, "-lc++");

    if (output_exe_opt) |out_exe| {
        const emit_arg = try std.fmt.allocPrint(allocator, "-femit-bin={s}", .{out_exe});
        try argv.append(allocator, emit_arg);
    }

    var child = try std.process.spawn(io, .{
        .argv = argv.items,
    });
    const term = try child.wait(io);
    switch (term) {
        .exited => |code| {
            if (code != 0) return error.ZigCompilationFailed;
        },
        else => return error.ZigCompilationFailed,
    }
    try stdout.print("Built native executable successfully.\n", .{});
    try stdout.flush();
}

fn cmdRun(
    allocator: std.mem.Allocator,
    io: Io,
    input_path: []const u8,
    script_args: []const []const u8,
) !void {
    const src = try Io.Dir.cwd().readFileAlloc(io, input_path, allocator, .limited(64 * 1024 * 1024));
    const base_dir = dirNameOrDot(input_path);
    const prog = try engage.parser.parseAndBundle(allocator, io, src, base_dir);

    var evm = engage.EngageVM.init(allocator, io);
    defer evm.deinit();
    evm.base_dir = base_dir;
    for (script_args) |a| {
        try evm.rt.cli_args.append(evm.allocator(), engage.Value.fromString(a));
    }
    _ = try evm.evalProgram(prog);
}

fn cmdRepl(allocator: std.mem.Allocator, io: Io, stdout: *Io.Writer) !void {
    var evm = engage.EngageVM.init(allocator, io);
    defer evm.deinit();

    try stdout.print("Engage v3 Interactive REPL (Zig Engine). Type 'exit' to quit.\n", .{});
    try stdout.flush();

    var stdin_buf: [4096]u8 = undefined;
    var stdin_reader = Io.File.stdin().reader(io, &stdin_buf);
    const r = &stdin_reader.interface;

    while (true) {
        try stdout.print("engage> ", .{});
        try stdout.flush();

        const raw_line = (try r.takeDelimiter('\n')) orelse break;
        const line = std.mem.trim(u8, raw_line, " \t\r\n");
        if (line.len == 0) continue;
        if (std.mem.eql(u8, line, "exit") or std.mem.eql(u8, line, "quit")) break;

        const val = evm.eval(line) catch |err| {
            try stdout.print("Error: {s}\n", .{@errorName(err)});
            try stdout.flush();
            continue;
        };
        if (val != .none) {
            const s = try val.toString(evm.allocator());
            try stdout.print("=> {s}\n", .{s});
            try stdout.flush();
        }
    }
}

pub fn main(init: std.process.Init) !void {
    const arena = init.arena.allocator();
    const io = init.io;
    const args = try init.minimal.args.toSlice(arena);

    var stdout_buffer: [2048]u8 = undefined;
    var stdout_file_writer: Io.File.Writer = .init(.stdout(), io, &stdout_buffer);
    const stdout = &stdout_file_writer.interface;

    if (args.len < 2) {
        try printUsage(stdout);
        return;
    }

    const subcmd = args[1];
    if (std.mem.eql(u8, subcmd, "--help") or std.mem.eql(u8, subcmd, "-h") or std.mem.eql(u8, subcmd, "help")) {
        try printUsage(stdout);
        return;
    }

    if (std.mem.eql(u8, subcmd, "repl")) {
        try cmdRepl(arena, io, stdout);
        return;
    }

    if (std.mem.eql(u8, subcmd, "run")) {
        if (args.len < 3) {
            try printUsage(stdout);
            return;
        }
        try cmdRun(arena, io, args[2], args[3..]);
        return;
    }

    if (std.mem.eql(u8, subcmd, "transpile")) {
        if (args.len < 3) {
            try printUsage(stdout);
            return;
        }
        var in_path: []const u8 = args[2];
        var out_path: ?[]const u8 = null;
        var i: usize = 2;
        while (i < args.len) : (i += 1) {
            if (std.mem.eql(u8, args[i], "-o") and i + 1 < args.len) {
                out_path = args[i + 1];
                i += 1;
            } else {
                in_path = args[i];
            }
        }
        _ = try cmdTranspile(arena, io, in_path, out_path, stdout);
        return;
    }

    if (std.mem.eql(u8, subcmd, "build")) {
        if (args.len < 3) {
            try printUsage(stdout);
            return;
        }
        var in_path: []const u8 = args[2];
        var out_exe: ?[]const u8 = null;
        var i: usize = 2;
        while (i < args.len) : (i += 1) {
            if (std.mem.eql(u8, args[i], "-o") and i + 1 < args.len) {
                out_exe = args[i + 1];
                i += 1;
            } else {
                in_path = args[i];
            }
        }
        try cmdBuild(arena, io, in_path, out_exe, stdout);
        return;
    }

    // Legacy / direct invocation: `engage <input.engage> <output.zig>` (for self-hosting compiler CLI compatibility) or `engage <file.engage> [args...]`
    if (args.len == 3 and std.mem.endsWith(u8, args[1], ".engage") and std.mem.endsWith(u8, args[2], ".zig")) {
        _ = try cmdTranspile(arena, io, args[1], args[2], stdout);
        return;
    }

    try cmdRun(arena, io, subcmd, args[2..]);
}
