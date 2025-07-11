# The Engage Programming Language

Welcome to Engage, a conceptual programming language designed from the ground up for readability, power, and safety. Engage merges the most intuitive features from several modern and domain-specific languages to create a unique development experience.

**The core philosophy of Engage is that code should be as clear to read as natural language, without sacrificing the control and performance needed for complex applications.**

This repository contains a complete, functional interpreter for Engage, written in Python, including a **Lexer**, a **Parser**, and an **Interpreter/Evaluator**.

## Language at a Glance

Engage code is designed to be self-descriptive. Here’s a quick example:

```
// Define a function to greet someone
to greet with person_name:
    let message be "Hello, " concatenated with person_name.
    print with message.
end

// Call the function
greet with "World".

```

**Output:**

```
Hello, World

```

## Features

-   **Natural Language Syntax:** Write code that reads like a set of instructions, with keywords like `let`, `be`, `with`, `plus`, and `is greater than`.
    
-   **Statically Typed, Dynamically Felt:** The language is designed to be statically typed under the hood, but the interpreter uses dynamic typing for simplicity, giving you the feel of a scripting language.
    
-   **Built-in Safety:** Function-based scope and explicit `return` statements prevent common errors.
    
-   **Clear Control Flow:**  `if...then...otherwise...end` blocks make logic easy to follow.
    
-   **Simple and Powerful Functions:** Easily define functions with clear parameters and return values.
    

## How to Run Engage Code

This project includes a fully functional interpreter written in Python. To run an Engage program, you will need the three core Python files:

1.  `engage_lexer.py`
    
2.  `engage_parser.py`
    
3.  `engage_interpreter.py`
    

### Steps:

1.  **Save the Code:** Place the three Python files (`engage_lexer.py`, `engage_parser.py`, `engage_interpreter.py`) in the same directory.
    
2.  **Write Your Engage Program:** Create a string or a file containing your Engage code.
    
3.  **Run the Interpreter:** The main execution logic is in `engage_interpreter.py`. You can run it directly from your terminal.
    
    ```
    python engage_interpreter.py
    
    ```
    
    The script is pre-configured to run a sample Engage program defined within its `if __name__ == '__main__':` block.
    

### Running Your Own Code

To run your own code, modify the `engage_code` variable inside `engage_interpreter.py`:

```
# In engage_interpreter.py

if __name__ == '__main__':
    # --- Replace this with your Engage code ---
    engage_code = """
    to my_awesome_function:
        print with "This is my custom program!".
    end

    my_awesome_function.
    """
    # -----------------------------------------
    
    print("--- Running Engage Code ---")
    try:
        run(engage_code, global_symbol_table)
    except Exception as e:
        print(f"An error occurred: {e}")

```

## The Interpreter Pipeline

The interpreter works in three stages, which you can see in the `run()` function in `engage_interpreter.py`:

1.  **Lexing (`engage_lexer.py`):** The source code is scanned and broken down into a sequence of tokens (e.g., `KEYWORD`, `IDENTIFIER`, `NUMBER`).
    
2.  **Parsing (`engage_parser.py`):** The flat list of tokens is organized into a hierarchical **Abstract Syntax Tree (AST)**. The AST represents the grammatical structure of the code.
    
3.  **Evaluation (`engage_interpreter.py`):** The interpreter "walks" the AST, node by node, and executes the logic. It manages a **Symbol Table** to store variables and functions in their correct scopes.
    

## Near Future Development

Engage is a starting point. Here are some features that could be added next:

-   More complex data structures (Tables, Vectors, Records).
    
-   A standard library with more built-in functions.
    
-   Enhanced error reporting with line and column numbers.
    
-   Implementation of the UI Component and Game Object systems.
    
-   A proper module system for importing code from other files.


## Future Development Ideas

1. Vibe Coding and The Living Environment
This is the cornerstone of the Engage experience, designed to eliminate friction between idea and execution. The entire environment is built to provide immediate feedback and encourage experimentation.
Image-Based Persistence: The entire development environment—all code, objects, assets, and the program's current state—is saved into a single engage.image file. You don't "run" a program; you resume an image.
Live Coding and Debugging: Because the environment is always live, you can pause execution at any point, inspect any object, modify its state, rewrite a function's code, and then continue execution from that exact spot without restarting.
Hot Swapping of Assets: Instantly see changes by dragging new textures, sounds, or models into the running environment.
Intelligent and Context-Aware Tooling: The IDE is an active partner in the creative process.
"Pro-Vibe" Suggestions: Code completion offers context-aware help, such as popping up a color picker when defining a color variable or suggesting common event handlers.
"Code Sketchpad": A dedicated space for "doodling" with code snippets and testing ideas without affecting the main project.

2. Concurrency and Parallelism
Engage provides a simple yet powerful model for handling multiple operations at once.
Tasks and Channels:
Tasks: Lightweight, concurrent functions that are incredibly cheap to create and manage, making massive parallelism practical.
Channels: The primary method for safe communication between tasks, preventing data races and deadlocks by design.
Fibers: For cooperative multitasking, fibers are lightweight coroutines that can be paused and resumed explicitly. They are perfect for scripting complex, sequential logic like AI behavior or animations without blocking the main program.

3. Object-Oriented and Structural Programming
Engage offers a flexible and safe approach to structuring data and behavior.
Protocol-Oriented Programming: Define protocols as blueprints of methods and properties to create powerful abstractions without forcing a strict class hierarchy.
Powerful Records (Structs): Records are true value types that can have methods and implement protocols, encouraging safer, more predictable code by passing data by value.
Class-Based Objects and Messaging: For traditional OOP, Engage supports formal class structures. It also embraces the philosophy that "everything is a message," unifying the object model by having you send messages to objects rather than calling methods on them.

4. Metaprogramming and Extensibility
Reshape the language itself to fit your problem domain.
Syntactic Macros: A powerful macro system allows you to add new syntax to the language. Macros operate on the code's structure (the AST) during compilation, enabling the creation of highly expressive Domain-Specific Languages (DSLs) for tasks like dialogue systems, animation sequences, or custom UI layouts.
Context System: An implicit context system allows a scope to hold variables (like a custom memory allocator or logger) that are automatically passed to any function called within that scope, reducing boilerplate and making libraries more flexible.

5. Game Development and Graphics
Engage treats creative and interactive elements as first-class citizens.
Simple, High-Level API: A comprehensive, command-based standard library for 2D/3D graphics, physics, and input abstracts away low-level details.
Natively Supported 2D & 3D Graphics: Built-in commands and data types for sprites, shapes, text, particles, 3D models, skeletal animation, lighting, and ray casting.
Natively Supported Voxels: First-class support for voxel-based worlds, including efficient data structures and an optimized rendering engine.
High-Level Creative Abstractions:
Shaders as Native Functions: Write shaders directly in Engage using a specialized dialect, with the compiler handling the translation.
Built-in Tweening and Animation: An expressive, built-in syntax for creating smooth animations without manual frame-by-frame calculations.
First-Class Creative Types: Colors, vectors, and gradients are built-in types with intuitive operations (e.g., my_color darkened by 20%).

6. Visual and Interactive Environment
The visual environment is a direct, tangible representation of your code, designed for intuitive interaction.
Natively Supported Visual Scripting: A node-based visual scripting interface that is a direct, one-to-one representation of Engage's text-based code.
1:1 Bidirectional Syncing: Changes in the text editor are instantly reflected in the visual graph, and vice-versa.
Visual Scaffolding, Textual Refinement: Quickly "vibe out" the overall flow of a system by connecting nodes visually, then double-click a node to write the detailed logic in text.
Interactive Value Probes: See the actual data flowing through the connections between nodes as the program runs, making data flow tangible and easy to debug.
    

## Feel free to experiment, expand the syntax, and add new features to the interpreter!
