#!/usr/bin/env python3
"""
Engage v2 Package Test Script
Verifies that the core components work correctly.
"""

import sys
import os
import subprocess

def test_import():
    """Test that core modules can be imported."""
    print("Testing imports...")
    try:
        from engage_lexer import Lexer
        from engage_parser import Parser
        from engage_interpreter import Interpreter
        print("✅ Core modules import successfully")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_basic_functionality():
    """Test basic lexer and parser functionality."""
    print("Testing basic functionality...")
    try:
        from engage_lexer import Lexer
        from engage_parser import Parser
        
        # Test lexer
        code = 'let x be 5.'
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        
        # Test parser
        parser = Parser(tokens, source_text=code)
        ast = parser.parse()
        
        print("✅ Basic lexer and parser work correctly")
        return True
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        return False

def test_example_programs():
    """Test that example programs can be run."""
    print("Testing example programs...")
    
    examples = [
        "examples/hello_world.engage",
        "examples/simple_math.engage"
    ]
    
    success_count = 0
    for example in examples:
        if os.path.exists(example):
            try:
                # Test with interpreter
                result = subprocess.run([
                    sys.executable, "engage_interpreter.py", example
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    print(f"✅ {example} runs successfully")
                    success_count += 1
                else:
                    print(f"❌ {example} failed: {result.stderr}")
            except subprocess.TimeoutExpired:
                print(f"❌ {example} timed out")
            except Exception as e:
                print(f"❌ {example} error: {e}")
        else:
            print(f"❌ {example} not found")
    
    return success_count == len(examples)

def test_transpiler():
    """Test that the transpiler can generate C++ code."""
    print("Testing C++ transpiler...")
    
    example = "examples/hello_world.engage"
    if os.path.exists(example):
        try:
            result = subprocess.run([
                sys.executable, "engage_transpiler.py", example
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and os.path.exists("hello_world.cpp"):
                print("✅ C++ transpiler generates code successfully")
                # Clean up
                try:
                    os.remove("hello_world.cpp")
                except:
                    pass
                return True
            else:
                print(f"❌ Transpiler failed: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ Transpiler test error: {e}")
            return False
    else:
        print(f"❌ Example file {example} not found")
        return False

def main():
    """Run all tests."""
    print("Engage v2 Package Test")
    print("=" * 30)
    
    tests = [
        test_import,
        test_basic_functionality,
        test_example_programs,
        test_transpiler
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 30)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! Engage v2 package is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())