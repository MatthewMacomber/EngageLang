#!/usr/bin/env python3
"""
Engage Programming Language Launcher
Simple script to run Engage programs with the interpreter.
"""

import sys
import os
from engage_interpreter import main

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_engage.py <program.engage>")
        print("\nExample programs:")
        print("  python run_engage.py hello_world.engage")
        print("  python run_engage.py simple_math.engage")
        print("  python run_engage.py working_comprehensive_demo.engage")
        sys.exit(1)
    
    program_file = sys.argv[1]
    if not os.path.exists(program_file):
        print(f"Error: File '{program_file}' not found.")
        sys.exit(1)
    
    # Run the program
    main(program_file)