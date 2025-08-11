# engage_vm.py
import sys
import pickle
import os

# Import the full interpreter and its components
from engage_interpreter import run as run_interpreter, setup_global_environment, SymbolTable, EngageRuntimeError

IMAGE_FILENAME = "engage.image"

# --- Image Management ---
def bootstrap_image():
    """Creates a fresh, fully-featured symbol table by calling the main interpreter's setup."""
    print("Bootstrapping new image...")
    symbol_table = SymbolTable()
    setup_global_environment(symbol_table)
    return symbol_table

def save_image(symbol_table):
    """Saves the symbol table to the image file."""
    # Note: We can't pickle threads or complex non-serializable objects.
    # This is a limitation of the current image saving approach.
    # For now, we'll just pickle the symbol table, acknowledging this.
    try:
        with open(IMAGE_FILENAME, 'wb') as f:
            pickle.dump(symbol_table, f)
        print(f"Environment saved to {IMAGE_FILENAME}")
    except Exception as e:
        print(f"Warning: Could not save image file ({e}). Some state may not be serializable.", file=sys.stderr)

def load_image():
    """Loads the symbol table from the image file, or bootstraps a new one."""
    if not os.path.exists(IMAGE_FILENAME):
        return bootstrap_image()
    try:
        with open(IMAGE_FILENAME, 'rb') as f:
            symbol_table = pickle.load(f)
        print(f"Environment loaded from {IMAGE_FILENAME}")
        return symbol_table
    except Exception as e:
        print(f"Warning: Could not load image file ({e}). Starting fresh.", file=sys.stderr)
        return bootstrap_image()

# --- Main Execution Block (REPL) ---
def run(code_string, context, file_path="<stdin>"):
    """
    Runs code by delegating to the main interpreter.
    This function is used by the test suite and the REPL.
    """
    try:
        # We call the main `run_interpreter` function from engage_interpreter.py
        result = run_interpreter(code_string, context, file_path)
        return result
    except EngageRuntimeError as e:
        # The main interpreter already formats and prints the error,
        # but we print it here as well for visibility in the REPL.
        print(e.format_error(show_locals=False), file=sys.stderr)
        return None
    except Exception as e:
        print(f"An unexpected Python error occurred: {e}", file=sys.stderr)
        return None

if __name__ == '__main__':
    # When run as a script, this file provides a REPL.
    global_symbol_table = load_image()
    print("\nWelcome to the Engage Live Environment (Unified).")
    print("This REPL uses the full interpreter.")
    print("Type Engage code. To submit a multi-line block, enter a blank line.")
    print("Type '_run <filepath>' to execute a file.")
    print("Type '_save' to snapshot, or '_quit' to save and exit.")
    
    buffer = []
    
    while True:
        try:
            prompt = "engage> " if not buffer else "...     "
            line = input(prompt)

            if not buffer:
                if line.strip() == '_quit':
                    save_image(global_symbol_table)
                    break
                if line.strip() == '_save':
                    save_image(global_symbol_table)
                    continue
                if line.strip().startswith('_run '):
                    filepath = line.strip().split(' ', 1)[1]
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            file_code = f.read()
                        print(f"--- Running file: {filepath} ---")
                        run(file_code, global_symbol_table, file_path=filepath)
                        print(f"--- Finished file: {filepath} ---")
                    except FileNotFoundError:
                        print(f"Error: File not found at '{filepath}'", file=sys.stderr)
                    continue

            if not line.strip() and buffer:
                full_code = "\n".join(buffer)
                buffer = []
                result = run(full_code, global_symbol_table)
                if result is not None:
                    # The main interpreter returns Value objects, so we represent them.
                    print(repr(result))
                continue
            
            if line or buffer:
                 buffer.append(line)

        except KeyboardInterrupt:
            print("\nInterrupted. Use '_quit' to exit.")
            buffer = []
        except EOFError:
            save_image(global_symbol_table)
            break
