# Engage Example Programs

This directory contains example programs demonstrating various features of the Engage programming language.

## Basic Examples

- `hello_world.engage` - Basic syntax and string operations
- `simple_math.engage` - Arithmetic operations and variables
- `simple_fibonacci.engage` - Recursive functions

## Intermediate Examples

- `fibonacci.engage` - Enhanced fibonacci with error handling
- `guess_the_number.engage` - Interactive program with input/output
- `records_demo.engage` - Object-oriented programming with records

## Advanced Examples

- `working_comprehensive_demo.engage` - All core features working together
- `working_collections_demo.engage` - Tables, vectors, and data structures
- `standard_library_showcase.engage` - Complete standard library demonstration

## Running Examples

Use the interpreter to run any example:

```bash
python engage_interpreter.py hello_world.engage
python engage_interpreter.py working_comprehensive_demo.engage
```

Or use the launcher script:

```bash
python run_engage.py hello_world.engage
```

## C++ Compilation

Many examples can be compiled to C++:

```bash
python engage_transpiler.py hello_world.engage
cl /std:c++latest /EHsc /Fe:hello.exe hello_world.cpp
```