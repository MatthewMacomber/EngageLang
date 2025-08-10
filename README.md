# Engage Programming Language v2

A natural language programming language designed for readability, power, and safety.

## Quick Start

1. **Run a program**: `python engage_interpreter.py examples/hello_world.engage`
2. **Interactive REPL**: `python engage_vm.py`
3. **Compile to C++**: `python engage_transpiler.py examples/hello_world.engage`
4. **Use the launcher**: `python run_engage.py examples/hello_world.engage`
5. **Test the package**: `python test_package.py`

## Core Files

### Language Implementation
- `engage_lexer.py` - Tokenization and lexical analysis
- `engage_parser.py` - AST generation and syntax parsing  
- `engage_interpreter.py` - Main execution engine
- `engage_vm.py` - Bytecode virtual machine with REPL
- `engage_transpiler.py` - C++ code generation
- `engage_errors.py` - Enhanced error reporting system

### Standard Library
- `engage_stdlib.py` - Standard library foundation
- `stdlib_strings.py` - String manipulation functions
- `stdlib_math.py` - Mathematical operations
- `stdlib_files.py` - File system operations
- `stdlib_collections.py` - Data structure manipulation
- `stdlib_types.py` - Type checking and conversion

### Advanced Systems
- `engage_modules.py` - Import/export system
- `engage_ui_components.py` - Interactive UI framework
- `engage_game_objects.py` - 2D game development

## Example Programs

All examples are located in the `examples/` directory:

### Basic Examples
- `examples/hello_world.engage` - Basic syntax and string operations
- `examples/simple_math.engage` - Arithmetic operations
- `examples/simple_fibonacci.engage` - Recursive functions

### Intermediate Examples
- `examples/fibonacci.engage` - Enhanced fibonacci with error handling
- `examples/guess_the_number.engage` - Interactive program with input/output

### Advanced Examples  
- `examples/working_comprehensive_demo.engage` - All core features
- `examples/working_collections_demo.engage` - Data structures
- `examples/records_demo.engage` - Object-oriented programming
- `examples/standard_library_showcase.engage` - Complete standard library

## Language Features

- **Natural syntax**: `let x be 5`, `if x is greater than 3 then...end`
- **Data structures**: Tables (hash maps), Vectors (arrays), Records (objects)
- **Standard library**: Strings, Math, Files, Collections, Types modules
- **Error handling**: Result types with `or return error`
- **Concurrency**: Tasks and channels
- **Module system**: Import/export with namespace isolation
- **Multiple execution**: Interpreter, VM, and C++ transpiler

## Testing

Test the package installation:
```bash
python test_package.py
```

Run the comprehensive test suite:
```bash
python -m pytest tests/engage_tests.py -v
```

## C++ Compilation

Generate and compile C++ code:
```bash
python engage_transpiler.py examples/hello_world.engage
cl /std:c++latest /EHsc /Fe:hello.exe hello_world.cpp    # Windows
g++ -std=c++latest -o hello hello_world.cpp              # Linux/macOS
```

## Package Structure

```
Engage v2/
├── README.md                    # This file
├── GETTING_STARTED.md          # Quick start guide  
├── CHANGELOG.md                # Version history
├── run_engage.py               # Simple launcher script
├── test_package.py             # Package verification
├── engage_*.py                 # Core implementation
├── stdlib_*.py                 # Standard library modules
├── examples/                   # Example programs
└── tests/                      # Test suite
```