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
    

## Future Development

Engage is a starting point. Here are some features that could be added next:

-   More complex data structures (Tables, Vectors, Records).
    
-   A standard library with more built-in functions.
    
-   Enhanced error reporting with line and column numbers.
    
-   Implementation of the UI Component and Game Object systems.
    
-   A proper module system for importing code from other files.
    

Feel free to experiment, expand the syntax, and add new features to the interpreter!
