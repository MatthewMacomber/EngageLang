# Getting Started with Engage v2

Welcome to Engage, a natural language programming language designed for readability and power.

## Quick Start

1. **Run your first program:**
   ```bash
   python engage_interpreter.py examples/hello_world.engage
   ```

2. **Try the interactive REPL:**
   ```bash
   python engage_vm.py
   ```

3. **Compile to C++:**
   ```bash
   python engage_transpiler.py examples/hello_world.engage
   cl /std:c++latest /EHsc /Fe:hello.exe hello_world.cpp
   ```

## Language Basics

### Variables and Values
```engage
let name be "Alice".
let age be 25.
let height be 5.6.
```

### Functions
```engage
to greet with person_name:
    let message be "Hello, " concatenated with person_name.
    print with message.
end

greet with "World".
```

### Conditionals
```engage
let score be 85.

if score is greater than 90 then
    print with "Excellent!".
otherwise
    print with "Good job!".
end
```

### Data Structures
```engage
// Tables (hash maps)
let inventory be Table.
set inventory["sword"] to 1.
set inventory["potion"] to 5.

// Vectors (arrays)
let numbers be Vector.
let len1 be push with numbers, 10.
let len2 be push with numbers, 20.
```

### Records (Objects)
```engage
to define Person:
    property name with "Unknown".
    property age with 0.
    
    to introduce:
        print with "Hi, I'm " concatenated with self.name.
    end
end

let alice be new Person with name: "Alice", age: 30.
alice.introduce.
```

## Standard Library

Engage includes comprehensive standard library modules:

```engage
import "strings" as str.
import "math" as math.
import "files" as files.
import "collections" as coll.
import "types" as types.

let text be "Hello World".
let length be str.length with text.
let upper_text be str.to_upper with text.

let result be math.sqrt with 16.
let power be math.pow with 2, 3.
```

## Example Programs

### Basic Examples
- `examples/hello_world.engage` - Your first Engage program
- `examples/simple_math.engage` - Basic arithmetic
- `examples/simple_fibonacci.engage` - Recursive functions

### Advanced Examples
- `examples/working_comprehensive_demo.engage` - All features
- `examples/records_demo.engage` - Object-oriented programming
- `examples/standard_library_showcase.engage` - Complete standard library

## Running Programs

### Using the Interpreter
```bash
python engage_interpreter.py examples/hello_world.engage
```

### Using the Launcher Script
```bash
python run_engage.py examples/hello_world.engage
```

### Interactive Development
```bash
python engage_vm.py
```

Then use commands like:
- `_run examples/hello_world.engage` - Execute a file
- `_load examples/fibonacci.engage` - Load and execute
- Type Engage code directly for immediate execution

## C++ Compilation

Generate optimized C++ code:

```bash
# Generate C++ code
python engage_transpiler.py examples/hello_world.engage

# Compile with Visual Studio (Windows)
cl /std:c++latest /EHsc /Fe:hello.exe hello_world.cpp

# Compile with GCC/Clang (Linux/macOS)
g++ -std=c++latest -o hello hello_world.cpp
clang++ -std=c++latest -o hello hello_world.cpp
```

## Testing

Run the test suite to verify everything works:

```bash
python -m pytest tests/engage_tests.py -v
```

## Next Steps

1. **Explore Examples**: Start with `examples/hello_world.engage` and work your way up
2. **Read the Documentation**: Check out the main README.md for comprehensive features
3. **Try the REPL**: Use `python engage_vm.py` for interactive development
4. **Build Something**: Create your own `.engage` files using the examples as templates

## Language Features

- **Natural Syntax**: Code reads like instructions
- **Multiple Execution**: Interpreter, VM, and C++ transpiler
- **Rich Data Types**: Tables, Vectors, Records, and more
- **Standard Library**: Strings, Math, Files, Collections, Types
- **Error Handling**: Result types with explicit error propagation
- **Concurrency**: Tasks and channels for parallel programming
- **Module System**: Import/export with namespace isolation

## Getting Help

- Check the examples directory for working code
- Read error messages carefully - they include helpful suggestions
- Use the REPL for quick testing and experimentation
- Review the comprehensive README.md for detailed documentation