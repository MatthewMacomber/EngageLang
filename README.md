# The Engage Programming Language (Engage v3)

Welcome to Engage, a natural-language programming language designed for readability, expressiveness, native performance, and effortless embedding.

**The core philosophy of Engage is that code should read like clear English instructions without sacrificing the control, speed, and safety needed for systems programming, software tools, and game scripting.**

Engage v3 is built natively in **Zig (0.17.0)**. It can be used both as a standalone compiled language (emitting optimized Zig code compiled to native executables) and as an embeddable, fast in-process scripting language for game engines and native host applications.

---

## Language at a Glance

```engage
// Define a Vector2 record
define a record named Vector2:
    property x with 0.
    property y with 0.

    to scale with factor:
        set self.x to self.x times factor.
        set self.y to self.y times factor.
    end

    to magnitude_squared:
        return (self.x times self.x) plus (self.y times self.y).
    end
end

// Create an instance, manipulate it, and inspect results
let pos be new Vector2 with x: 3, y: 4.
scale with pos, 2.
let mag_sq be pos.magnitude_squared.
print with "Squared magnitude is: " concatenated with to_string with mag_sq.
```

**Output:**
```text
Squared magnitude is: 100
```

---

## Key Capabilities

1. **Native Compiler & CLI (`engage`)**:
   - `engage build <file.engage> [-o <out.exe>]`: Transpiles Engage AST to self-contained Zig code and invokes `zig build-exe` to produce an optimized native executable.
   - `engage transpile <file.engage> [-o <out.zig>]`: Transpiles Engage to readable Zig 0.17 code.
   - `engage run <file.engage> [args...]`: Directly executes Engage programs via the native in-process engine.
   - `engage repl`: Launches an interactive REPL session with live multi-line input and expression evaluation.
2. **Zig Native Module (`engage`)**:
   - Easily imported in any Zig project via `build.zig` (`@import("engage")`).
   - Create VM instances with `EngageVM.init(allocator)`.
   - Register native host functions, expose globals, inspect values, execute scripts, and spawn concurrent fibers.
3. **C ABI Embeddability (`libengage` & `include/engage.h`)**:
   - Compiles to static library `zig-out/lib/engage.lib` and C header `zig-out/include/engage.h`.
   - Enables seamless embedding inside C, C++, Rust, and game engines (Godot, Unreal, custom engines).
4. **Self-Hosting Compiler (`engage_compiler.engage`)**:
   - Engage compiler written in Engage itself, outputting Zig 0.17 code instead of legacy C++.
5. **Archived Engage v2**:
   - The former Python reference implementation and C++17 bootstrap toolchain are preserved in `archive/Engage v2/`.

---

## Getting Started

### Prerequisites
- [Zig 0.17.0](https://ziglang.org/download/) installed and on your system `PATH`.

### Building the Project
From the repository root:
```bash
# Build the CLI executable, static library, and C header
zig build

# Run all unit and integration tests
zig build test --summary all
```

Build outputs will be generated in `zig-out/`:
- `zig-out/bin/engage.exe` — The Engage CLI
- `zig-out/lib/engage.lib` — Embeddable C static library
- `zig-out/include/engage.h` — C API header

---

## CLI Usage

### 1. Run an Engage Script Directly
```bash
.\zig-out\bin\engage.exe run examples\hello_world.engage
.\zig-out\bin\engage.exe run examples\fibonacci.engage
.\zig-out\bin\engage.exe run examples\records_demo.engage
.\zig-out\bin\engage.exe run examples\game_demo.engage
.\zig-out\bin\engage.exe run examples\ui_demo.engage
```

### 2. Compile to a Standalone Native Executable
Transpiles to Zig code and invokes `zig build-exe` automatically:
```bash
.\zig-out\bin\engage.exe build examples\fibonacci.engage -o fibonacci.exe
.\fibonacci.exe
```

### 3. Transpile to Zig Source
Generate clean, readable Zig code:
```bash
.\zig-out\bin\engage.exe transpile examples\hello_world.engage -o hello_world.zig
```

### 4. Interactive REPL
```bash
.\zig-out\bin\engage.exe repl
```
```text
Engage 3.0.0 Interactive REPL (Zig engine)
Type 'exit' or 'quit' to leave, blank line to submit multi-line blocks.
engage> let greeting be "Hello from REPL!".
engage> print with greeting.
Hello from REPL!
engage> exit
```

---

## External Libraries (Zig & C/C++ FFI)

Engage can import and use native external libraries directly in both **interpreted/VM mode (`engage run`)** and **compiled native binaries (`engage build`)**:

### 1. Zero-Ceremony Zig Modules (`.zig`)
Functions from external Zig files are imported directly with automatic comptime type reflection and argument marshaling:

```engage
from "external_math.zig" import fast_lerp, zig_fib, zig_is_prime.

let midpoint be fast_lerp with 10, 50, 0.5.
let fib10 be zig_fib with 10.
let is_p17 be zig_is_prime with 17.
```

### 2. Typed C and C++ Libraries (`.c`, `.cpp`, `.dll`, `.so`, system libc)
C and C++ functions are imported with typed signatures (`Number`, `Int`, `String`, `Bool`, `Pointer`, `Void`):

```engage
from "external_c_lib.c" import
    c_hypot with a: Number, b: Number returns Number,
    c_factorial with n: Int returns Int,
    c_sum_range with s: Int, e: Int returns Int.

let hyp be c_hypot with 3, 4.
let fact6 be c_factorial with 6.
```

Or using explicit `extern from` syntax:
```engage
extern from "c" to puts with str: String returns Int.
extern from "external_c_lib.c" to c_hypot with a: Number, b: Number returns Number.
```

### 3. Execution & Compilation
- **`engage run <script.engage>`**: Compiles an on-the-fly dynamic bridge DLL in `.engage-cache/` and dynamically binds the external functions into the running VM.
- **`engage build <script.engage> -o <bin>`**: Generates native Zig wrapper code and invokes `zig build-exe` with all external C/C++ source files and `-lc` / `-lc++` automatically.
- Check out `examples/external_libraries_demo.engage` for a complete runnable demonstration.

### 4. Current Limitations & Not Yet Implemented
The following deliberate deferrals and architectural bounds currently apply:
- **C Structs by Value**: Only primitive scalar types (`Number`, `Int`, `String`, `Bool`, `Void`) and opaque pointers (`Pointer`) are marshaled across the FFI boundary. Stack-allocated C structs passed or returned by value are not yet unpacked; use opaque handles / pointers instead.
- **C++ Name Mangling**: Direct calling of overloaded C++ class methods or member functions requires standard `extern "C"` wrappers.
- **Variadic C Functions (`...`)**: Calling varargs functions (such as `printf`) directly without explicit fixed-arity signatures is unsupported; write a fixed-parameter wrapper instead.
- **In-Process Hot Reloading**: External libraries compiled into `.engage-cache/` remain loaded for the lifetime of the process. Modifying an external C/Zig source file while a process or REPL is running requires restarting the session to rebuild the cache.
- **Direct Header Parsing (`.h` auto-import)**: External C headers are not parsed AST-style at runtime; explicit parameter and return signatures are declared via `from "lib.c" import fn with ... returns ...` or `extern from ...`.

---

## Embedding Engage

### In Zig Projects
Add Engage as a dependency or module in your `build.zig`:
```zig
const engage = @import("engage");

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    const alloc = gpa.allocator();

    var vm = engage.EngageVM.init(alloc);
    defer vm.deinit();

    // Register a native function callable from Engage scripts
    try vm.registerFn("host_add", myHostAdd);

    // Evaluate script
    const res = try vm.eval(
        \\let a be 10.
        \\let b be 20.
        \\let total be host_add with a, b.
        \\print with "Total from host is: " concatenated with to_string with total.
    );
    _ = res;
}
```

### In C / C++ and Game Engines
Include `include/engage.h` and link against `engage.lib`:
```c
#include "engage.h"
#include <stdio.h>

int main() {
    engage_vm_t* vm = engage_vm_create();

    // Set a global variable from the host
    engage_set_global_num(vm, "player_health", 100.0);

    // Run script
    engage_val_t result = engage_eval(vm, "let damaged be player_health minus 25. return damaged.");
    printf("Result: %f\n", engage_val_as_number(result));

    engage_vm_destroy(vm);
    return 0;
}
```

---

## Standard Library Modules

Engage includes built-in standard library functions across:
- **Strings**: `length`, `substring`, `slice`, `char_at`, `char_code`, `from_char_code`, `index_of`, `contains`, `starts_with`, `ends_with`, `split`, `join`, `trim`, `to_upper`, `to_lower`, `concat`, `replace`
- **Math**: `sqrt`, `pow`, `abs`, `min`, `max`, `floor`, `ceil`, `round`, `sin`, `cos`, `tan`, `random`, `random_int`
- **I/O & CLI**: `input`, `read_file`, `write_file`, `file_exists`, `get_args`
- **Collections**: `Vector` and `Table` creation, sparse vector indexing, `push`, `pop`, `insert`, `remove`, `size`, `has_key`, `keys`, `values`, `sort`, `.size` / `.length` properties
- **Types**: `type_of`, `to_string`, `number`, `to_number`, `check_number`, `check_string`, `check_vector`, `check_table`, `check_record`, `is_none`
- **Control Flow**: `if ... then ... otherwise ... end`, `while`, `repeat`, `for each`, `switch on <expr> case <val>: ... default/otherwise: ... end`
- **Error Handling**: `Ok with val`, `Error with msg`, `or return error`, `is an Ok`, `is an Error`, `the ok value of`, `the error message of`
- **Concurrency & Fibers**: `Channel`, `send ... through ...`, `receive from ...`, fibers with `yield` and cooperative resumption
- **Game & UI Objects**: `create_game_object`, `get_game_object`, `destroy_game_object`, `game_set_position`, `game_set_sprite`, `game_add_tag`, `game_check_collision`, `find_game_objects_with_tag`, `create_panel`, `create_button`, `create_label`, `create_text_input`, `ui_set_property`, `ui_get_property`, `ui_set_text`

---

## Complete Examples & Minigames

The `examples/` directory contains a comprehensive suite of complete programs:
- **`examples/dungeon_crawler_minigame.engage`**: Text-based roguelike RPG featuring Hero and Monster records, patrol AI fibers, treasure chests with Result errors, and combat evaluations via `switch on`.
- **`examples/wordle_minigame.engage`**: Complete Wordle puzzle engine featuring duplicate letter scoring (🟩, 🟨, ⬜), dictionary evaluation, and round statistics.
- **`examples/arcade_arena_minigame.engage`**: 2D arcade space arena simulation featuring game objects, projectile AABB collision checks, inter-task event channels, and live HUD updates.
- **`examples/task_scheduler_pipeline.engage`**: Event-driven priority job scheduler featuring producer fibers, channel queues, priority sorting, and error-resilient task processing.
- **`examples/fiber_demo.engage`**: Fiber cooperative multitasking and state preservation across yields.
- **`examples/concurrency_demo.engage`**: Channel message passing between concurrent tasks.
- **`examples/error_handling_showcase.engage`**: Production-grade Result error propagation, stack trace simulation, and validation.
- **`examples/game_demo.engage` & `examples/ui_demo.engage`**: Game engine integration and UI widget creation.

---

## Project Structure

```text
EngageLang/
├── build.zig                   # Zig 0.17 build configuration (CLI, module, C static lib, tests)
├── build.zig.zon               # Package manifest
├── include/
│   └── engage.h                # C ABI interface header
├── src/
│   ├── root.zig                # Library root, exports Zig API and C ABI extern functions
│   ├── main.zig                # Standalone engage CLI (run, build, transpile, repl)
│   ├── lexer.zig               # Tokenizer supporting Engage natural keywords and operators
│   ├── ast.zig                 # Tagged-union AST definitions
│   ├── parser.zig              # Recursive-descent + precedence-climbing parser & module bundler
│   ├── runtime.zig             # Runtime value representation, gc-safe heap structs, and stdlib
│   ├── vm.zig                  # In-process interpreter & embeddable scripting engine
│   └── codegen.zig             # AST -> Zig 0.17 transpiler emitting standalone Zig executables
├── engage_compiler.engage      # Self-hosting Engage compiler emitting Zig 0.17 code
├── examples/                   # Showcase scripts (hello world, fibonacci, records, games, UI)
├── archive/
│   └── Engage v2/              # Archived Python compiler, VM, and C++17 transpiler
└── docs/                       # Language design specifications
```
