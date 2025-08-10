# engage_transpiler.py
# This script walks the AST and transpiles Engage code into C++ code.

import sys
import json
from engage_lexer import Lexer, Token
from engage_parser import Parser, ASTNode, ProgramNode, VarAssignNode, SetNode, VarAccessNode, BinOpNode, NumberNode, StringNode, FuncDefNode, FuncCallNode, ReturnNode, IfNode, UnaryOpNode, WhileNode, RecordDefNode, NewInstanceNode, MemberAccessNode, SelfNode

class TranspilerError(Exception):
    """
    Enhanced transpiler error with detailed context information.
    Provides comprehensive error reporting for transpilation failures.
    """
    def __init__(self, message, node=None, error_type="TranspilerError", suggestions=None):
        self.message = message
        self.node = node
        self.error_type = error_type
        self.suggestions = suggestions or []
        super().__init__(message)
    
    def add_suggestion(self, suggestion):
        """Add a helpful suggestion for resolving the error."""
        if suggestion not in self.suggestions:
            self.suggestions.append(suggestion)
    
    def format_error(self):
        """Format the error with context and suggestions."""
        lines = [f"{self.error_type}: {self.message}"]
        
        if self.node:
            # Add node context if available
            lines.append(f"  Context: {type(self.node).__name__}")
            if hasattr(self.node, 'name_token') and self.node.name_token:
                lines.append(f"  Name: {self.node.name_token.value}")
        
        if self.suggestions:
            lines.append("  Suggestions:")
            for suggestion in self.suggestions:
                lines.append(f"    • {suggestion}")
        
        return "\n".join(lines)

class Transpiler:
    """
    Enhanced transpiler with comprehensive language support infrastructure.
    
    Core Infrastructure:
    - Advanced multi-scope symbol table management
    - Function signature tracking and return type inference
    - Record definition tracking for custom types and methods
    - Comprehensive error handling framework with Result type support
    - Visitor pattern architecture for complete AST coverage
    - Sophisticated C++ code generation with proper scoping
    - Detailed error reporting with context and suggestions
    """
    def __init__(self):
        # Code generation sections
        self.main_code = ""              # Code for main() function body
        self.global_code = ""            # Headers, structs, global functions
        self.indent_level = 0            # Current indentation level for proper formatting
        self.current_scope_is_global = True  # Track current code generation scope
        
        # Error handling and reporting
        self.errors = []                 # List of transpiler errors
        self.warnings = []               # List of transpiler warnings
        self.unsupported_features = set() # Track unsupported features encountered
        
        # Enhanced symbol table management for multi-scope tracking
        self.symbol_table_stack = []     # Stack of symbol tables for nested scopes
        self.current_symbol_table = {}   # Current scope's symbol table
        self.global_symbol_table = {}    # Global scope symbol table
        
        # Function table for tracking function signatures and return types
        self.function_table = {}         # Function name -> FunctionSignature mapping
        
        # Record definition tracking for custom types and their methods
        self.record_definitions = {}     # Record name -> RecordDefinition mapping
        
        # Standard library function implementations
        self.stdlib_implementations = {} # Function name -> C++ implementation mapping
        
        # Error handling framework
        self.error_handling_enabled = True  # Enable Result type support
        self.result_type_used = False    # Track if Result types are used in code
        
        # Code generation state
        self.current_function_name = None  # Track current function being processed
        self.current_record_name = None    # Track current record being processed
        self.local_variable_counter = 0    # Counter for generating unique local variable names

    class FunctionSignature:
        """Represents a function signature with parameters and return type."""
        def __init__(self, name, parameters, return_type="auto", is_method=False, record_name=None):
            self.name = name
            self.parameters = parameters  # List of (param_name, param_type) tuples
            self.return_type = return_type
            self.is_method = is_method
            self.record_name = record_name  # For methods, the record they belong to
            self.is_builtin = False
            self.cpp_implementation = None  # Custom C++ implementation if needed
        
        def get_cpp_signature(self):
            """Generate C++ function signature."""
            param_list = []
            for param_name, param_type in self.parameters:
                param_list.append(f"{param_type} {param_name}")
            params_str = ", ".join(param_list)
            return f"{self.return_type} {self.name}({params_str})"
        
        def __repr__(self):
            return f"FunctionSignature({self.name}, params={self.parameters}, return={self.return_type})"

    class RecordDefinition:
        """Represents a record definition with properties and methods."""
        def __init__(self, name):
            self.name = name
            self.properties = {}  # Property name -> (type, default_value) mapping
            self.methods = {}     # Method name -> FunctionSignature mapping
            self.cpp_struct_generated = False
        
        def add_property(self, name, prop_type, default_value=None):
            """Add a property to the record."""
            self.properties[name] = (prop_type, default_value)
        
        def add_method(self, name, signature):
            """Add a method to the record."""
            self.methods[name] = signature
        
        def get_cpp_struct_name(self):
            """Get the C++ struct name for this record."""
            return f"Record_{self.name}"
        
        def __repr__(self):
            return f"RecordDefinition({self.name}, props={list(self.properties.keys())}, methods={list(self.methods.keys())})"

    def push_scope(self):
        """Push a new symbol table scope onto the stack."""
        self.symbol_table_stack.append(self.current_symbol_table.copy())
        self.current_symbol_table = {}
    
    def pop_scope(self):
        """Pop the current symbol table scope from the stack."""
        if self.symbol_table_stack:
            self.current_symbol_table = self.symbol_table_stack.pop()
        else:
            self.current_symbol_table = {}
    
    def add_symbol(self, name, cpp_type, scope="current"):
        """
        Add a variable to the appropriate symbol table with its C++ type.
        
        Args:
            name: Variable name
            cpp_type: C++ type (e.g., 'double', 'std::string', 'EngageValue')
            scope: 'current', 'global', or 'local'
        """
        if scope == "global":
            self.global_symbol_table[name] = cpp_type
        elif scope == "current":
            self.current_symbol_table[name] = cpp_type
        else:  # local scope
            self.current_symbol_table[name] = cpp_type

    def get_symbol_type(self, name):
        """
        Get the C++ type of a variable from the symbol table hierarchy.
        
        Searches current scope first, then parent scopes, then global scope.
        
        Args:
            name: Variable name
            
        Returns:
            C++ type string, or 'EngageValue' if not found (for dynamic typing)
        """
        # Check current scope
        if name in self.current_symbol_table:
            return self.current_symbol_table[name]
        
        # Check parent scopes (from most recent to oldest)
        for scope in reversed(self.symbol_table_stack):
            if name in scope:
                return scope[name]
        
        # Check global scope
        if name in self.global_symbol_table:
            return self.global_symbol_table[name]
        
        # Check if it's a known function
        if name in self.function_table:
            return "function"
        
        # Check if it's a known record type
        if name in self.record_definitions:
            return "record_type"
        
        # Default to EngageValue for dynamic typing support
        return "EngageValue"

    def add_function(self, name, parameters, return_type="auto", is_method=False, record_name=None):
        """
        Add a function signature to the function table.
        
        Args:
            name: Function name
            parameters: List of (param_name, param_type) tuples
            return_type: Return type (default: 'auto')
            is_method: Whether this is a method of a record
            record_name: Name of the record if this is a method
        """
        signature = self.FunctionSignature(name, parameters, return_type, is_method, record_name)
        self.function_table[name] = signature
        return signature

    def get_function_signature(self, name):
        """
        Get the function signature for a given function name.
        
        Args:
            name: Function name
            
        Returns:
            FunctionSignature object or None if not found
        """
        return self.function_table.get(name)

    def add_record_definition(self, name):
        """
        Add a new record definition.
        
        Args:
            name: Record name
            
        Returns:
            RecordDefinition object
        """
        record_def = self.RecordDefinition(name)
        self.record_definitions[name] = record_def
        return record_def

    def get_record_definition(self, name):
        """
        Get the record definition for a given record name.
        
        Args:
            name: Record name
            
        Returns:
            RecordDefinition object or None if not found
        """
        return self.record_definitions.get(name)

    def add_stdlib_implementation(self, name, cpp_code):
        """
        Add a C++ implementation for a standard library function.
        
        Args:
            name: Function name
            cpp_code: C++ implementation code
        """
        self.stdlib_implementations[name] = cpp_code

    def get_stdlib_implementation(self, name):
        """
        Get the C++ implementation for a standard library function.
        
        Args:
            name: Function name
            
        Returns:
            C++ implementation code or None if not found
        """
        return self.stdlib_implementations.get(name)

    def enable_result_types(self):
        """Enable Result type support for error handling."""
        self.error_handling_enabled = True
        self.result_type_used = True

    def generate_unique_variable_name(self, base_name="temp_var"):
        """
        Generate a unique variable name for temporary variables.
        
        Args:
            base_name: Base name for the variable
            
        Returns:
            Unique variable name
        """
        self.local_variable_counter += 1
        return f"{base_name}_{self.local_variable_counter}"

    def reset_transpiler_state(self):
        """Reset all transpiler state for fresh transpilation."""
        self.main_code = ""
        self.global_code = ""
        self.indent_level = 0
        self.current_scope_is_global = True
        
        # Reset symbol table management
        self.symbol_table_stack = []
        self.current_symbol_table = {}
        self.global_symbol_table = {}
        
        # Reset function and record tracking
        self.function_table = {}
        self.record_definitions = {}
        self.stdlib_implementations = {}
        
        # Reset error handling state
        self.error_handling_enabled = True
        self.result_type_used = False
        
        # Reset code generation state
        self.current_function_name = None
        self.current_record_name = None
        self.local_variable_counter = 0
        
        # Reset error tracking
        self.clear_errors()
    
    def add_error(self, message, node=None, error_type="TranspilerError", suggestions=None):
        """
        Add a transpiler error with detailed context information.
        
        Args:
            message: Error message describing the issue
            node: AST node where the error occurred (optional)
            error_type: Type of error (TranspilerError, UnsupportedFeature, etc.)
            suggestions: List of suggestions for resolving the error
        """
        error = TranspilerError(message, node, error_type, suggestions)
        self.errors.append(error)
        return error
    
    def add_warning(self, message, node=None, suggestions=None):
        """
        Add a transpiler warning for non-critical issues.
        
        Args:
            message: Warning message
            node: AST node where the warning occurred (optional)
            suggestions: List of suggestions for improvement
        """
        warning = TranspilerError(message, node, "Warning", suggestions)
        self.warnings.append(warning)
        return warning
    
    def add_unsupported_feature(self, feature_name, node=None, alternative=None):
        """
        Add an unsupported feature error with helpful information.
        
        Args:
            feature_name: Name of the unsupported feature
            node: AST node representing the unsupported feature
            alternative: Suggested alternative or workaround
        """
        self.unsupported_features.add(feature_name)
        
        suggestions = [
            f"The '{feature_name}' feature is not fully supported in C++ transpilation",
            "Consider using the Engage interpreter for full feature support"
        ]
        
        if alternative:
            suggestions.append(f"Alternative: {alternative}")
        
        return self.add_error(
            f"Unsupported feature: {feature_name}",
            node,
            "UnsupportedFeature",
            suggestions
        )
    
    def has_errors(self):
        """Check if any errors have been encountered."""
        return len(self.errors) > 0
    
    def has_warnings(self):
        """Check if any warnings have been encountered."""
        return len(self.warnings) > 0
    
    def get_error_summary(self):
        """Get a summary of errors and warnings."""
        error_count = len(self.errors)
        warning_count = len(self.warnings)
        unsupported_count = len(self.unsupported_features)
        
        summary = []
        if error_count > 0:
            summary.append(f"{error_count} error{'s' if error_count != 1 else ''}")
        if warning_count > 0:
            summary.append(f"{warning_count} warning{'s' if warning_count != 1 else ''}")
        if unsupported_count > 0:
            summary.append(f"{unsupported_count} unsupported feature{'s' if unsupported_count != 1 else ''}")
        
        return ", ".join(summary) if summary else "No issues found"
    
    def format_all_errors(self):
        """Format all errors and warnings for display."""
        lines = []
        
        if self.errors:
            lines.append("=== TRANSPILER ERRORS ===")
            for i, error in enumerate(self.errors, 1):
                lines.append(f"\nError {i}:")
                lines.append(error.format_error())
        
        if self.warnings:
            lines.append("\n=== TRANSPILER WARNINGS ===")
            for i, warning in enumerate(self.warnings, 1):
                lines.append(f"\nWarning {i}:")
                lines.append(warning.format_error())
        
        if self.unsupported_features:
            lines.append("\n=== UNSUPPORTED FEATURES ENCOUNTERED ===")
            for feature in sorted(self.unsupported_features):
                lines.append(f"  • {feature}")
        
        return "\n".join(lines)
    
    def clear_errors(self):
        """Clear all errors and warnings."""
        self.errors.clear()
        self.warnings.clear()
        self.unsupported_features.clear()

    def transpile(self, node):
        """
        Enhanced main transpilation orchestration method with comprehensive language support.
        
        This method implements the complete transpilation pipeline:
        1. Reset all transpiler state for fresh transpilation
        2. Initialize standard library function implementations
        3. Generate necessary C++ headers and includes
        4. Process the AST to generate global declarations and main function code
        5. Generate EngageValue union type and Result type if needed
        6. Create a complete C++ program structure with proper main() wrapper
        7. Handle and report any errors encountered during transpilation
        8. Return fully formatted, compilable C++ code or error information
        
        Requirements: 1.1, 9.1, 10.1, 10.2
        
        Args:
            node: Root AST node (typically ProgramNode) to transpile
            
        Returns:
            Tuple of (cpp_code, success, error_report)
            - cpp_code: Complete C++ program as a string (or partial code if errors)
            - success: Boolean indicating if transpilation was successful
            - error_report: Formatted error and warning report
        """
        try:
            # Reset all transpiler state for fresh transpilation
            self.reset_transpiler_state()
            
            # Initialize standard library function implementations
            self._initialize_stdlib_implementations()
            
            # Generate necessary C++ headers for the complete program structure
            self._generate_headers()
            
            # Generate EngageValue union type for dynamic typing support
            self._generate_engage_value_type()
            
            # Generate Result type if error handling is used
            if self.error_handling_enabled:
                self._generate_result_type()
            
            # Process the AST to generate code
            self.visit(node)
            
            # Generate all standard library function implementations used in the code
            self._generate_used_stdlib_functions()
            
            # Create the complete C++ program with proper main() function wrapper
            cpp_code = self._generate_complete_program()
            
            # Check for errors and warnings
            success = not self.has_errors()
            error_report = self._generate_transpilation_report()
            
            return cpp_code, success, error_report
            
        except TranspilerError as e:
            # Handle transpiler-specific errors
            error_report = self._generate_transpilation_report()
            partial_code = self._generate_partial_program()
            return partial_code, False, error_report
            
        except Exception as e:
            # Handle unexpected errors
            self.add_error(
                f"Unexpected error during transpilation: {str(e)}",
                None,
                "FatalError",
                [
                    "This is likely a bug in the transpiler",
                    "Try simplifying your Engage code",
                    "Report this issue with your code sample"
                ]
            )
            error_report = self._generate_transpilation_report()
            return "/* Transpilation failed */", False, error_report
    
    def _generate_transpilation_report(self):
        """
        Generate a comprehensive transpilation report with errors, warnings, and guidance.
        
        Returns:
            Formatted report string with all transpilation issues and suggestions
        """
        lines = []
        
        # Header
        lines.append("=== ENGAGE TO C++ TRANSPILATION REPORT ===")
        lines.append("")
        
        # Summary
        summary = self.get_error_summary()
        if summary == "No issues found":
            lines.append("✓ Transpilation completed successfully!")
            lines.append("")
            
            if self.warnings:
                lines.append("Note: Some warnings were generated (see below)")
                lines.append("")
        else:
            lines.append(f"⚠ Transpilation completed with issues: {summary}")
            lines.append("")
        
        # Detailed errors and warnings
        if self.has_errors() or self.has_warnings():
            detailed_report = self.format_all_errors()
            lines.append(detailed_report)
            lines.append("")
        
        # Compilation guidance (if successful or partial success)
        if not self.has_errors() or len(self.errors) < 5:  # Show guidance unless too many errors
            lines.append("=== COMPILATION GUIDANCE ===")
            lines.extend(self._generate_compilation_instructions())
        
        return "\n".join(lines)
    
    def _generate_compilation_instructions(self):
        """
        Generate clear compilation instructions for different C++ compilers.
        
        Requirements: 10.3, 10.4
        
        Returns:
            List of instruction lines for compiling the generated C++ code
        """
        instructions = []
        
        # Determine required C++ standard
        cpp_standard = "latest"  # Use latest C++ standard for best compatibility
        if self._uses_fiber_features():
            cpp_standard = "latest"  # C++latest required for coroutines
            instructions.append("Note: C++20 standard required for fiber/coroutine features")
        
        instructions.extend([
            "",
            "To compile the generated C++ code:",
            "",
            "=== Windows (Visual Studio) ===",
            f"cl /std:c++{cpp_standard} /EHsc output.cpp",
            "  or",
            f"cl /std:c++{cpp_standard} /EHsc /Fe:program.exe output.cpp",
            "",
            "=== Windows (MinGW/MSYS2) ===",
            f"g++ -std=c++{cpp_standard} -o program.exe output.cpp",
            "",
            "=== Linux/macOS (GCC) ===",
            f"g++ -std=c++{cpp_standard} -o program output.cpp",
            "",
            "=== Linux/macOS (Clang) ===",
            f"clang++ -std=c++{cpp_standard} -o program output.cpp",
            "",
            "=== Additional Compiler Flags (if needed) ===",
        ])
        
        # Threading flags
        if self._uses_concurrency_features():
            instructions.extend([
                "For threading support:",
                "  Linux/macOS: Add -pthread flag",
                "  Example: g++ -std=c++17 -pthread -o program output.cpp",
                ""
            ])
        
        # Optimization flags
        instructions.extend([
            "For optimized builds:",
            "  Add -O2 or -O3 for optimization",
            "  Add -DNDEBUG to disable debug assertions",
            "  Example: g++ -std=c++17 -O2 -DNDEBUG -o program output.cpp",
            "",
            "For debug builds:",
            "  Add -g for debug information",
            "  Add -Wall -Wextra for additional warnings",
            "  Example: g++ -std=c++17 -g -Wall -Wextra -o program output.cpp",
            ""
        ])
        
        # Troubleshooting
        instructions.extend([
            "=== TROUBLESHOOTING COMMON ISSUES ===",
            "",
            "If you get 'variant not found' errors:",
            "  • Ensure you're using C++17 or later (-std=c++17)",
            "  • Update your compiler to a recent version",
            "",
            "If you get 'coroutine not found' errors:",
            "  • Use C++20 standard (-std=c++20)",
            "  • Ensure your compiler supports C++20 coroutines",
            "",
            "If you get linking errors with threading:",
            "  • Add -pthread flag on Linux/macOS",
            "  • Ensure threading libraries are available",
            "",
            "If you get 'undefined reference' errors:",
            "  • Check that all required libraries are linked",
            "  • Verify that standard library headers are available",
            "",
            "For performance issues:",
            "  • Use optimization flags (-O2 or -O3)",
            "  • Consider the interpreter for complex features",
            ""
        ])
        
        # Feature-specific guidance
        if self.unsupported_features:
            instructions.extend([
                "=== UNSUPPORTED FEATURES ===",
                "",
                "The following features were encountered but are not fully supported:",
            ])
            for feature in sorted(self.unsupported_features):
                instructions.append(f"  • {feature}")
            instructions.extend([
                "",
                "For full feature support, use the Engage interpreter:",
                "  python engage_interpreter.py your_program.engage",
                ""
            ])
        
        return instructions
    
    def _generate_partial_program(self):
        """
        Generate a partial C++ program even when errors occurred.
        This helps users see what was successfully transpiled.
        """
        try:
            return self._generate_complete_program()
        except:
            # If complete program generation fails, return what we have
            return f"""// Partial C++ code (transpilation incomplete due to errors)
{self.global_code}

int main() {{
    // Main function code (may be incomplete)
{self.main_code}
    return 0;
}}"""
    
    def format_cpp_identifier(self, name):
        """
        Format an Engage identifier for safe use in C++.
        
        Args:
            name: Original identifier name
            
        Returns:
            C++-safe identifier name
        """
        # Replace spaces and special characters with underscores
        cpp_name = name.replace(' ', '_').replace('-', '_')
        
        # Ensure it starts with a letter or underscore
        if cpp_name and not (cpp_name[0].isalpha() or cpp_name[0] == '_'):
            cpp_name = f"var_{cpp_name}"
        
        # Handle C++ keywords
        cpp_keywords = {
            'auto', 'break', 'case', 'char', 'const', 'continue', 'default', 'do',
            'double', 'else', 'enum', 'extern', 'float', 'for', 'goto', 'if',
            'int', 'long', 'register', 'return', 'short', 'signed', 'sizeof', 'static',
            'struct', 'switch', 'typedef', 'union', 'unsigned', 'void', 'volatile', 'while',
            'class', 'namespace', 'template', 'typename', 'using', 'virtual', 'private',
            'protected', 'public', 'try', 'catch', 'throw', 'new', 'delete', 'this'
        }
        
        if cpp_name.lower() in cpp_keywords:
            cpp_name = f"engage_{cpp_name}"
        
        return cpp_name
    
    def _generate_headers(self):
        """
        Generate comprehensive C++ includes and headers for full language support.
        
        Includes all necessary C++ standard library headers for complete Engage language features:
        - iostream: for print statements and I/O operations
        - string: for string operations and concatenation
        - vector: for Vector data structure
        - map: for Table data structure
        - algorithm: for sorting and collection operations
        - cmath: for mathematical functions
        - random: for random number generation
        - stdexcept: for error handling and exceptions
        - sstream: for string conversion utilities
        - memory: for smart pointers and memory management
        - functional: for function objects and lambdas
        - variant: for EngageValue union type (C++17)
        - optional: for None value handling (C++17)
        - type_traits: for template metaprogramming
        - utility: for std::move, std::forward, etc.
        - thread, queue, mutex: for concurrency features
        - coroutine: for fiber/coroutine support (C++20)
        
        Requirements: 9.1, 9.2, 10.1
        """
        # Add file header comment
        self.add_line("// Generated C++ code from Engage transpiler", global_scope=True)
        self.add_line("// Requires C++17 standard minimum, C++20 preferred for full feature support", global_scope=True)
        self.add_line("", global_scope=True)
        
        # Core C++ standard library headers - essential for basic functionality
        core_headers = [
            "#include <iostream>",      # I/O operations, cout, cin
            "#include <string>",        # String class and operations
            "#include <vector>",        # Dynamic arrays for Vector type
            "#include <map>",           # Hash maps for Table type
            "#include <algorithm>",     # Sorting, searching, transformations
            "#include <cmath>",         # Mathematical functions
            "#include <ctime>",         # Time functions for random seed
            "#include <random>",        # Random number generation
            "#include <stdexcept>",     # Standard exceptions
            "#include <sstream>",       # String stream operations
            "#include <memory>",        # Smart pointers
            "#include <functional>",    # Function objects, lambdas
            ""
        ]
        
        # C++17/C++20 feature headers - required for advanced type system
        modern_cpp_headers = [
            "#include <variant>",       # C++17: Union types for EngageValue
            "#include <optional>",      # C++17: None value handling
            "#include <type_traits>",   # Template metaprogramming
            "#include <utility>",       # std::move, std::forward
            "#include <any>",           # C++17: Type-erased value storage
            ""
        ]
        
        # Threading headers for concurrency support
        concurrency_headers = [
            "#include <thread>",        # Thread creation and management
            "#include <queue>",         # Queue for channel implementation
            "#include <mutex>",         # Mutual exclusion
            "#include <condition_variable>",  # Thread synchronization
            "#include <future>",        # Async operations
            "#include <atomic>",        # Atomic operations
            ""
        ]
        
        # C++20 coroutine headers for fiber support
        coroutine_headers = [
            "#include <coroutine>",     # C++20: Coroutine support
            ""
        ]
        
        # Generate core headers (always included)
        for header in core_headers:
            self.add_line(header, global_scope=True)
        
        # Generate modern C++ headers (always included for type system)
        for header in modern_cpp_headers:
            self.add_line(header, global_scope=True)
        
        # Add threading headers for concurrency support
        if self._uses_concurrency_features():
            self.add_line("// Threading headers for concurrency features", global_scope=True)
            for header in concurrency_headers:
                self.add_line(header, global_scope=True)
        
        # Add C++20 coroutine headers if fiber features are used
        if self._uses_fiber_features():
            self.add_line("// C++20 coroutine headers for fiber support", global_scope=True)
            for header in coroutine_headers:
                self.add_line(header, global_scope=True)
        
        # Add using declarations for common std types to improve code readability
        self.add_line("// Using declarations for common standard library types", global_scope=True)
        using_declarations = [
            "using std::string;",
            "using std::cout;",
            "using std::cin;",
            "using std::endl;", 
            "using std::vector;",
            "using std::map;",
            "using std::variant;",
            "using std::optional;",
            "using std::unique_ptr;",
            "using std::shared_ptr;",
            "using std::make_unique;",
            "using std::make_shared;",
            ""
        ]
        
        for declaration in using_declarations:
            self.add_line(declaration, global_scope=True)

    def _uses_concurrency_features(self):
        """
        Check if the code uses concurrency features that require threading headers.
        
        Analyzes the transpiler state to determine if concurrency features are used,
        including channels, tasks, concurrent execution, and message passing.
        
        Returns:
            bool: True if concurrency features are detected, False otherwise
        """
        # Check if any concurrency-related functions are in the function table
        concurrency_functions = {
            'create_channel', 'send', 'receive', 'run_concurrently', 
            'create_task', 'wait_for_task', 'channel_close'
        }
        
        for func_name in concurrency_functions:
            if func_name in self.function_table:
                return True
        
        # Check if any concurrency-related standard library implementations are used
        for func_name in concurrency_functions:
            if func_name in self.stdlib_implementations:
                return True
        
        # For comprehensive support, include threading headers by default
        # This ensures compatibility with potential concurrency features
        return True

    def _uses_fiber_features(self):
        """
        Check if the code uses fiber/coroutine features that require C++20 headers.
        
        Analyzes the transpiler state to determine if fiber or coroutine features are used,
        including fiber definitions, yield statements, and cooperative multitasking.
        
        Returns:
            bool: True if fiber features are detected, False otherwise
        """
        # Check if any fiber-related functions are in the function table
        fiber_functions = {
            'create_fiber', 'yield', 'resume_fiber', 'fiber_finished',
            'fiber_value', 'run_fiber'
        }
        
        for func_name in fiber_functions:
            if func_name in self.function_table:
                return True
        
        # Check if any fiber-related standard library implementations are used
        for func_name in fiber_functions:
            if func_name in self.stdlib_implementations:
                return True
        
        # Check if any record definitions contain fiber-related methods
        for record_name, record_def in self.record_definitions.items():
            for method_name in record_def.methods:
                if any(fiber_func in method_name.lower() for fiber_func in ['yield', 'fiber', 'resume']):
                    return True
        
        # For comprehensive support, include coroutine headers by default
        # This ensures compatibility with potential fiber features
        return True

    def _generate_channel_struct(self):
        """
        Generate the EngageChannel struct for basic concurrency support.
        
        Creates a thread-safe queue-based channel implementation using std::queue and std::mutex.
        This is a simplified implementation with limitations compared to full Engage channels.
        
        Requirements: 8.1, 10.4
        """
        channel_struct_code = '''
// EngageChannel: Simplified channel implementation for basic concurrency
// WARNING: This is not equivalent to the full Engage channel system
class EngageChannel {
private:
    std::queue<EngageValue> queue_;
    std::mutex mutex_;
    std::condition_variable condition_;
    bool closed_ = false;

public:
    // Send a value to the channel (non-blocking)
    void send(const EngageValue& value) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!closed_) {
            queue_.push(value);
            condition_.notify_one();
        }
    }
    
    // Receive a value from the channel (blocking)
    EngageValue receive() {
        std::unique_lock<std::mutex> lock(mutex_);
        condition_.wait(lock, [this] { return !queue_.empty() || closed_; });
        
        if (queue_.empty() && closed_) {
            return EngageValue(); // Return None/empty value
        }
        
        EngageValue value = queue_.front();
        queue_.pop();
        return value;
    }
    
    // Close the channel
    void close() {
        std::lock_guard<std::mutex> lock(mutex_);
        closed_ = true;
        condition_.notify_all();
    }
    
    // Check if channel is empty
    bool empty() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return queue_.empty();
    }
    
    // Get queue size
    size_t size() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return queue_.size();
    }
};
'''
        self.add_line(channel_struct_code, global_scope=True)

    def _generate_fiber_struct(self):
        """
        Generate the EngageFiber base class for basic coroutine support.
        
        Creates a simplified fiber/coroutine implementation using basic C++ patterns.
        This is a simplified implementation with limitations compared to full Engage fibers.
        
        Requirements: 8.2, 10.4
        """
        fiber_struct_code = '''
// EngageFiber: Simplified fiber/coroutine implementation
// WARNING: This is not equivalent to the full Engage fiber system
class EngageFiber {
protected:
    bool finished_ = false;
    EngageValue current_value_;
    
public:
    virtual ~EngageFiber() = default;
    
    // Run the fiber (simplified - runs to completion)
    virtual EngageValue run() = 0;
    
    // Check if fiber is finished
    bool is_finished() const { return finished_; }
    
    // Get current value
    EngageValue get_current_value() const { return current_value_; }
    
    // Resume fiber (simplified implementation)
    EngageValue resume() {
        if (!finished_) {
            current_value_ = run();
            finished_ = true; // Simplified - fiber runs to completion
        }
        return current_value_;
    }
};
'''
        self.add_line(fiber_struct_code, global_scope=True)

    def _initialize_stdlib_implementations(self):
        """
        Initialize C++ implementations for all Engage standard library functions.
        
        This method sets up the mapping between Engage stdlib functions and their
        C++ equivalents, enabling comprehensive language feature support.
        
        Requirements: 6.1, 6.2, 6.3, 6.4
        """
        # String manipulation functions
        self.add_stdlib_implementation("trim", """
string engage_trim(const string& str) {
    size_t start = str.find_first_not_of(" \\t\\n\\r");
    if (start == string::npos) return "";
    size_t end = str.find_last_not_of(" \\t\\n\\r");
    return str.substr(start, end - start + 1);
}""")
        
        self.add_stdlib_implementation("to_upper", """
string engage_to_upper(const string& str) {
    string result = str;
    std::transform(result.begin(), result.end(), result.begin(), ::toupper);
    return result;
}""")
        
        self.add_stdlib_implementation("to_lower", """
string engage_to_lower(const string& str) {
    string result = str;
    std::transform(result.begin(), result.end(), result.begin(), ::tolower);
    return result;
}""")
        
        self.add_stdlib_implementation("split", """
vector<string> engage_split(const string& str, const string& delimiter) {
    vector<string> result;
    size_t start = 0;
    size_t end = str.find(delimiter);
    while (end != string::npos) {
        result.push_back(str.substr(start, end - start));
        start = end + delimiter.length();
        end = str.find(delimiter, start);
    }
    result.push_back(str.substr(start));
    return result;
}""")
        
        self.add_stdlib_implementation("string_length", """
size_t engage_string_length(const string& str) {
    return str.length();
}""")
        
        # Mathematical functions
        self.add_stdlib_implementation("sqrt", """
double engage_sqrt(double x) {
    return std::sqrt(x);
}""")
        
        self.add_stdlib_implementation("pow", """
double engage_pow(double base, double exp) {
    return std::pow(base, exp);
}""")
        
        self.add_stdlib_implementation("abs", """
double engage_abs(double x) {
    return std::abs(x);
}""")
        
        self.add_stdlib_implementation("min", """
double engage_min(double a, double b) {
    return std::min(a, b);
}""")
        
        self.add_stdlib_implementation("max", """
double engage_max(double a, double b) {
    return std::max(a, b);
}""")
        
        self.add_stdlib_implementation("floor", """
double engage_floor(double x) {
    return std::floor(x);
}""")
        
        self.add_stdlib_implementation("ceil", """
double engage_ceil(double x) {
    return std::ceil(x);
}""")
        
        self.add_stdlib_implementation("round", """
double engage_round(double x) {
    return std::round(x);
}""")
        
        self.add_stdlib_implementation("random", """
double engage_random() {
    static std::random_device rd;
    static std::mt19937 gen(rd());
    static std::uniform_real_distribution<double> dis(0.0, 1.0);
    return dis(gen);
}""")
        
        # Collection manipulation functions
        self.add_stdlib_implementation("sort", """
void engage_sort(vector<EngageValue>& vec) {
    std::sort(vec.begin(), vec.end(), [](const EngageValue& a, const EngageValue& b) {
        return a.as_number() < b.as_number();
    });
}""")
        
        self.add_stdlib_implementation("keys", """
vector<string> engage_keys(const map<string, EngageValue>& table) {
    vector<string> result;
    for (const auto& pair : table) {
        result.push_back(pair.first);
    }
    return result;
}""")
        
        self.add_stdlib_implementation("values", """
vector<EngageValue> engage_values(const map<string, EngageValue>& table) {
    vector<EngageValue> result;
    for (const auto& pair : table) {
        result.push_back(pair.second);
    }
    return result;
}""")
        
        self.add_stdlib_implementation("vector_push", """
void engage_vector_push(vector<EngageValue>& vec, const EngageValue& value) {
    vec.push_back(value);
}""")
        
        self.add_stdlib_implementation("vector_pop", """
EngageValue engage_vector_pop(vector<EngageValue>& vec) {
    if (vec.empty()) {
        throw std::runtime_error("Cannot pop from empty vector");
    }
    EngageValue result = vec.back();
    vec.pop_back();
    return result;
}""")
        
        self.add_stdlib_implementation("vector_length", """
size_t engage_vector_length(const vector<EngageValue>& vec) {
    return vec.size();
}""")
        
        self.add_stdlib_implementation("table_size", """
size_t engage_table_size(const map<string, EngageValue>& table) {
    return table.size();
}""")
        
        self.add_stdlib_implementation("table_has_key", """
bool engage_table_has_key(const map<string, EngageValue>& table, const string& key) {
    return table.find(key) != table.end();
}""")
        
        # Type checking functions
        self.add_stdlib_implementation("type_of", """
string engage_type_of(const EngageValue& value) {
    return value.type_name();
}""")
        
        self.add_stdlib_implementation("check_number", """
bool engage_check_number(const EngageValue& value) {
    return value.is_number();
}""")
        
        self.add_stdlib_implementation("check_string", """
bool engage_check_string(const EngageValue& value) {
    return value.is_string();
}""")
        
        self.add_stdlib_implementation("check_vector", """
bool engage_check_vector(const EngageValue& value) {
    return value.is_vector();
}""")
        
        self.add_stdlib_implementation("check_table", """
bool engage_check_table(const EngageValue& value) {
    return value.is_table();
}""")
        
        self.add_stdlib_implementation("check_record", """
bool engage_check_record(const EngageValue& value) {
    return value.is_record();
}""")
        
        self.add_stdlib_implementation("is_none", """
bool engage_is_none(const EngageValue& value) {
    return value.is_none();
}""")
        
        # Add function signatures to function table
        self.add_function("trim", [("str", "string")], "string")
        self.add_function("to_upper", [("str", "string")], "string")
        self.add_function("to_lower", [("str", "string")], "string")
        self.add_function("split", [("str", "string"), ("delimiter", "string")], "vector<string>")
        self.add_function("string_length", [("str", "string")], "size_t")
        self.add_function("sqrt", [("x", "double")], "double")
        self.add_function("pow", [("base", "double"), ("exp", "double")], "double")
        self.add_function("abs", [("x", "double")], "double")
        self.add_function("min", [("a", "double"), ("b", "double")], "double")
        self.add_function("max", [("a", "double"), ("b", "double")], "double")
        self.add_function("floor", [("x", "double")], "double")
        self.add_function("ceil", [("x", "double")], "double")
        self.add_function("round", [("x", "double")], "double")
        self.add_function("random", [], "double")
        self.add_function("sort", [("vec", "vector<EngageValue>&")], "void")
        self.add_function("keys", [("table", "map<string, EngageValue>")], "vector<string>")
        self.add_function("values", [("table", "map<string, EngageValue>")], "vector<EngageValue>")
        self.add_function("vector_push", [("vec", "vector<EngageValue>&"), ("value", "EngageValue")], "void")
        self.add_function("vector_pop", [("vec", "vector<EngageValue>&")], "EngageValue")
        self.add_function("vector_length", [("vec", "vector<EngageValue>")], "size_t")
        self.add_function("table_size", [("table", "map<string, EngageValue>")], "size_t")
        self.add_function("table_has_key", [("table", "map<string, EngageValue>"), ("key", "string")], "bool")
        self.add_function("type_of", [("value", "EngageValue")], "string")
        self.add_function("check_number", [("value", "EngageValue")], "bool")
        self.add_function("check_string", [("value", "EngageValue")], "bool")
        self.add_function("check_vector", [("value", "EngageValue")], "bool")
        self.add_function("check_table", [("value", "EngageValue")], "bool")
        self.add_function("check_record", [("value", "EngageValue")], "bool")
        self.add_function("is_none", [("value", "EngageValue")], "bool")
        
        # Game object function stubs - simplified implementations with limitations
        # Requirements: 8.3, 10.4
        self.add_stdlib_implementation("create_game_object", """
// WARNING: Simplified game object implementation - not equivalent to full Engage game system
struct EngageGameObject {
    static int next_id;
    int id;
    string object_type;
    double x = 0.0, y = 0.0;
    string sprite_path;
    int sprite_width = 0, sprite_height = 0;
    vector<string> tags;
    
    EngageGameObject(const string& type = "GameObject") 
        : id(++next_id), object_type(type) {}
};
int EngageGameObject::next_id = 0;

EngageGameObject* engage_create_game_object(const string& type = "GameObject") {
    return new EngageGameObject(type);
}""")
        
        self.add_stdlib_implementation("game_set_position", """
EngageGameObject* engage_game_set_position(EngageGameObject* obj, double x, double y) {
    if (obj) {
        obj->x = x;
        obj->y = y;
    }
    return obj;
}""")
        
        self.add_stdlib_implementation("game_set_sprite", """
EngageGameObject* engage_game_set_sprite(EngageGameObject* obj, const string& sprite_path, int width, int height) {
    if (obj) {
        obj->sprite_path = sprite_path;
        obj->sprite_width = width;
        obj->sprite_height = height;
    }
    return obj;
}""")
        
        self.add_stdlib_implementation("game_add_tag", """
EngageGameObject* engage_game_add_tag(EngageGameObject* obj, const string& tag) {
    if (obj) {
        obj->tags.push_back(tag);
    }
    return obj;
}""")
        
        self.add_stdlib_implementation("game_check_collision", """
bool engage_game_check_collision(EngageGameObject* obj1, EngageGameObject* obj2) {
    if (!obj1 || !obj2) return false;
    
    // Simplified bounding box collision detection
    // Assumes objects have 32x32 default size if sprite size not set
    int w1 = obj1->sprite_width > 0 ? obj1->sprite_width : 32;
    int h1 = obj1->sprite_height > 0 ? obj1->sprite_height : 32;
    int w2 = obj2->sprite_width > 0 ? obj2->sprite_width : 32;
    int h2 = obj2->sprite_height > 0 ? obj2->sprite_height : 32;
    
    return (obj1->x < obj2->x + w2 &&
            obj1->x + w1 > obj2->x &&
            obj1->y < obj2->y + h2 &&
            obj1->y + h1 > obj2->y);
}""")
        
        self.add_stdlib_implementation("game_find_objects_by_tag", """
vector<EngageGameObject*> engage_game_find_objects_by_tag(const string& tag) {
    // WARNING: This is a stub implementation
    // In a full game engine, this would search a global object registry
    vector<EngageGameObject*> result;
    // TODO: Implement proper object registry and tag-based search
    return result;
}""")
        
        # Add game object function signatures to function table
        self.add_function("create_game_object", [("type", "string")], "EngageGameObject*")
        self.add_function("game_set_position", [("obj", "EngageGameObject*"), ("x", "double"), ("y", "double")], "EngageGameObject*")
        self.add_function("game_set_sprite", [("obj", "EngageGameObject*"), ("sprite_path", "string"), ("width", "int"), ("height", "int")], "EngageGameObject*")
        self.add_function("game_add_tag", [("obj", "EngageGameObject*"), ("tag", "string")], "EngageGameObject*")
        self.add_function("game_check_collision", [("obj1", "EngageGameObject*"), ("obj2", "EngageGameObject*")], "bool")
        self.add_function("game_find_objects_by_tag", [("tag", "string")], "vector<EngageGameObject*>")
        
        # UI component function stubs - simplified implementations with limitations
        # Requirements: 8.4, 10.4
        self.add_stdlib_implementation("create_panel", """
// WARNING: Simplified UI component implementation - not equivalent to full Engage UI system
struct EngageUIComponent {
    static int next_id;
    int id;
    string component_type;
    map<string, EngageValue> properties;
    vector<EngageUIComponent*> children;
    EngageUIComponent* parent = nullptr;
    
    EngageUIComponent(const string& type) 
        : id(++next_id), component_type(type) {
        // Set default properties
        properties["x"] = EngageValue(0.0);
        properties["y"] = EngageValue(0.0);
        properties["width"] = EngageValue(100.0);
        properties["height"] = EngageValue(100.0);
        properties["visible"] = EngageValue(1.0); // true
    }
};
int EngageUIComponent::next_id = 0;

EngageUIComponent* engage_create_panel() {
    return new EngageUIComponent("Panel");
}""")
        
        self.add_stdlib_implementation("create_label", """
EngageUIComponent* engage_create_label(const string& text) {
    EngageUIComponent* label = new EngageUIComponent("Label");
    label->properties["text"] = EngageValue(text);
    label->properties["width"] = EngageValue(200.0);
    label->properties["height"] = EngageValue(30.0);
    return label;
}""")
        
        self.add_stdlib_implementation("create_button", """
EngageUIComponent* engage_create_button(const string& text) {
    EngageUIComponent* button = new EngageUIComponent("Button");
    button->properties["text"] = EngageValue(text);
    button->properties["width"] = EngageValue(100.0);
    button->properties["height"] = EngageValue(30.0);
    return button;
}""")
        
        self.add_stdlib_implementation("ui_set_property", """
void engage_ui_set_property(EngageUIComponent* component, const string& property_name, const EngageValue& value) {
    if (component) {
        component->properties[property_name] = value;
    }
}""")
        
        self.add_stdlib_implementation("ui_add_child", """
void engage_ui_add_child(EngageUIComponent* parent, EngageUIComponent* child) {
    if (parent && child) {
        parent->children.push_back(child);
        child->parent = parent;
    }
}""")
        
        # Add UI component function signatures to function table
        self.add_function("create_panel", [], "EngageUIComponent*")
        self.add_function("create_label", [("text", "string")], "EngageUIComponent*")
        self.add_function("create_button", [("text", "string")], "EngageUIComponent*")
        self.add_function("ui_set_property", [("component", "EngageUIComponent*"), ("property_name", "string"), ("value", "EngageValue")], "void")
        self.add_function("ui_add_child", [("parent", "EngageUIComponent*"), ("child", "EngageUIComponent*")], "void")
    
    def _generate_engage_value_type(self):
        """
        Generate the EngageValue union type for dynamic typing support.
        
        Creates a comprehensive variant type that can hold all Engage value types
        with proper type checking and conversion methods.
        
        Requirements: 9.3, 6.4
        """
        engage_value_code = '''
// EngageValue union type for dynamic typing support
class EngageValue {
public:
    enum Type { NUMBER, STRING, VECTOR, TABLE, RECORD, FUNCTION, NONE };
    
private:
    Type type_;
    variant<double, string, vector<EngageValue>, map<string, EngageValue>, void*> value_;
    
public:
    // Constructors
    EngageValue() : type_(NONE) {}
    EngageValue(double val) : type_(NUMBER), value_(val) {}
    EngageValue(const string& val) : type_(STRING), value_(val) {}
    EngageValue(const char* val) : type_(STRING), value_(string(val)) {}
    EngageValue(const vector<EngageValue>& val) : type_(VECTOR), value_(val) {}
    EngageValue(const map<string, EngageValue>& val) : type_(TABLE), value_(val) {}
    
    // Copy constructor
    EngageValue(const EngageValue& other) : type_(other.type_), value_(other.value_) {}
    
    // Move constructor
    EngageValue(EngageValue&& other) noexcept : type_(other.type_), value_(std::move(other.value_)) {
        other.type_ = NONE;
    }
    
    // Assignment operators
    EngageValue& operator=(const EngageValue& other) {
        if (this != &other) {
            type_ = other.type_;
            value_ = other.value_;
        }
        return *this;
    }
    
    EngageValue& operator=(EngageValue&& other) noexcept {
        if (this != &other) {
            type_ = other.type_;
            value_ = std::move(other.value_);
            other.type_ = NONE;
        }
        return *this;
    }
    
    // Type checking methods
    bool is_number() const { return type_ == NUMBER; }
    bool is_string() const { return type_ == STRING; }
    bool is_vector() const { return type_ == VECTOR; }
    bool is_table() const { return type_ == TABLE; }
    bool is_record() const { return type_ == RECORD; }
    bool is_function() const { return type_ == FUNCTION; }
    bool is_none() const { return type_ == NONE; }
    
    // Type conversion methods
    double as_number() const {
        if (type_ == NUMBER) return std::get<double>(value_);
        if (type_ == STRING) {
            try { return std::stod(std::get<string>(value_)); }
            catch (...) { return 0.0; }
        }
        return 0.0;
    }
    
    string as_string() const {
        if (type_ == STRING) return std::get<string>(value_);
        if (type_ == NUMBER) {
            double val = std::get<double>(value_);
            if (val == static_cast<int>(val)) {
                return std::to_string(static_cast<int>(val));
            }
            return std::to_string(val);
        }
        if (type_ == NONE) return "None";
        return "<object>";
    }
    
    string to_string() const { return as_string(); }
    
    // Truthiness evaluation for conditional expressions
    bool is_truthy() const {
        switch (type_) {
            case NUMBER: return std::get<double>(value_) != 0.0;
            case STRING: return !std::get<string>(value_).empty();
            case VECTOR: return !std::get<vector<EngageValue>>(value_).empty();
            case TABLE: return !std::get<map<string, EngageValue>>(value_).empty();
            case NONE: return false;
            default: return true;
        }
    }
    
    // Type name for debugging and type_of function
    string type_name() const {
        switch (type_) {
            case NUMBER: return "Number";
            case STRING: return "String";
            case VECTOR: return "Vector";
            case TABLE: return "Table";
            case RECORD: return "Record";
            case FUNCTION: return "Function";
            case NONE: return "None";
            default: return "Unknown";
        }
    }
    
    // Arithmetic operators
    EngageValue operator+(const EngageValue& other) const {
        if (is_string() || other.is_string()) {
            return EngageValue(as_string() + other.as_string());
        }
        return EngageValue(as_number() + other.as_number());
    }
    
    EngageValue operator-(const EngageValue& other) const {
        return EngageValue(as_number() - other.as_number());
    }
    
    EngageValue operator*(const EngageValue& other) const {
        return EngageValue(as_number() * other.as_number());
    }
    
    EngageValue operator/(const EngageValue& other) const {
        double divisor = other.as_number();
        if (divisor == 0.0) throw std::runtime_error("Division by zero");
        return EngageValue(as_number() / divisor);
    }
    
    // Comparison operators
    bool operator==(const EngageValue& other) const {
        if (type_ != other.type_) return false;
        switch (type_) {
            case NUMBER: return std::get<double>(value_) == std::get<double>(other.value_);
            case STRING: return std::get<string>(value_) == std::get<string>(other.value_);
            case NONE: return true;
            default: return false;
        }
    }
    
    bool operator!=(const EngageValue& other) const { return !(*this == other); }
    bool operator<(const EngageValue& other) const { return as_number() < other.as_number(); }
    bool operator>(const EngageValue& other) const { return as_number() > other.as_number(); }
    bool operator<=(const EngageValue& other) const { return as_number() <= other.as_number(); }
    bool operator>=(const EngageValue& other) const { return as_number() >= other.as_number(); }
    
    // Stream output operator for debugging
    friend std::ostream& operator<<(std::ostream& os, const EngageValue& val) {
        os << val.as_string();
        return os;
    }
};

'''
        self.add_line(engage_value_code, global_scope=True)

    def _generate_result_type(self):
        """
        Generate the Result type template for error handling support.
        
        Creates a Result<T> template class that can hold either a success value
        or an error message, enabling robust error propagation.
        
        Requirements: 7.1, 7.2
        """
        result_type_code = '''
// Result type template for error handling
template<typename T>
class Result {
private:
    bool is_ok_;
    T value_;
    string error_message_;
    
public:
    // Static factory methods
    static Result<T> Ok(const T& value) {
        Result<T> result;
        result.is_ok_ = true;
        result.value_ = value;
        return result;
    }
    
    static Result<T> Error(const string& message) {
        Result<T> result;
        result.is_ok_ = false;
        result.error_message_ = message;
        return result;
    }
    
    // State checking methods
    bool is_ok() const { return is_ok_; }
    bool is_error() const { return !is_ok_; }
    
    // Value access methods
    T value() const {
        if (!is_ok_) {
            throw std::runtime_error("Attempted to access value of error result: " + error_message_);
        }
        return value_;
    }
    
    string error() const {
        if (is_ok_) {
            throw std::runtime_error("Attempted to access error of ok result");
        }
        return error_message_;
    }
    
    // Convenience methods
    T value_or(const T& default_value) const {
        return is_ok_ ? value_ : default_value;
    }
    
private:
    Result() : is_ok_(false) {}
};

'''
        self.add_line(result_type_code, global_scope=True)

    def _generate_used_stdlib_functions(self):
        """
        Generate C++ implementations for all standard library functions used in the code.
        
        Only generates implementations for functions that are actually referenced
        in the transpiled code to keep the output minimal.
        
        Requirements: 6.1, 6.2, 6.3, 6.4
        """
        self.add_comment("Standard library function implementations", global_scope=True)
        self.add_blank_line(global_scope=True)
        
        # Generate implementations for functions found in the function table
        for func_name, signature in self.function_table.items():
            if not signature.is_builtin and func_name in self.stdlib_implementations:
                implementation = self.get_stdlib_implementation(func_name)
                if implementation:
                    self.add_line(implementation, global_scope=True)
                    self.add_blank_line(global_scope=True)

    def _generate_complete_program(self):
        """
        Create the comprehensive complete C++ program structure with full language support.
        
        This method orchestrates the generation of a complete, compilable C++ program by
        combining all generated components in the correct order:
        
        1. File header with compilation information
        2. All necessary C++ standard library includes
        3. Forward declarations for complex types
        4. EngageValue union type for dynamic typing
        5. Result type template for error handling (if used)
        6. Standard library function implementations
        7. Record/struct definitions with methods
        8. Global function definitions
        9. Main function with comprehensive error handling and program logic
        10. Program cleanup and termination
        
        Requirements: 9.1, 9.4, 10.2
        
        Returns:
            Complete C++ program string ready for compilation with cl, g++, or clang++
        """
        # Start building the complete program structure
        complete_program = ""
        
        # Add the global code section (headers, types, functions, etc.)
        if self.global_code:
            complete_program += self.global_code
        
        # Ensure proper spacing before main function
        if not complete_program.endswith('\n\n'):
            complete_program += "\n"
        
        # Generate the main function with comprehensive structure
        main_function = self._generate_main_function()
        complete_program += main_function
        
        return complete_program
    
    def _generate_main_function(self):
        """
        Generate a comprehensive main() function with proper error handling and initialization.
        
        Creates a robust main function that includes:
        - Program initialization comments
        - Exception handling wrapper
        - Proper indentation for transpiled code
        - Comprehensive error reporting
        - Clean program termination
        
        Requirements: 9.4, 10.2
        
        Returns:
            Complete main function as a string
        """
        main_lines = []
        
        # Function signature and opening
        main_lines.append("int main() {")
        main_lines.append("    // =================================================================")
        main_lines.append("    // Main function - Transpiled from Engage language")
        main_lines.append("    // Generated with comprehensive language feature support")
        main_lines.append("    // Requires C++17 standard minimum, C++20 preferred")
        main_lines.append("    // =================================================================")
        main_lines.append("")
        
        # Program initialization section
        main_lines.append("    // Program initialization")
        main_lines.append("    try {")
        main_lines.append("        // Initialize random number generator")
        main_lines.append("        // Note: std::time requires #include <ctime>")
        main_lines.append("        std::srand(static_cast<unsigned int>(std::time(nullptr)));")
        main_lines.append("")
        
        # Add the main program logic with proper indentation
        if self.main_code.strip():
            main_lines.append("        // Begin transpiled program logic")
            main_lines.append("        // ----------------------------------------")
            
            # Process each line of main code and add proper indentation
            for line in self.main_code.split('\n'):
                if line.strip():
                    # Add two levels of indentation (try block + main function)
                    main_lines.append("        " + line)
                else:
                    # Preserve empty lines
                    main_lines.append("")
            
            main_lines.append("")
            main_lines.append("        // End transpiled program logic")
            main_lines.append("        // ----------------------------------------")
        else:
            # If no main code, add informative comment
            main_lines.append("        // No main program logic to execute")
            main_lines.append("        cout << \"Engage program executed successfully (no operations)\" << endl;")
        
        # Comprehensive exception handling
        main_lines.append("")
        main_lines.append("    } catch (const std::runtime_error& e) {")
        main_lines.append("        std::cerr << \"Runtime Error: \" << e.what() << endl;")
        main_lines.append("        std::cerr << \"Program terminated due to runtime error.\" << endl;")
        main_lines.append("        return 1;")
        main_lines.append("    } catch (const std::logic_error& e) {")
        main_lines.append("        std::cerr << \"Logic Error: \" << e.what() << endl;")
        main_lines.append("        std::cerr << \"Program terminated due to logic error.\" << endl;")
        main_lines.append("        return 2;")
        main_lines.append("    } catch (const std::bad_alloc& e) {")
        main_lines.append("        std::cerr << \"Memory Error: \" << e.what() << endl;")
        main_lines.append("        std::cerr << \"Program terminated due to memory allocation failure.\" << endl;")
        main_lines.append("        return 3;")
        main_lines.append("    } catch (const std::exception& e) {")
        main_lines.append("        std::cerr << \"Standard Exception: \" << e.what() << endl;")
        main_lines.append("        std::cerr << \"Program terminated due to standard exception.\" << endl;")
        main_lines.append("        return 4;")
        main_lines.append("    } catch (...) {")
        main_lines.append("        std::cerr << \"Unknown Error: An unhandled exception occurred.\" << endl;")
        main_lines.append("        std::cerr << \"Program terminated due to unknown error.\" << endl;")
        main_lines.append("        return 5;")
        main_lines.append("    }")
        main_lines.append("")
        
        # Program cleanup and successful termination
        main_lines.append("    // Program completed successfully")
        main_lines.append("    return 0;")
        main_lines.append("}")
        main_lines.append("")
        
        # Add compilation instructions as comments
        main_lines.append("/*")
        main_lines.append("Compilation Instructions:")
        main_lines.append("========================")
        main_lines.append("")
        main_lines.append("Windows (Visual Studio):")
        main_lines.append("  cl /EHsc /std:c++17 program.cpp")
        main_lines.append("  cl /EHsc /std:c++20 program.cpp  (preferred for full feature support)")
        main_lines.append("")
        main_lines.append("Linux/macOS (GCC):")
        main_lines.append("  g++ -std=c++17 -o program program.cpp")
        main_lines.append("  g++ -std=c++20 -o program program.cpp  (preferred for full feature support)")
        main_lines.append("")
        main_lines.append("Linux/macOS (Clang):")
        main_lines.append("  clang++ -std=c++17 -o program program.cpp")
        main_lines.append("  clang++ -std=c++20 -o program program.cpp  (preferred for full feature support)")
        main_lines.append("")
        main_lines.append("For threading support, add -pthread flag on Linux/macOS:")
        main_lines.append("  g++ -std=c++17 -pthread -o program program.cpp")
        main_lines.append("*/")
        
        return '\n'.join(main_lines)

    def add_line(self, line, global_scope=False, extra_indent=0):
        """
        Enhanced method for comprehensive indentation management and code formatting.
        
        Provides sophisticated code formatting with proper indentation handling,
        automatic brace management, comment formatting, and scope-aware code generation.
        
        Features:
        - Automatic indentation based on current nesting level
        - Smart handling of opening/closing braces
        - Proper comment formatting and alignment
        - Empty line handling without unnecessary indentation
        - Extra indentation support for special cases
        - Consistent spacing and formatting
        
        Requirements: 9.2, 10.3
        
        Args:
            line: The code line to add
            global_scope: If True, adds to global_code; otherwise adds to main_code
            extra_indent: Additional indentation levels to apply
        """
        # Handle empty lines without indentation
        if not line.strip():
            formatted_line = "\n"
        else:
            # Calculate total indentation level
            total_indent_level = self.indent_level + extra_indent
            
            # Handle special indentation cases for braces
            line_stripped = line.strip()
            
            # Decrease indentation for closing braces
            if line_stripped.startswith('}') and total_indent_level > 0:
                total_indent_level -= 1
            
            # Apply proper indentation
            indent = "    " * total_indent_level
            formatted_line = indent + line_stripped + "\n"
            
            # Increase indentation for opening braces (for next line)
            if line_stripped.endswith('{'):
                # This will affect the next line's indentation
                pass
        
        # Add to appropriate code section based on scope
        if global_scope or self.current_scope_is_global:
            self.global_code += formatted_line
        else:
            self.main_code += formatted_line
    
    def add_block(self, lines, global_scope=False, with_braces=False, block_comment=None):
        """
        Add multiple lines of code as a properly formatted block with consistent indentation.
        
        Provides comprehensive block formatting with optional brace handling,
        comment headers, and automatic indentation management for code blocks.
        
        Features:
        - Consistent indentation for all lines in the block
        - Optional automatic brace wrapping
        - Block comment headers for documentation
        - Proper spacing and formatting
        - Scope-aware code generation
        
        Requirements: 9.2, 10.3
        
        Args:
            lines: List of code lines to add
            global_scope: If True, adds to global_code; otherwise adds to main_code
            with_braces: If True, wrap the block in braces with proper indentation
            block_comment: Optional comment to add before the block
        """
        # Add block comment if provided
        if block_comment:
            self.add_comment(block_comment, global_scope)
        
        # Add opening brace if requested
        if with_braces:
            self.add_line("{", global_scope)
            self.indent_level += 1
        
        # Add all lines in the block
        for line in lines:
            if isinstance(line, str):
                self.add_line(line, global_scope)
            elif isinstance(line, list):
                # Handle nested blocks
                self.add_block(line, global_scope)
        
        # Add closing brace if requested
        if with_braces:
            self.indent_level -= 1
            self.add_line("}", global_scope)
    
    def add_comment(self, comment, global_scope=False, style="single"):
        """
        Add a formatted comment line with proper indentation and styling.
        
        Provides comprehensive comment formatting with multiple styles,
        proper indentation, and consistent formatting for code documentation.
        
        Requirements: 9.2, 10.3
        
        Args:
            comment: Comment text (without // prefix)
            global_scope: If True, adds to global_code; otherwise adds to main_code
            style: Comment style ("single", "block", "inline")
        """
        if style == "single":
            self.add_line(f"// {comment}", global_scope)
        elif style == "block":
            self.add_line(f"/* {comment} */", global_scope)
        elif style == "inline":
            # For inline comments, don't add newline (caller handles it)
            return f" // {comment}"
        else:
            self.add_line(f"// {comment}", global_scope)
    
    def add_multiline_comment(self, lines, global_scope=False):
        """
        Add a multi-line comment block with proper formatting.
        
        Creates well-formatted multi-line comment blocks for comprehensive
        code documentation and explanations.
        
        Requirements: 9.2, 10.3
        
        Args:
            lines: List of comment lines (without // prefix)
            global_scope: If True, adds to global_code; otherwise adds to main_code
        """
        self.add_line("/*", global_scope)
        for line in lines:
            self.add_line(f" * {line}", global_scope)
        self.add_line(" */", global_scope)
    
    def add_blank_line(self, global_scope=False):
        """
        Add a blank line for code formatting and readability.
        
        Utility for improving code structure and readability by adding
        appropriate spacing between code sections.
        
        Requirements: 9.2, 10.3
        
        Args:
            global_scope: If True, adds to global_code; otherwise adds to main_code
        """
        self.add_line("", global_scope)
    
    def begin_block(self, opening_line=None, global_scope=False):
        """
        Begin a new code block with proper brace handling and indentation.
        
        Manages the opening of code blocks with automatic indentation increase,
        proper brace placement, and scope tracking for nested structures.
        
        Requirements: 9.2, 10.3
        
        Args:
            opening_line: Optional line to add before opening brace (e.g., "if (condition)")
            global_scope: If True, adds to global_code; otherwise adds to main_code
        """
        if opening_line:
            self.add_line(f"{opening_line} {{", global_scope)
        else:
            self.add_line("{", global_scope)
        self.indent_level += 1
    
    def end_block(self, global_scope=False, closing_comment=None):
        """
        End a code block with proper brace handling and indentation.
        
        Manages the closing of code blocks with automatic indentation decrease,
        proper brace placement, and optional closing comments for clarity.
        
        Requirements: 9.2, 10.3
        
        Args:
            global_scope: If True, adds to global_code; otherwise adds to main_code
            closing_comment: Optional comment to add after closing brace
        """
        self.indent_level = max(0, self.indent_level - 1)
        if closing_comment:
            self.add_line(f"}} // {closing_comment}", global_scope)
        else:
            self.add_line("}", global_scope)
    
    def add_section_header(self, title, global_scope=False, style="double"):
        """
        Add a formatted section header comment for code organization.
        
        Creates visually distinct section headers to improve code readability
        and organization in the generated C++ code.
        
        Requirements: 9.2, 10.3
        
        Args:
            title: Section title text
            global_scope: If True, adds to global_code; otherwise adds to main_code
            style: Header style ("single", "double", "box")
        """
        if style == "double":
            separator = "=" * (len(title) + 4)
            self.add_line(f"// {separator}", global_scope)
            self.add_line(f"// {title.upper()}", global_scope)
            self.add_line(f"// {separator}", global_scope)
        elif style == "single":
            separator = "-" * (len(title) + 4)
            self.add_line(f"// {separator}", global_scope)
            self.add_line(f"// {title}", global_scope)
            self.add_line(f"// {separator}", global_scope)
        elif style == "box":
            width = max(len(title) + 4, 40)
            border = "*" * width
            padding = " " * ((width - len(title) - 2) // 2)
            self.add_line(f"/* {border} */", global_scope)
            self.add_line(f"/* {padding}{title}{padding} */", global_scope)
            self.add_line(f"/* {border} */", global_scope)
        
        self.add_blank_line(global_scope)
    
    def format_cpp_identifier(self, name):
        """
        Format an Engage identifier for use in C++ code.
        
        Ensures that Engage variable and function names are properly formatted
        for C++ compilation, handling any naming conflicts or reserved words.
        
        Requirements: 3.2, 3.4
        
        Args:
            name: Original Engage identifier
            
        Returns:
            C++ compatible identifier
        """
        # Handle C++ reserved words by adding prefix
        cpp_reserved = {
            'class', 'struct', 'int', 'double', 'float', 'char', 'bool',
            'if', 'else', 'while', 'for', 'do', 'switch', 'case', 'default',
            'break', 'continue', 'return', 'void', 'const', 'static',
            'public', 'private', 'protected', 'virtual', 'override',
            'namespace', 'using', 'template', 'typename', 'auto'
        }
        
        if name.lower() in cpp_reserved:
            return f"engage_{name}"
        
        # Replace any invalid characters with underscores
        import re
        formatted = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        
        # Ensure it starts with a letter or underscore
        if formatted and formatted[0].isdigit():
            formatted = f"var_{formatted}"
        
        return formatted or "unnamed_var"
    
    def format_string_literal(self, value):
        """
        Format a string value as a proper C++ string literal.
        
        Handles proper escaping of special characters and ensures the string
        is formatted correctly for C++ compilation.
        
        Requirements: 3.2, 3.4
        
        Args:
            value: String value to format
            
        Returns:
            Properly escaped C++ string literal
        """
        # Escape special characters for C++
        escaped = value.replace('\\', '\\\\')  # Escape backslashes first
        escaped = escaped.replace('"', '\\"')   # Escape double quotes
        escaped = escaped.replace('\n', '\\n')  # Escape newlines
        escaped = escaped.replace('\t', '\\t')  # Escape tabs
        escaped = escaped.replace('\r', '\\r')  # Escape carriage returns
        
        return f'"{escaped}"'
    
    def generate_type_conversion(self, value_cpp, from_type, to_type):
        """
        Generate appropriate C++ type conversion code.
        
        Creates proper type conversion expressions for mixed-type operations,
        ensuring type safety and proper formatting in the generated C++ code.
        
        Requirements: 3.2, 3.4
        
        Args:
            value_cpp: C++ expression to convert
            from_type: Source type
            to_type: Target type
            
        Returns:
            C++ expression with appropriate type conversion
        """
        if from_type == to_type:
            return value_cpp
        
        # Number to string conversion with better formatting
        if from_type == 'double' and to_type == 'string':
            # Use integer formatting for whole numbers, decimal for others
            return f"std::to_string(static_cast<int>({value_cpp}))"
        
        # String to number conversion
        if from_type == 'string' and to_type == 'double':
            return f"std::stod({value_cpp})"
        
        # Boolean to string conversion
        if from_type == 'bool' and to_type == 'string':
            return f"({value_cpp} ? \"true\" : \"false\")"
        
        # Default: attempt direct conversion
        return f"static_cast<{to_type}>({value_cpp})"
    
    def add_function_header(self, func_name, parameters, return_type, global_scope=True, comment=None):
        """
        Add a properly formatted function header with documentation.
        
        Creates well-formatted function declarations with proper spacing,
        parameter formatting, and optional documentation comments.
        
        Requirements: 9.2, 10.3
        
        Args:
            func_name: Function name
            parameters: List of (param_name, param_type) tuples
            return_type: Function return type
            global_scope: If True, adds to global_code; otherwise adds to main_code
            comment: Optional function description comment
        """
        if comment:
            self.add_comment(comment, global_scope)
        
        # Format parameters
        if parameters:
            param_strs = [f"{param_type} {param_name}" for param_name, param_type in parameters]
            params = ", ".join(param_strs)
        else:
            params = ""
        
        # Add function signature
        self.add_line(f"{return_type} {func_name}({params}) {{", global_scope)
        self.indent_level += 1
    
    def add_struct_header(self, struct_name, global_scope=True, comment=None):
        """
        Add a properly formatted struct/class header with documentation.
        
        Creates well-formatted struct declarations with proper spacing
        and optional documentation comments.
        
        Requirements: 9.2, 10.3
        
        Args:
            struct_name: Struct/class name
            global_scope: If True, adds to global_code; otherwise adds to main_code
            comment: Optional struct description comment
        """
        if comment:
            self.add_comment(comment, global_scope)
        
        self.add_line(f"struct {struct_name} {{", global_scope)
        self.indent_level += 1
    
    def ensure_proper_spacing(self, global_scope=False):
        """
        Ensure proper spacing in the generated code.
        
        Adds appropriate blank lines to improve code readability and structure,
        avoiding excessive blank lines while maintaining good formatting.
        
        Requirements: 9.2, 10.3
        
        Args:
            global_scope: If True, affects global_code; otherwise affects main_code
        """
        target_code = self.global_code if (global_scope or self.current_scope_is_global) else self.main_code
        
        # Only add blank line if the last line isn't already blank
        if target_code and not target_code.endswith('\n\n'):
            self.add_blank_line(global_scope)
    
    def format_variable_declaration(self, var_name, var_type, initial_value=None):
        """
        Format a variable declaration with proper C++ syntax.
        
        Creates properly formatted variable declarations with type information,
        initialization, and consistent formatting.
        
        Requirements: 9.2, 10.3
        
        Args:
            var_name: Variable name
            var_type: Variable type
            initial_value: Optional initial value
            
        Returns:
            Formatted variable declaration string
        """
        if initial_value is not None:
            return f"{var_type} {var_name} = {initial_value};"
        else:
            return f"{var_type} {var_name};"
    
    def format_assignment(self, var_name, value):
        """
        Format an assignment statement with proper C++ syntax.
        
        Creates properly formatted assignment statements with consistent
        spacing and formatting.
        
        Requirements: 9.2, 10.3
        
        Args:
            var_name: Variable name
            value: Value to assign
            
        Returns:
            Formatted assignment statement string
        """
        return f"{var_name} = {value};"

    def indent(self):
        """Increase indentation level for proper code formatting."""
        self.indent_level += 1

    def dedent(self):
        """Decrease indentation level for proper code formatting."""
        if self.indent_level > 0:
            self.indent_level -= 1

    def _process_statement(self, statement):
        """
        Process a statement, handling both regular expressions and control flow constructs.
        
        Control flow statements (if, while) require special handling as they generate
        multiple lines of C++ code with proper block structure and indentation.
        
        Args:
            statement: AST node representing the statement to process
        """
        if isinstance(statement, IfNode):
            self._process_if_statement(statement)
        elif isinstance(statement, WhileNode):
            self._process_while_statement(statement)
        else:
            # Regular expression statement - generate single line with semicolon
            line, _ = self.visit(statement)
            if line:
                self.add_line(line + ";")

    def _process_if_statement(self, node):
        """
        Process if-then-otherwise-end statements with proper C++ if-else generation.
        
        Handles multiple condition cases with proper else-if chaining and generates
        proper C++ if-else constructs with correct scoping and indentation.
        
        Requirements: 2.1, 2.3
        
        Args:
            node: IfNode AST node containing cases and else_case
        """
        # Process each condition case
        for i, (condition, body) in enumerate(node.cases):
            # Generate condition expression
            condition_cpp, _ = self.visit(condition)
            
            # Generate if/else if statement
            if i == 0:
                self.add_line(f"if (({condition_cpp}).is_truthy()) {{")
            else:
                self.add_line(f"else if (({condition_cpp}).is_truthy()) {{")
            
            # Process body statements with proper indentation
            self.indent()
            for body_statement in body:
                self._process_statement(body_statement)
            self.dedent()
            self.add_line("}")
        
        # Process else case if present
        if node.else_case:
            self.add_line("else {")
            self.indent()
            for else_statement in node.else_case:
                self._process_statement(else_statement)
            self.dedent()
            self.add_line("}")

    def _process_while_statement(self, node):
        """
        Process while loop statements with proper C++ while loop generation.
        
        Generates C++ while loops with proper condition evaluation and handles
        loop body statements with correct variable scoping.
        
        Requirements: 2.1, 2.3
        
        Args:
            node: WhileNode AST node containing condition_node and body_nodes
        """
        # Generate condition expression
        condition_cpp, _ = self.visit(node.condition_node)
        
        # Generate while loop header
        self.add_line(f"while (({condition_cpp}).is_truthy()) {{")
        
        # Process body statements with proper indentation
        self.indent()
        for body_statement in node.body_nodes:
            self._process_statement(body_statement)
        self.dedent()
        self.add_line("}")

    def visit(self, node):
        """
        Visitor pattern dispatcher - routes AST nodes to appropriate visitor methods.
        
        This is the core of the visitor pattern architecture, dynamically calling
        the correct visit_* method based on the node type. Enhanced with comprehensive
        error handling and context tracking.
        
        Args:
            node: AST node to visit
            
        Returns:
            Tuple of (cpp_code, type_info) from the specific visitor method
        """
        try:
            method_name = f'visit_{type(node).__name__}'
            method = getattr(self, method_name, self.no_visit_method)
            return method(node)
        except TranspilerError:
            # Re-raise transpiler errors as-is
            raise
        except Exception as e:
            # Convert other exceptions to transpiler errors with context
            self.add_error(
                f"Internal error while processing {type(node).__name__}: {str(e)}",
                node,
                "InternalError",
                [
                    "This may be a bug in the transpiler",
                    "Try simplifying the code around this area",
                    "Report this issue if it persists"
                ]
            )
            raise TranspilerError(f"Internal error processing {type(node).__name__}", node)

    def no_visit_method(self, node):
        """
        Fallback method for unsupported AST node types.
        Provides clear error messaging and suggestions for missing visitor implementations.
        """
        node_type = type(node).__name__
        
        # Check if this is a known unsupported feature
        unsupported_features = {
            'TaskNode': ('concurrency tasks', 'Use the Engage interpreter for full concurrency support'),
            'ChannelNode': ('channels', 'Use the Engage interpreter for channel-based communication'),
            'SendNode': ('channel send operations', 'Use the Engage interpreter for message passing'),
            'ReceiveNode': ('channel receive operations', 'Use the Engage interpreter for message passing'),
            'FiberDefNode': ('fiber definitions', 'Use the Engage interpreter for cooperative multitasking'),
            'YieldNode': ('yield statements', 'Use the Engage interpreter for fiber support'),
            'ImportNode': ('import statements', 'Manually include required code or use the interpreter'),
            'FromImportNode': ('from-import statements', 'Manually include required code or use the interpreter'),
            'ExportVarNode': ('variable exports', 'Use global variables or the interpreter'),
            'ExportFuncNode': ('function exports', 'Use global functions or the interpreter')
        }
        
        if node_type in unsupported_features:
            feature_name, alternative = unsupported_features[node_type]
            self.add_unsupported_feature(feature_name, node, alternative)
            return "/* Unsupported feature */", "void"
        
        # For truly unknown node types
        suggestions = [
            f"The {node_type} AST node is not supported in C++ transpilation",
            "Check if this is a new language feature that needs implementation",
            "Consider using the Engage interpreter for full language support",
            f"If needed, add a visit_{node_type} method to the transpiler"
        ]
        
        self.add_error(
            f"Unsupported AST node type: {node_type}",
            node,
            "UnsupportedNode",
            suggestions
        )
        
        return "/* Unsupported node */", "void"

    # --- Visitor Methods ---

    def visit_ProgramNode(self, node):
        for statement in node.statements:
            if isinstance(statement, (RecordDefNode, FuncDefNode)):
                self.visit(statement)

        self.current_scope_is_global = False
        self.indent()
        for statement in node.statements:
            if not isinstance(statement, (RecordDefNode, FuncDefNode)):
                self._process_statement(statement)
        self.dedent()
        return None, "Void"


    def visit_NumberNode(self, node):
        if isinstance(node.value, float) and node.value.is_integer():
            return f"{int(node.value)}.0", "double"
        return str(node.value), "double"

    def visit_StringNode(self, node):
        escaped_value = node.value.replace('"', '\\"')
        return f'std::string("{escaped_value}")', "std::string"

    def visit_VarAssignNode(self, node):
        """
        Handle variable assignment with enhanced type tracking and scoping.
        
        Uses the enhanced symbol table to track variable types across scopes
        and generates appropriate C++ variable declarations.
        
        Requirements: 2.1, 9.1, 9.3
        """
        var_name = node.name_token.value
        value_cpp, value_type = self.visit(node.value_node)
        
        # Format variable name for C++ compatibility
        cpp_var_name = self.format_cpp_identifier(var_name)
        
        # Add to appropriate symbol table scope
        scope = "global" if self.current_scope_is_global else "current"
        self.add_symbol(var_name, value_type, scope)
        
        # Generate C++ variable declaration
        return f"{value_type} {cpp_var_name} = {value_cpp}", "Void"

    def visit_SetNode(self, node):
        """
        Handle variable assignment (set statements) with enhanced type tracking.
        
        Updates existing variables or creates new ones with proper type tracking
        across the enhanced symbol table hierarchy.
        
        Requirements: 2.1, 9.1, 9.3
        """
        target_cpp, _ = self.visit(node.target_node)
        value_cpp, value_type = self.visit(node.value_node)
        
        # Update symbol table if this is a simple variable assignment
        if isinstance(node.target_node, VarAccessNode):
            var_name = node.target_node.name_token.value
            scope = "global" if self.current_scope_is_global else "current"
            self.add_symbol(var_name, value_type, scope)
        
        return f"{target_cpp} = {value_cpp}", "Void"

    def visit_VarAccessNode(self, node):
        """
        Handle variable references using enhanced multi-scope symbol table lookup.
        
        Uses the enhanced symbol table hierarchy to determine the correct C++ type
        and generates appropriate C++ variable access code with proper scoping.
        Implements None value representation using EngageValue with NONE type.
        
        Requirements: 2.1, 3.3, 7.4, 9.1
        """
        var_name = node.name_token.value
        
        # Handle None as a special literal value
        if var_name == "None":
            return self._handle_none_value_creation()
        
        var_type = self.get_symbol_type(var_name)
        
        # Format the variable name for C++ compatibility
        cpp_var_name = self.format_cpp_identifier(var_name)
        
        # Check if it's a known function
        if var_type == "function":
            return cpp_var_name, "function"
        
        # Check if it's a known record type
        if var_type == "record_type":
            return cpp_var_name, "record_type"
        
        # For built-in functions, use the original name
        if var_name in ['print', 'input', 'number']:
            return var_name, "function"
        
        # Return the formatted variable name and its tracked type
        return cpp_var_name, var_type

    def visit_BinOpNode(self, node):
        """
        Handle binary operations including arithmetic, string operations, and error propagation.
        
        Implements automatic type conversion for mixed string/number operations,
        handles the 'concatenated with' keyword for string concatenation,
        and implements "or return error" construct transpilation for error propagation.
        
        Requirements: 2.2, 2.4, 7.1, 7.3
        """
        op = node.op_token.value
        
        # Handle 'or return error' construct specially - implement error propagation
        if op == 'or return error':
            return self._handle_error_propagation(node.left_node)
        
        # Handle error type checking operations
        if op in ['is an Error', 'is an Ok']:
            return self._handle_error_type_checking(node.left_node, op)
        
        # Handle 'is an' with TypeNameNode (Error or Ok)
        if op == 'is an' and hasattr(node.right_node, 'type_token'):
            type_name = node.right_node.type_token.value
            if type_name in ['Error', 'Ok']:
                full_op = f'is an {type_name}'
                return self._handle_error_type_checking(node.left_node, full_op)
        
        # For all other operations, evaluate both operands
        left_cpp, left_type = self.visit(node.left_node)
        right_cpp, right_type = self.visit(node.right_node)

        # Map Engage operators to C++ operators
        op_map = {
            'plus': '+', 'minus': '-', 'times': '*', 'divided by': '/',
            'is': "==", 'is equal to': "==", 'is not': "!=", 'is greater than': ">", 'is less than': "<",
            'and': "&&", 'or': "||"
        }
        
        # Handle string concatenation with 'concatenated with' keyword
        if op == 'concatenated with':
            # Convert numbers to strings for concatenation with better formatting
            if left_type == 'double':
                left_cpp = f"std::to_string(static_cast<int>({left_cpp}))"
            if right_type == 'double':
                right_cpp = f"std::to_string(static_cast<int>({right_cpp}))"
            
            return f"({left_cpp} + {right_cpp})", "std::string"
        
        # Handle mixed string/number operations with 'plus' (automatic string concatenation)
        if op == 'plus' and (left_type == 'std::string' or right_type == 'std::string'):
            # Automatic type conversion for mixed string/number operations with better formatting
            if left_type == 'double':
                left_cpp = f"std::to_string(static_cast<int>({left_cpp}))"
            if right_type == 'double':
                right_cpp = f"std::to_string(static_cast<int>({right_cpp}))"
            
            return f"({left_cpp} + {right_cpp})", "std::string"

        # Handle comparison operations (return bool type)
        if op in ['is', 'is equal to', 'is not', 'is greater than', 'is less than']:
            # Special handling for None comparisons
            if (left_type == "EngageValue" and right_type == "EngageValue"):
                # Use EngageValue comparison operators
                cpp_op = op_map.get(op, op)
                return f"({left_cpp} {cpp_op} {right_cpp})", "bool"
            else:
                cpp_op = op_map.get(op, op)
                return f"({left_cpp} {cpp_op} {right_cpp})", "bool"
        
        # Handle logical operations (return bool type)
        if op in ['and', 'or']:
            cpp_op = op_map.get(op, op)
            return f"({left_cpp} {cpp_op} {right_cpp})", "bool"

        # Handle arithmetic operations (return double type)
        cpp_op = op_map.get(op, op)
        if cpp_op != op:  # If we found a mapping
            return f"({left_cpp} {cpp_op} {right_cpp})", "double"
        else:
            # Unsupported operation
            raise Exception(f"Unsupported binary operation: '{op}'. "
                           f"Supported operations are: {', '.join(op_map.keys())}, 'concatenated with', 'or return error', 'is an Error', 'is an Ok', 'is an'")

    def _handle_error_propagation(self, left_node):
        """
        Handle "or return error" construct transpilation.
        
        Implements error propagation by generating early return statements
        for error conditions. Handles error checking and value extraction
        from Result types with proper error message forwarding and context preservation.
        
        Requirements: 7.1, 7.3
        
        Args:
            left_node: The left operand AST node to evaluate
            
        Returns:
            Tuple of (cpp_code, cpp_type) for the error propagation construct
        """
        # Enable Result type usage
        self.enable_result_types()
        
        # Generate a unique temporary variable name
        temp_var = self.generate_unique_variable_name("temp_result")
        
        # Evaluate the left operand
        left_cpp, left_type = self.visit(left_node)
        
        # Generate error checking and early return code
        if left_type.startswith("Result<"):
            # Extract the inner type from Result<T>
            inner_type = left_type[7:-1]  # Remove "Result<" and ">"
            
            # Generate the error propagation code
            error_check_code = f"""auto {temp_var} = {left_cpp};
if ({temp_var}.is_error()) {{
    return Result<{inner_type}>::Error({temp_var}.error());
}}
auto {temp_var}_value = {temp_var}.value()"""
            
            # Add the error checking code to the current scope
            self.add_line(error_check_code)
            
            # Return the extracted value
            return f"{temp_var}_value", inner_type
        else:
            # If the left operand is not a Result type, just return it as-is
            # This handles cases where non-Result values are used with "or return error"
            return left_cpp, left_type

    def _handle_error_type_checking(self, left_node, op):
        """
        Handle error type checking operations like "is an Error" and "is an Ok".
        
        Generates C++ error condition checks without evaluating the right operand.
        
        Requirements: 7.1
        
        Args:
            left_node: The left operand AST node to check
            op: The operation ('is an Error' or 'is an Ok')
            
        Returns:
            Tuple of (cpp_code, cpp_type) for the error type check
        """
        # Evaluate the left operand
        left_cpp, left_type = self.visit(left_node)
        
        if left_type.startswith("Result<"):
            if op == 'is an Error':
                return f"({left_cpp}.is_error())", "bool"
            elif op == 'is an Ok':
                return f"({left_cpp}.is_ok())", "bool"
        else:
            # For non-Result types, they are never Error results
            if op == 'is an Error':
                return "false", "bool"
            elif op == 'is an Ok':
                return "true", "bool"
        
        return "false", "bool"

    def _handle_none_value_creation(self):
        """
        Handle None value creation.
        
        Implements None value representation using EngageValue with NONE type.
        Generates proper C++ null value handling and comparison.
        
        Requirements: 7.4
        
        Returns:
            Tuple of (cpp_code, cpp_type) for None value creation
        """
        return "EngageValue()", "EngageValue"

    def _handle_none_checking(self, value_cpp, value_type):
        """
        Handle None value checking and conditional logic.
        
        Generates proper C++ null value comparison using EngageValue.is_none().
        Supports None assignment and propagation.
        
        Requirements: 7.4
        
        Args:
            value_cpp: C++ expression for the value to check
            value_type: C++ type of the value
            
        Returns:
            Tuple of (cpp_code, cpp_type) for None checking
        """
        if value_type == "EngageValue":
            return f"({value_cpp}.is_none())", "bool"
        else:
            # For non-EngageValue types, they are never None
            return "false", "bool"

    def visit_FuncCallNode(self, node):
        """
        Enhanced function call visitor with comprehensive argument passing support.
        
        Implements function invocation with:
        - Argument list evaluation and type conversion
        - Proper C++ function calls with parameter matching
        - Support for both built-in and user-defined function calls
        - Special handling for standard library functions
        - Method calls on objects and records
        
        Requirements: 3.2, 3.4
        
        Args:
            node: FuncCallNode AST node containing function call information
            
        Returns:
            Tuple of (C++ expression, return type)
        """
        # Special handling for print statements
        if isinstance(node.node_to_call, VarAccessNode) and node.node_to_call.name_token.value == 'print':
            return self.visit_PrintNode(node)
        
        # Get function name and check if it's a known function
        if isinstance(node.node_to_call, VarAccessNode):
            func_name = node.node_to_call.name_token.value
            func_name_cpp = self.format_cpp_identifier(func_name)
            
            # Check if this is a standard library function
            if func_name in self.stdlib_implementations:
                return self._handle_stdlib_function_call(func_name, func_name_cpp, node.arg_nodes)
            
            # Check if this is a user-defined function
            signature = self.get_function_signature(func_name_cpp)
            if signature:
                return self._handle_user_function_call(func_name_cpp, signature, node.arg_nodes)
            
            # Handle built-in functions with special argument processing
            if func_name in ['push', 'pop', 'length', 'size', 'keys', 'values', 'sort', 'to_string', 'has_key']:
                return self._handle_builtin_function_call(func_name, node.arg_nodes)
            
            # Default function call handling
            args_cpp = []
            for arg in node.arg_nodes:
                arg_cpp, arg_type = self.visit(arg)
                # Wrap in EngageValue if needed for dynamic typing
                if arg_type not in ['EngageValue', 'const EngageValue&']:
                    arg_cpp = f"EngageValue({arg_cpp})"
                args_cpp.append(arg_cpp)
            
            return f"{func_name_cpp}({', '.join(args_cpp)})", "EngageValue"
        
        # Handle method calls or complex function expressions
        func_cpp, func_type = self.visit(node.node_to_call)
        args_cpp = []
        
        for arg in node.arg_nodes:
            arg_cpp, arg_type = self.visit(arg)
            # Ensure proper type conversion for arguments
            if arg_type not in ['EngageValue', 'const EngageValue&']:
                arg_cpp = f"EngageValue({arg_cpp})"
            args_cpp.append(arg_cpp)
        
        return f"{func_cpp}({', '.join(args_cpp)})", "EngageValue"
    
    def _handle_stdlib_function_call(self, func_name, func_name_cpp, arg_nodes):
        """
        Handle calls to standard library functions with proper argument conversion.
        
        Args:
            func_name: Original Engage function name
            func_name_cpp: C++ formatted function name
            arg_nodes: List of argument AST nodes
            
        Returns:
            Tuple of (C++ expression, return type)
        """
        # Get function signature for proper argument handling
        signature = self.get_function_signature(func_name)
        if not signature:
            # Add signature if not already present
            self._add_stdlib_function_signature(func_name)
            signature = self.get_function_signature(func_name)
        
        # Process arguments with type conversion
        args_cpp = []
        for i, arg in enumerate(arg_nodes):
            arg_cpp, arg_type = self.visit(arg)
            
            # Apply type conversion based on expected parameter type
            if signature and i < len(signature.parameters):
                expected_type = signature.parameters[i][1]
                if expected_type != arg_type:
                    arg_cpp = self._convert_argument_type(arg_cpp, arg_type, expected_type)
            
            args_cpp.append(arg_cpp)
        
        # Generate function call with proper prefix
        stdlib_func_name = f"engage_{func_name}"
        return f"{stdlib_func_name}({', '.join(args_cpp)})", signature.return_type if signature else "EngageValue"
    
    def _handle_user_function_call(self, func_name_cpp, signature, arg_nodes):
        """
        Handle calls to user-defined functions with parameter matching.
        
        Args:
            func_name_cpp: C++ formatted function name
            signature: FunctionSignature object
            arg_nodes: List of argument AST nodes
            
        Returns:
            Tuple of (C++ expression, return type)
        """
        args_cpp = []
        
        # Process arguments with type checking and conversion
        for i, arg in enumerate(arg_nodes):
            arg_cpp, arg_type = self.visit(arg)
            
            # Convert to expected parameter type if needed
            if i < len(signature.parameters):
                expected_type = signature.parameters[i][1]
                if expected_type != arg_type:
                    arg_cpp = self._convert_argument_type(arg_cpp, arg_type, expected_type)
            else:
                # Extra arguments - wrap in EngageValue for safety
                if arg_type not in ['EngageValue', 'const EngageValue&']:
                    arg_cpp = f"EngageValue({arg_cpp})"
            
            args_cpp.append(arg_cpp)
        
        return f"{func_name_cpp}({', '.join(args_cpp)})", signature.return_type
    
    def _handle_builtin_function_call(self, func_name, arg_nodes):
        """
        Handle calls to built-in functions that operate on data structures.
        
        Args:
            func_name: Built-in function name
            arg_nodes: List of argument AST nodes
            
        Returns:
            Tuple of (C++ expression, return type)
        """
        if func_name == 'push' and len(arg_nodes) >= 2:
            # push with vector, value
            container_cpp, container_type = self.visit(arg_nodes[0])
            value_cpp, value_type = self.visit(arg_nodes[1])
            
            # Convert value to EngageValue if needed
            if value_type not in ['EngageValue', 'const EngageValue&']:
                value_cpp = f"EngageValue({value_cpp})"
            
            return f"engage_vector_push({container_cpp}, {value_cpp})", "void"
        
        elif func_name == 'pop' and len(arg_nodes) >= 1:
            # pop with vector
            container_cpp, container_type = self.visit(arg_nodes[0])
            return f"engage_vector_pop({container_cpp})", "EngageValue"
        
        elif func_name == 'length' and len(arg_nodes) >= 1:
            # length with container
            container_cpp, container_type = self.visit(arg_nodes[0])
            
            if 'vector' in container_type.lower():
                return f"engage_vector_length({container_cpp})", "size_t"
            elif 'string' in container_type.lower():
                return f"engage_string_length({container_cpp})", "size_t"
            else:
                # Default to vector length for unknown container types
                return f"engage_vector_length({container_cpp})", "size_t"
        
        elif func_name == 'size' and len(arg_nodes) >= 1:
            # size with table
            container_cpp, container_type = self.visit(arg_nodes[0])
            return f"engage_table_size({container_cpp})", "size_t"
        
        elif func_name == 'keys' and len(arg_nodes) >= 1:
            # keys with table
            container_cpp, container_type = self.visit(arg_nodes[0])
            return f"engage_keys({container_cpp})", "vector<string>"
        
        elif func_name == 'values' and len(arg_nodes) >= 1:
            # values with table
            container_cpp, container_type = self.visit(arg_nodes[0])
            return f"engage_values({container_cpp})", "vector<EngageValue>"
        
        elif func_name == 'sort' and len(arg_nodes) >= 1:
            # sort with vector
            container_cpp, container_type = self.visit(arg_nodes[0])
            return f"engage_sort({container_cpp})", "void"
        
        elif func_name == 'to_string' and len(arg_nodes) >= 1:
            # to_string with value
            value_cpp, value_type = self.visit(arg_nodes[0])
            if value_type in ['EngageValue', 'const EngageValue&']:
                return f"({value_cpp}).as_string()", "std::string"
            elif value_type == 'double':
                return f"std::to_string(static_cast<int>({value_cpp}))", "std::string"
            elif value_type in ['string', 'std::string']:
                return value_cpp, "std::string"
            else:
                return f"EngageValue({value_cpp}).as_string()", "std::string"
        
        elif func_name == 'has_key' and len(arg_nodes) >= 2:
            # has_key with table, key
            table_cpp, table_type = self.visit(arg_nodes[0])
            key_cpp, key_type = self.visit(arg_nodes[1])
            
            # Convert key to string if needed
            if key_type not in ['string', 'std::string']:
                if key_type in ['EngageValue', 'const EngageValue&']:
                    key_cpp = f"({key_cpp}).as_string()"
                else:
                    key_cpp = f"EngageValue({key_cpp}).as_string()"
            
            return f"engage_table_has_key({table_cpp}, {key_cpp})", "bool"
        
        # Default handling for unknown built-in functions
        args_cpp = [self.visit(arg)[0] for arg in arg_nodes]
        return f"engage_{func_name}({', '.join(args_cpp)})", "EngageValue"
    
    def _convert_argument_type(self, arg_cpp, from_type, to_type):
        """
        Convert an argument from one type to another for function calls.
        
        Args:
            arg_cpp: C++ expression for the argument
            from_type: Source type
            to_type: Target type
            
        Returns:
            C++ expression with appropriate type conversion
        """
        if from_type == to_type:
            return arg_cpp
        
        # Convert to EngageValue
        if to_type in ['EngageValue', 'const EngageValue&']:
            if from_type not in ['EngageValue', 'const EngageValue&']:
                return f"EngageValue({arg_cpp})"
            return arg_cpp
        
        # Convert from EngageValue to specific type
        if from_type in ['EngageValue', 'const EngageValue&']:
            if to_type == 'double':
                return f"({arg_cpp}).as_number()"
            elif to_type in ['string', 'std::string']:
                return f"({arg_cpp}).as_string()"
            elif to_type == 'bool':
                return f"({arg_cpp}).is_truthy()"
        
        # Use general type conversion utility
        return self.generate_type_conversion(arg_cpp, from_type, to_type)
    
    def _add_stdlib_function_signature(self, func_name):
        """
        Add a standard library function signature if not already present.
        
        Args:
            func_name: Standard library function name
        """
        # This method would add signatures for stdlib functions
        # The signatures are already added in _initialize_stdlib_implementations
        pass

    def visit_PrintNode(self, node):
        """
        Handle 'print with' statements by generating C++ cout statements.
        
        Supports:
        - Multiple arguments with proper spacing
        - Mixed types (strings, numbers, variables)
        - Proper formatting with automatic type conversion
        - Empty print statements (just newline)
        
        Requirements: 2.3, 3.4
        """
        if not node.arg_nodes:
            # Empty print statement - just output newline
            return "std::cout << std::endl", "Void"
        
        # Handle multiple arguments by chaining cout operations
        cout_parts = []
        
        for i, arg_node in enumerate(node.arg_nodes):
            arg_cpp, arg_type = self.visit(arg_node)
            
            # Add the argument to cout chain
            cout_parts.append(arg_cpp)
            
            # Add space between arguments (except for the last one)
            if i < len(node.arg_nodes) - 1:
                cout_parts.append('" "')
        
        # Build the complete cout statement
        cout_chain = " << ".join(cout_parts)
        return f"std::cout << {cout_chain} << std::endl", "Void"

    def visit_RecordDefNode(self, node):
        """
        Enhanced record definition visitor for C++ struct/class generation.
        
        Implements comprehensive record support including:
        - Property definitions with default values and proper types
        - Method definitions within the record structure
        - Constructor generation for property initialization
        - Proper C++ struct generation with member variables and methods
        
        Requirements: 5.1, 5.2
        
        Args:
            node: RecordDefNode containing record name and members
            
        Returns:
            (None, "Void") - Record definitions don't return values
        """
        record_name = node.name_token.value
        
        # Create and register record definition for tracking
        record_def = self.add_record_definition(record_name)
        
        # Set current record context for method processing
        previous_record = self.current_record_name
        self.current_record_name = record_name
        
        # Generate C++ struct declaration
        struct_name = record_def.get_cpp_struct_name()
        self.add_line(f"struct {struct_name} {{", global_scope=True)
        self.indent_level += 1
        
        # Process properties first to collect their information
        properties = []
        methods = []
        
        for member in node.members:
            if isinstance(member, FuncDefNode):  # Method definition - check this first
                methods.append(member)
            elif isinstance(member, VarAssignNode):  # Property with default value
                properties.append(member)
            elif hasattr(member, 'default_value'):  # PropertyDefNode
                properties.append(member)
            else:
                # Unknown member type, skip with warning
                print(f"Warning: Unknown member type in record {record_name}: {type(member)}")
        
        # Generate property declarations with proper types
        for prop in properties:
            prop_name = prop.name_token.value
            
            # Determine property type and default value
            if hasattr(prop, 'value_node'):  # VarAssignNode
                default_val, prop_type = self.visit(prop.value_node)
                cpp_type = self._map_engage_type_to_cpp(prop_type)
            elif hasattr(prop, 'default_value'):  # PropertyDefNode
                if prop.default_value:
                    default_val, prop_type = self.visit(prop.default_value)
                    cpp_type = self._map_engage_type_to_cpp(prop_type)
                else:
                    default_val = "EngageValue()"
                    cpp_type = "EngageValue"
                    prop_type = "EngageValue"
            else:
                default_val = "EngageValue()"
                cpp_type = "EngageValue"
                prop_type = "EngageValue"
            
            # Add property to record definition
            record_def.add_property(prop_name, cpp_type, default_val)
            
            # Generate C++ member variable declaration
            self.add_line(f"{cpp_type} {prop_name} = {default_val};", global_scope=True)
        
        # Add blank line before methods if we have both properties and methods
        if properties and methods:
            self.add_line("", global_scope=True)
        
        # Generate constructor if we have properties
        if properties:
            self._generate_record_constructor(record_def, struct_name)
            self.add_line("", global_scope=True)
        
        # Generate method definitions within the record structure
        for method in methods:
            method_name = method.name_token.value
            
            # Create function signature for the method
            params = []
            for param_token in method.param_tokens:
                params.append((param_token.value, "EngageValue"))
            
            # Add method to record definition
            method_signature = self.FunctionSignature(
                method_name, params, "auto", is_method=True, record_name=record_name
            )
            record_def.add_method(method_name, method_signature)
            
            # Generate the method implementation
            self.visit_FuncDefNode(method, is_method=True)
            
            # Add blank line between methods
            if method != methods[-1]:  # Not the last method
                self.add_line("", global_scope=True)
        
        # Close the struct definition
        self.indent_level -= 1
        self.add_line("};", global_scope=True)
        self.add_line("", global_scope=True)
        
        # Mark struct as generated
        record_def.cpp_struct_generated = True
        
        # Restore previous record context
        self.current_record_name = previous_record
        
        return None, "Void"
    
    def _generate_record_constructor(self, record_def, struct_name):
        """
        Generate constructor for record with property initialization.
        
        Creates both default constructor and parameterized constructor
        for flexible object instantiation.
        
        Args:
            record_def: RecordDefinition object
            struct_name: C++ struct name
        """
        # Generate default constructor
        self.add_line(f"{struct_name}() = default;", global_scope=True)
        
        # Generate parameterized constructor if we have properties
        if record_def.properties:
            # Create constructor parameter list
            constructor_params = []
            initializer_list = []
            
            for prop_name, (prop_type, default_val) in record_def.properties.items():
                constructor_params.append(f"const {prop_type}& {prop_name}_param = {default_val}")
                initializer_list.append(f"{prop_name}({prop_name}_param)")
            
            params_str = ", ".join(constructor_params)
            init_str = " : " + ", ".join(initializer_list) if initializer_list else ""
            
            self.add_line(f"{struct_name}({params_str}){init_str} {{}}", global_scope=True)
    
    def _map_engage_type_to_cpp(self, engage_type):
        """
        Map Engage types to appropriate C++ types.
        
        Args:
            engage_type: Engage type string
            
        Returns:
            Corresponding C++ type string
        """
        type_mapping = {
            "double": "double",
            "std::string": "std::string", 
            "string": "std::string",
            "std::vector<EngageValue>": "std::vector<EngageValue>",
            "std::map<std::string, EngageValue>": "std::map<std::string, EngageValue>",
            "EngageValue": "EngageValue"
        }
        
        return type_mapping.get(engage_type, "EngageValue")

    def visit_FuncDefNode(self, node, is_method=False):
        """
        Enhanced function definition visitor with comprehensive parameter handling.
        
        Implements C++ function generation with:
        - Proper parameter lists with type inference and conversion
        - Function signatures with appropriate return types
        - Function body transpilation with local variable scoping
        - Support for both global functions and record methods
        
        Requirements: 3.1, 3.2
        
        Args:
            node: FuncDefNode AST node containing function definition
            is_method: Whether this is a method within a record
            
        Returns:
            None (function definitions don't return values)
        """
        func_name = self.format_cpp_identifier(node.name_token.value)
        
        # Extract parameter information with proper type handling
        parameters = []
        param_cpp_list = []
        
        for param_token in node.param_tokens:
            param_name = self.format_cpp_identifier(param_token.value)
            # Use EngageValue for dynamic typing support
            param_type = "const EngageValue&"
            parameters.append((param_name, param_type))
            param_cpp_list.append(f"{param_type} {param_name}")
        
        # Determine return type through basic analysis
        return_type = self._infer_function_return_type(node.body_nodes)
        
        # Add function signature to function table for later reference
        signature = self.add_function(
            func_name, 
            parameters, 
            return_type, 
            is_method, 
            self.current_record_name if is_method else None
        )
        
        # Generate C++ function signature
        param_str = ", ".join(param_cpp_list)
        
        # Store current function context for nested processing
        previous_function = self.current_function_name
        self.current_function_name = func_name
        
        # Push new scope for function parameters and local variables
        self.push_scope()
        
        # Add parameters to current scope symbol table
        for param_name, param_type in parameters:
            self.add_symbol(param_name, param_type, "current")
        
        # Generate function definition
        # For methods inside records, we want to add to global_code (where the struct is)
        # For regular functions, we add to global_code as well
        use_global_scope = True  # Always add functions to global scope
        
        # Temporarily set the scope to global when generating methods
        previous_scope = self.current_scope_is_global
        if is_method:
            self.current_scope_is_global = True
        
        self.add_line(f"{return_type} {func_name}({param_str}) {{", global_scope=use_global_scope)
        self.indent_level += 1
        
        # Process function body with proper statement handling
        for statement in node.body_nodes:
            self._process_statement(statement)
        
        # Add default return if no explicit return found and return type is not void
        if return_type != "void" and not self._has_explicit_return(node.body_nodes):
            if return_type == "EngageValue":
                self.add_line("return EngageValue();  // Default None return", global_scope=use_global_scope)
            else:
                self.add_line(f"return {self._get_default_value_for_type(return_type)};", global_scope=use_global_scope)
        
        self.indent_level -= 1
        self.add_line("}", global_scope=use_global_scope)
        
        # Restore previous scope
        if is_method:
            self.current_scope_is_global = previous_scope
        
        if not is_method:
            self.add_blank_line(global_scope=True)
        
        # Restore previous function context and scope
        self.pop_scope()
        self.current_function_name = previous_function
        
        return None, "Void"
    
    def _infer_function_return_type(self, body_nodes):
        """
        Infer the return type of a function based on its body statements.
        
        Analyzes return statements to determine the most appropriate C++ return type.
        Falls back to EngageValue for dynamic typing if type cannot be determined.
        
        Args:
            body_nodes: List of AST nodes representing the function body
            
        Returns:
            String representing the C++ return type
        """
        # Look for explicit return statements
        for statement in body_nodes:
            if isinstance(statement, ReturnNode):
                if statement.node_to_return:
                    # Try to infer type from return expression
                    if isinstance(statement.node_to_return, NumberNode):
                        return "double"
                    elif isinstance(statement.node_to_return, StringNode):
                        return "std::string"
                    elif isinstance(statement.node_to_return, VarAccessNode):
                        # Check if we know the variable type
                        var_type = self.get_symbol_type(statement.node_to_return.name_token.value)
                        if var_type != "EngageValue":
                            return var_type
                else:
                    # Return with no value - void function
                    return "void"
        
        # Default to EngageValue for dynamic typing support
        return "EngageValue"
    
    def _has_explicit_return(self, body_nodes):
        """
        Check if the function body contains an explicit return statement.
        
        Args:
            body_nodes: List of AST nodes representing the function body
            
        Returns:
            Boolean indicating whether an explicit return is present
        """
        for statement in body_nodes:
            if isinstance(statement, ReturnNode):
                return True
            # Could also check nested statements in if/while blocks
        return False
    
    def _get_default_value_for_type(self, cpp_type):
        """
        Get the default value for a given C++ type.
        
        Args:
            cpp_type: C++ type string
            
        Returns:
            String representing the default value for the type
        """
        type_defaults = {
            "double": "0.0",
            "int": "0",
            "std::string": '""',
            "bool": "false",
            "EngageValue": "EngageValue()",
            "void": ""
        }
        return type_defaults.get(cpp_type, "EngageValue()")

    def visit_ReturnNode(self, node):
        """
        Enhanced return statement visitor with comprehensive value handling.
        
        Implements return value handling with:
        - Appropriate C++ return statements with type conversion
        - Void returns and value returns handled correctly
        - Proper cleanup and scope exit in generated code
        - Type checking and conversion based on function signature
        
        Requirements: 3.3
        
        Args:
            node: ReturnNode AST node containing return expression
            
        Returns:
            Tuple of (C++ return statement, "Void")
        """
        # Handle return with no value (void return)
        if not hasattr(node, 'node_to_return') or node.node_to_return is None:
            return "return", "Void"
        
        # For compatibility with different parser versions
        return_expr_node = getattr(node, 'node_to_return', None) or getattr(node, 'value_node', None)
        
        if return_expr_node is None:
            return "return", "Void"
        
        # Process the return expression
        value_cpp, value_type = self.visit(return_expr_node)
        
        # Get the expected return type from current function signature
        expected_return_type = self._get_current_function_return_type()
        
        # Apply type conversion if needed
        if expected_return_type and expected_return_type != "auto" and expected_return_type != value_type:
            value_cpp = self._convert_return_value(value_cpp, value_type, expected_return_type)
        
        # Generate return statement with proper formatting
        return f"return {value_cpp}", "Void"
    
    def _get_current_function_return_type(self):
        """
        Get the expected return type of the current function being processed.
        
        Returns:
            String representing the expected return type, or None if not available
        """
        if self.current_function_name:
            signature = self.get_function_signature(self.current_function_name)
            if signature:
                return signature.return_type
        return None
    
    def _convert_return_value(self, value_cpp, from_type, to_type):
        """
        Convert a return value from one type to another.
        
        Ensures that the returned value matches the function's declared return type
        by applying appropriate type conversions.
        
        Args:
            value_cpp: C++ expression for the return value
            from_type: Source type of the value
            to_type: Expected return type of the function
            
        Returns:
            C++ expression with appropriate type conversion
        """
        if from_type == to_type:
            return value_cpp
        
        # Convert to EngageValue (most common case for dynamic typing)
        if to_type == "EngageValue":
            if from_type not in ['EngageValue', 'const EngageValue&']:
                return f"EngageValue({value_cpp})"
            return value_cpp
        
        # Convert from EngageValue to specific type
        if from_type in ['EngageValue', 'const EngageValue&']:
            if to_type == 'double':
                return f"({value_cpp}).as_number()"
            elif to_type in ['string', 'std::string']:
                return f"({value_cpp}).as_string()"
            elif to_type == 'bool':
                return f"({value_cpp}).is_truthy()"
            elif to_type == 'int':
                return f"static_cast<int>(({value_cpp}).as_number())"
        
        # Handle specific type conversions
        if from_type == 'double' and to_type in ['string', 'std::string']:
            return f"std::to_string({value_cpp})"
        elif from_type in ['string', 'std::string'] and to_type == 'double':
            return f"std::stod({value_cpp})"
        elif from_type == 'int' and to_type == 'double':
            return f"static_cast<double>({value_cpp})"
        elif from_type == 'double' and to_type == 'int':
            return f"static_cast<int>({value_cpp})"
        
        # Use general type conversion utility as fallback
        return self.generate_type_conversion(value_cpp, from_type, to_type)

    def visit_NewInstanceNode(self, node):
        """
        Enhanced object instantiation visitor for object construction.
        
        Implements comprehensive object instantiation including:
        - Property initialization during object creation
        - Proper C++ constructor calls with parameter passing
        - Support for named parameter initialization syntax
        - Default value handling for unspecified properties
        
        Requirements: 5.4
        
        Args:
            node: NewInstanceNode containing class name and property initializations
            
        Returns:
            (cpp_constructor_call, record_type) - C++ constructor call and type
        """
        record_name = node.name_token.value
        
        # Get the record definition to understand its structure
        record_def = self.get_record_definition(record_name)
        if not record_def:
            # If record not found, create a basic instantiation
            if node.properties:
                props_cpp = [self.visit(p)[0] for p in node.properties.values()]
                return f"{record_name}{{{', '.join(props_cpp)}}}", record_name
            else:
                return f"{record_name}()", record_name
        
        # Use the C++ struct name
        struct_name = record_def.get_cpp_struct_name()
        
        # Handle property initialization
        if node.properties:
            # Named parameter initialization
            constructor_args = []
            
            # Process each property in the order defined in the record
            for prop_name, (prop_type, default_val) in record_def.properties.items():
                if prop_name in node.properties:
                    # Property is explicitly set
                    prop_value_cpp, _ = self.visit(node.properties[prop_name])
                    constructor_args.append(prop_value_cpp)
                else:
                    # Property not set, use default value
                    constructor_args.append(default_val)
            
            # Generate constructor call with all parameters
            args_str = ", ".join(constructor_args)
            return f"{struct_name}({args_str})", record_name
        else:
            # Default constructor (no properties specified)
            return f"{struct_name}()", record_name

    def visit_MemberAccessNode(self, node):
        """
        Enhanced member access visitor for property and method access.
        
        Implements comprehensive member access including:
        - Both property access and method invocation
        - Proper C++ member access operators (. and ->)
        - Support for method chaining and nested member access
        - Type inference for accessed members
        
        Requirements: 5.5
        
        Args:
            node: MemberAccessNode containing instance and member name
            
        Returns:
            (cpp_access_expression, member_type) - C++ member access and type
        """
        instance_cpp, instance_type = self.visit(node.instance_node)
        member_name = node.member_token.value
        
        # Determine if we're accessing a record type
        record_def = None
        if instance_type in self.record_definitions:
            record_def = self.record_definitions[instance_type]
        elif instance_type.startswith("Record_"):
            # Handle C++ struct names
            original_name = instance_type[7:]  # Remove "Record_" prefix
            record_def = self.record_definitions.get(original_name)
        
        if record_def:
            # Check if it's a property or method
            if member_name in record_def.properties:
                # Property access
                prop_type, _ = record_def.properties[member_name]
                return f"{instance_cpp}.{member_name}", prop_type
            elif member_name in record_def.methods:
                # Method access - return the method reference for potential calling
                method_sig = record_def.methods[member_name]
                return f"{instance_cpp}.{member_name}", method_sig.return_type
            else:
                # Unknown member, assume it's a property with EngageValue type
                return f"{instance_cpp}.{member_name}", "EngageValue"
        else:
            # Not a known record type, use generic access
            # Determine appropriate access operator
            if instance_type.endswith("*") or instance_type == "Self":
                # Pointer access
                return f"{instance_cpp}->{member_name}", "auto"
            else:
                # Direct access
                return f"{instance_cpp}.{member_name}", "auto"

    def visit_SelfNode(self, node):
        """
        Enhanced self reference visitor for this pointer handling.
        
        Implements comprehensive self reference including:
        - Proper C++ this pointer usage in method contexts
        - Self reference in property access and method calls
        - Proper scoping and context validation
        - Type information for the current record instance
        
        Requirements: 5.5
        
        Args:
            node: SelfNode representing self reference
            
        Returns:
            (cpp_this_reference, record_type) - C++ this pointer and current record type
        """
        # Check if we're currently in a method context
        if self.current_record_name:
            # We're in a record method, return appropriate this reference
            record_def = self.get_record_definition(self.current_record_name)
            if record_def:
                # Return this pointer with the specific record type
                return "(*this)", self.current_record_name
            else:
                # Fallback to generic this pointer
                return "(*this)", "Self"
        else:
            # Not in a method context, this might be an error but we'll handle it gracefully
            # This could happen in global functions or other contexts
            return "(*this)", "Self"

    def visit_UnaryOpNode(self, node):
        """
        Handle unary operations like 'not', 'call', Result unwrapping, and None checking.
        
        Implements proper C++ unary operations with support for:
        - Logical negation ('not')
        - Function calls without arguments ('call')
        - Result type value extraction ('the ok value of')
        - Result type error extraction ('the error message of')
        - None value checking and conditional logic
        
        Requirements: 7.4
        """
        operand_cpp, operand_type = self.visit(node.node)
        op = node.op_token.value
        
        if op == 'not':
            # Handle logical negation with proper truthiness evaluation
            if operand_type == "EngageValue":
                return f"(!{operand_cpp}.is_truthy())", "bool"
            else:
                return f"(!{operand_cpp})", "bool"
        elif op == 'call':
            # Handle function calls without arguments
            return f"{operand_cpp}()", "auto"
        elif op == 'the ok value of':
            # Handle Result type unwrapping with proper error checking
            if operand_type.startswith("Result<"):
                inner_type = operand_type[7:-1]  # Extract T from Result<T>
                return f"{operand_cpp}.value()", inner_type
            else:
                # For non-Result types, just return the value
                return operand_cpp, operand_type
        elif op == 'the error message of':
            # Handle Result type error extraction
            if operand_type.startswith("Result<"):
                return f"{operand_cpp}.error()", "std::string"
            else:
                # For non-Result types, this is an error
                raise Exception(f"Cannot extract error message from non-Result type: {operand_type}")
        elif op == 'is none':
            # Handle None checking
            return self._handle_none_checking(operand_cpp, operand_type)
        else:
            raise Exception(f"Unsupported unary operator: {op}")

    def visit_IfNode(self, node):
        """
        Handle if-then-otherwise-end statements for conditional statement generation.
        
        Implements proper C++ if-else constructs with correct scoping and handles
        multiple condition cases with proper else-if chaining.
        
        Note: This method is called from _process_if_statement for proper statement
        context handling. Direct calls should use _process_if_statement instead.
        
        Requirements: 2.1, 2.3
        
        Args:
            node: IfNode AST node containing cases and else_case
            
        Returns:
            Tuple of (None, "Void") as this is a statement, not an expression
        """
        # If statements are handled by _process_if_statement for proper block structure
        # This method exists for completeness but should not be called directly
        raise Exception("If statements should be processed through _process_if_statement "
                       "for proper C++ block structure generation. Use _process_statement instead.")

    def visit_WhileNode(self, node):
        """
        Handle while loop statements for loop generation.
        
        Generates C++ while loops with proper condition evaluation and handles
        loop body statements with correct variable scoping. Ensures proper break
        and continue statement support if needed.
        
        Note: This method is called from _process_while_statement for proper statement
        context handling. Direct calls should use _process_while_statement instead.
        
        Requirements: 2.1, 2.3
        
        Args:
            node: WhileNode AST node containing condition_node and body_nodes
            
        Returns:
            Tuple of (None, "Void") as this is a statement, not an expression
        """
        # While loops are handled by _process_while_statement for proper block structure
        # This method exists for completeness but should not be called directly
        raise Exception("While loops should be processed through _process_while_statement "
                       "for proper C++ block structure generation. Use _process_statement instead.")

    def visit_TaskNode(self, node):
        """
        Handle concurrent task execution with basic threading support.
        
        Generates C++ code using std::thread for basic concurrency.
        This is a simplified implementation with limitations compared to full Engage concurrency.
        
        Requirements: 8.1, 10.4
        """
        # Generate warning comment about limitations
        self.add_line("// WARNING: Simplified concurrency model - not equivalent to full Engage task system", global_scope=False)
        
        # Generate a lambda function for the task body
        task_var_name = self.generate_unique_variable_name("task")
        
        # Start lambda definition
        self.add_line(f"auto {task_var_name}_lambda = []() {{", global_scope=False)
        self.indent_level += 1
        
        # Process task body statements
        for statement in node.body_nodes:
            self._process_statement(statement)
        
        self.indent_level -= 1
        self.add_line("};", global_scope=False)
        
        # Create and start the thread
        thread_var_name = self.generate_unique_variable_name("thread")
        self.add_line(f"std::thread {thread_var_name}({task_var_name}_lambda);", global_scope=False)
        
        # For basic implementation, immediately detach the thread
        # In a full implementation, we would track threads for proper cleanup
        self.add_line(f"{thread_var_name}.detach();", global_scope=False)
        
        return f"{thread_var_name}", "std::thread"

    def visit_ChannelNode(self, node):
        """
        Handle channel creation for concurrency using std::queue and std::mutex.
        
        Generates C++ code for a thread-safe queue-based channel implementation.
        This is a simplified implementation with limitations compared to full Engage channels.
        
        Requirements: 8.1, 10.4
        """
        # Generate warning comment about limitations
        self.add_line("// WARNING: Simplified channel implementation - not equivalent to full Engage channel system", global_scope=False)
        
        channel_name = node.name_token.value if hasattr(node, 'name_token') else self.generate_unique_variable_name("channel")
        
        # Generate channel struct definition if not already generated
        if not hasattr(self, '_channel_struct_generated'):
            self._generate_channel_struct()
            self._channel_struct_generated = True
        
        # Create channel instance
        self.add_line(f"EngageChannel {channel_name};", global_scope=False)
        
        # Add to symbol table
        self.add_symbol(channel_name, "EngageChannel")
        
        return channel_name, "EngageChannel"

    def visit_SendNode(self, node):
        """
        Handle sending values through channels using thread-safe queue operations.
        
        Generates C++ code for pushing values to a channel queue.
        This is a simplified implementation with limitations compared to full Engage send operations.
        
        Requirements: 8.1, 10.4
        """
        # Generate warning comment about limitations
        self.add_line("// WARNING: Simplified send operation - not equivalent to full Engage send semantics", global_scope=False)
        
        # Get the value to send
        value_cpp, value_type = self.visit(node.value_node)
        
        # Get the channel
        channel_cpp, channel_type = self.visit(node.channel_node)
        
        # Generate send operation
        self.add_line(f"{channel_cpp}.send(EngageValue({value_cpp}));", global_scope=False)
        
        return f"{channel_cpp}.send(EngageValue({value_cpp}))", "void"

    def visit_ReceiveNode(self, node):
        """
        Handle receiving values from channels using thread-safe queue operations.
        
        Generates C++ code for popping values from a channel queue.
        This is a simplified implementation with limitations compared to full Engage receive operations.
        
        Requirements: 8.1, 10.4
        """
        # Generate warning comment about limitations
        self.add_line("// WARNING: Simplified receive operation - not equivalent to full Engage receive semantics", global_scope=False)
        
        # Get the channel
        channel_cpp, channel_type = self.visit(node.channel_node)
        
        # Generate receive operation
        receive_var_name = self.generate_unique_variable_name("received_value")
        self.add_line(f"EngageValue {receive_var_name} = {channel_cpp}.receive();", global_scope=False)
        
        return receive_var_name, "EngageValue"

    def visit_FiberDefNode(self, node):
        """
        Handle fiber (coroutine) definitions with basic generator pattern support.
        
        Generates C++ code using a simplified generator pattern or C++20 coroutines if available.
        This is a simplified implementation with limitations compared to full Engage fibers.
        
        Requirements: 8.2, 10.4
        """
        # Generate warning comment about limitations
        self.add_line("// WARNING: Simplified fiber implementation - not equivalent to full Engage fiber system", global_scope=False)
        
        fiber_name = node.name_token.value
        
        # Generate fiber struct definition if not already generated
        if not hasattr(self, '_fiber_struct_generated'):
            self._generate_fiber_struct()
            self._fiber_struct_generated = True
        
        # Create fiber class for this specific fiber
        fiber_class_name = f"Fiber_{fiber_name}"
        
        # Generate fiber class definition
        self.add_line(f"class {fiber_class_name} : public EngageFiber {{", global_scope=True)
        self.add_line("public:", global_scope=True)
        
        # Generate the fiber body as a method
        self.add_line(f"    EngageValue run() override {{", global_scope=True)
        
        # Store current state and switch to fiber context
        old_indent = self.indent_level
        old_scope = self.current_scope_is_global
        self.indent_level = 2
        self.current_scope_is_global = True
        
        # Process fiber body statements
        for statement in node.body_nodes:
            self._process_statement(statement)
        
        # Restore state
        self.indent_level = old_indent
        self.current_scope_is_global = old_scope
        
        self.add_line("        return EngageValue(); // Default return", global_scope=True)
        self.add_line("    }", global_scope=True)
        self.add_line("};", global_scope=True)
        self.add_line("", global_scope=True)
        
        # Create instance of the fiber
        fiber_instance_name = f"{fiber_name}_fiber"
        self.add_line(f"{fiber_class_name} {fiber_instance_name};", global_scope=False)
        
        # Add to symbol table
        self.add_symbol(fiber_instance_name, fiber_class_name)
        
        return fiber_instance_name, fiber_class_name

    def visit_YieldNode(self, node):
        """
        Handle yield statements in fibers with basic value return support.
        
        Generates C++ code for yielding values from fibers using a simplified approach.
        This is a simplified implementation with limitations compared to full Engage yield semantics.
        
        Requirements: 8.2, 10.4
        """
        # Generate warning comment about limitations
        self.add_line("// WARNING: Simplified yield operation - not equivalent to full Engage yield semantics", global_scope=False)
        
        # Get the value to yield
        if node.value_node:
            value_cpp, value_type = self.visit(node.value_node)
        else:
            value_cpp = "EngageValue()"
            value_type = "EngageValue"
        
        # Store the yielded value and return it
        # In a full implementation, this would suspend execution and allow resumption
        yield_var_name = self.generate_unique_variable_name("yielded_value")
        self.add_line(f"EngageValue {yield_var_name} = {value_cpp};", global_scope=False)
        self.add_line(f"// TODO: Implement proper fiber suspension/resumption", global_scope=False)
        self.add_line(f"return {yield_var_name}; // Simplified yield - returns immediately", global_scope=False)
        
        return yield_var_name, "EngageValue"
    
    def visit_TableNode(self, node):
        """
        Handle Table (hash map) creation with EngageValue support.
        
        Implements std::map creation for tables with string keys and EngageValue values.
        Generates proper C++ map declarations with support for table operations
        (assignment, access, keys, size) through built-in functions.
        
        Requirements: 4.2, 4.4
        
        Args:
            node: TableNode AST node representing table creation
            
        Returns:
            Tuple of (C++ expression, type)
        """
        # Use std::map<string, EngageValue> for mixed-type value support
        return "std::map<std::string, EngageValue>()", "std::map<std::string, EngageValue>"
    
    def visit_VectorNode(self, node):
        """
        Handle Vector (dynamic array) creation with EngageValue support.
        
        Implements std::vector creation for mixed-type vectors using EngageValue containers.
        Generates proper C++ vector declarations and initialization with support for
        vector operations through built-in functions.
        
        Requirements: 4.1, 4.4
        
        Args:
            node: VectorNode AST node representing vector creation
            
        Returns:
            Tuple of (C++ expression, type)
        """
        # Use std::vector<EngageValue> for mixed-type support
        return "std::vector<EngageValue>()", "std::vector<EngageValue>"
    
    def visit_IndexAccessNode(self, node):
        """
        Handle indexed access for Tables and Vectors with proper type checking.
        
        Implements bracket notation reading for both vector and table indexing
        with appropriate type checking and bounds checking. Generates proper
        C++ container access with error handling.
        
        Requirements: 4.3
        
        Args:
            node: IndexAccessNode AST node containing object and index
            
        Returns:
            Tuple of (C++ expression, return type)
        """
        container_cpp, container_type = self.visit(node.object_node)
        index_cpp, index_type = self.visit(node.index_node)
        
        # Handle vector indexing (numeric index)
        if 'vector' in container_type.lower():
            # Convert index to size_t for vector access
            if index_type in ['EngageValue', 'const EngageValue&']:
                index_cpp = f"static_cast<size_t>(({index_cpp}).as_number())"
            elif index_type == 'double':
                index_cpp = f"static_cast<size_t>({index_cpp})"
            
            # Add bounds checking for safety
            return f"({container_cpp}.at({index_cpp}))", "EngageValue"
        
        # Handle table indexing (string key)
        elif 'map' in container_type.lower():
            # Convert index to string for table access
            if index_type in ['EngageValue', 'const EngageValue&']:
                index_cpp = f"({index_cpp}).as_string()"
            elif index_type == 'double':
                index_cpp = f"std::to_string(static_cast<int>({index_cpp}))"
            elif index_type not in ['string', 'std::string']:
                index_cpp = f"EngageValue({index_cpp}).as_string()"
            
            # Use at() for bounds checking with tables
            return f"({container_cpp}.at({index_cpp}))", "EngageValue"
        
        # Default case - assume EngageValue container
        else:
            # For EngageValue containers, we need runtime type checking
            return f"({container_cpp})[{index_cpp}]", "EngageValue"
    
    def visit_IndexAssignNode(self, node):
        """
        Handle indexed assignment for Tables and Vectors with proper type checking.
        
        Implements bracket notation assignment for both vector and table indexing
        with appropriate type checking and bounds checking. Generates proper
        C++ container assignment with error handling.
        
        Requirements: 4.3
        
        Args:
            node: IndexAssignNode AST node containing object, index, and value
            
        Returns:
            Tuple of (C++ expression, return type)
        """
        container_cpp, container_type = self.visit(node.object_node)
        index_cpp, index_type = self.visit(node.index_node)
        value_cpp, value_type = self.visit(node.value_node)
        
        # Convert value to EngageValue if needed
        if value_type not in ['EngageValue', 'const EngageValue&']:
            value_cpp = f"EngageValue({value_cpp})"
        
        # Handle vector assignment (numeric index)
        if 'vector' in container_type.lower():
            # Convert index to size_t for vector access
            if index_type in ['EngageValue', 'const EngageValue&']:
                index_cpp = f"static_cast<size_t>(({index_cpp}).as_number())"
            elif index_type == 'double':
                index_cpp = f"static_cast<size_t>({index_cpp})"
            
            # Use at() for bounds checking
            return f"{container_cpp}.at({index_cpp}) = {value_cpp}", "Void"
        
        # Handle table assignment (string key)
        elif 'map' in container_type.lower():
            # Convert index to string for table access
            if index_type in ['EngageValue', 'const EngageValue&']:
                index_cpp = f"({index_cpp}).as_string()"
            elif index_type == 'double':
                index_cpp = f"std::to_string(static_cast<int>({index_cpp}))"
            elif index_type not in ['string', 'std::string']:
                index_cpp = f"EngageValue({index_cpp}).as_string()"
            
            # Use [] operator for table assignment (creates key if not exists)
            return f"{container_cpp}[{index_cpp}] = {value_cpp}", "Void"
        
        # Default case - assume EngageValue container
        else:
            # For EngageValue containers, we need runtime type checking
            return f"{container_cpp}[{index_cpp}] = {value_cpp}", "Void"
    
    def visit_PropertyDefNode(self, node):
        """
        Enhanced property definition visitor for member variable generation.
        
        Implements comprehensive property support including:
        - Default value assignment and type inference
        - Proper C++ member variable declarations
        - Support for property access and modification through methods
        - Type mapping from Engage types to C++ types
        
        Requirements: 5.2
        
        Args:
            node: PropertyDefNode containing property name and default value
            
        Returns:
            (cpp_declaration, "Void") - C++ member variable declaration
        """
        prop_name = node.name_token.value
        
        # Handle default value and type inference
        if node.default_value:
            default_val, engage_type = self.visit(node.default_value)
            cpp_type = self._map_engage_type_to_cpp(engage_type)
        else:
            # No default value provided, use EngageValue with None
            default_val = "EngageValue()"
            cpp_type = "EngageValue"
            engage_type = "EngageValue"
        
        # Generate C++ member variable declaration
        cpp_declaration = f"{cpp_type} {prop_name} = {default_val};"
        
        # If we're in a record context, add this property to the record definition
        if self.current_record_name:
            record_def = self.get_record_definition(self.current_record_name)
            if record_def:
                record_def.add_property(prop_name, cpp_type, default_val)
        
        return cpp_declaration, "Void"
    
    def visit_ImportNode(self, node):
        """Handle import statements."""
        # For basic transpilation, imports are not directly supported
        # This would require a more sophisticated module system
        module_name = node.module_name.value
        self.add_comment(f"Import statement: {module_name} (not supported in C++ transpilation)", global_scope=True)
        return "", "Void"
    
    def visit_FromImportNode(self, node):
        """Handle from...import statements."""
        # For basic transpilation, imports are not directly supported
        module_name = node.module_name.value
        symbols = [item.name.value for item in node.import_items]
        self.add_comment(f"From import statement: from {module_name} import {', '.join(symbols)} (not supported in C++ transpilation)", global_scope=True)
        return "", "Void"
    
    def visit_ExportVarNode(self, node):
        """Handle export variable statements."""
        # For basic transpilation, treat as regular variable assignment
        var_name = node.name_token.value
        value_cpp, value_type = self.visit(node.value_node)
        self.add_symbol(var_name, value_type)
        return f"{value_type} {var_name} = {value_cpp}", "Void"
    
    def visit_ExportFuncNode(self, node):
        """Handle export function statements."""
        # For basic transpilation, treat as regular function definition
        return self.visit_FuncDefNode(node)
    
    def visit_TypeNameNode(self, node):
        """Handle type name references."""
        type_name = node.type_token.value
        # For basic transpilation, just return the type name
        return type_name, "type"

    def visit_ResultNode(self, node):
        """
        Handle Result type constructors (Ok/Error).
        
        Implements visit_ResultNode method for Ok/Error result creation.
        Handles result value wrapping and error message assignment.
        Generates proper C++ Result template instantiation.
        Supports both value and error result types.
        
        Requirements: 7.2
        
        Args:
            node: ResultNode AST node with type_token ('Ok' or 'Error') and value_node
            
        Returns:
            Tuple of (cpp_code, cpp_type) for the Result creation
        """
        # Enable Result type usage
        self.enable_result_types()
        
        result_type = node.type_token.value
        
        if node.value_node:
            value_cpp, value_type = self.visit(node.value_node)
        else:
            # Handle cases where there's no value (e.g., just "Ok" or "Error")
            value_cpp = '""'
            value_type = "string"
        
        if result_type == 'Ok':
            # Generate Result<T>::Ok(value) factory method call
            result_cpp = f"Result<{value_type}>::Ok({value_cpp})"
            result_type_name = f"Result<{value_type}>"
            return result_cpp, result_type_name
            
        elif result_type == 'Error':
            # Generate Result<T>::Error(message) factory method call
            # For Error results, we need to determine the expected return type
            # If we're in a function context, use the function's return type
            if self.current_function_name:
                func_sig = self.get_function_signature(self.current_function_name)
                if func_sig and func_sig.return_type != "auto":
                    expected_type = func_sig.return_type
                    if expected_type.startswith("Result<"):
                        # Extract the inner type from Result<T>
                        inner_type = expected_type[7:-1]  # Remove "Result<" and ">"
                        result_cpp = f"Result<{inner_type}>::Error({value_cpp})"
                        result_type_name = f"Result<{inner_type}>"
                        return result_cpp, result_type_name
            
            # Default to EngageValue if we can't determine the type
            result_cpp = f"Result<EngageValue>::Error({value_cpp})"
            result_type_name = "Result<EngageValue>"
            return result_cpp, result_type_name
            
        else:
            raise Exception(f"Unknown Result type: {result_type}")

# --- Command-Line Interface Implementation ---

import argparse
import os

def create_argument_parser():
    """
    Create and configure the command-line argument parser.
    
    Provides clear usage instructions, help text, and argument validation
    for the transpiler CLI interface.
    
    Requirements: 1.1, 4.3
    
    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog='engage_transpiler',
        description='Engage Language Transpiler - Convert .engage files to C++ code',
        epilog='''
Examples:
  python engage_transpiler.py hello_world.engage
  python engage_transpiler.py --output my_program.cpp input.engage
  python engage_transpiler.py --verbose --no-debug fibonacci.engage
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Required positional argument for input file
    parser.add_argument(
        'input_file',
        help='Path to the .engage source file to transpile'
    )
    
    # Optional output file specification
    parser.add_argument(
        '-o', '--output',
        help='Output C++ file path (default: input_file.cpp)',
        metavar='OUTPUT_FILE'
    )
    
    # Verbose output option
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output showing lexer and parser details'
    )
    
    # Debug output control
    parser.add_argument(
        '--no-debug',
        action='store_true',
        help='Disable debug output (tokens, AST, etc.)'
    )
    
    # Version information
    parser.add_argument(
        '--version',
        action='version',
        version='Engage Transpiler v1.0'
    )
    
    return parser

def validate_input_file(filepath):
    """
    Validate the input file path and extension.
    
    Ensures the input file exists, is readable, and has the correct .engage extension.
    Provides clear error messages for common issues.
    
    Requirements: 1.1, 4.3
    
    Args:
        filepath: Path to the input file
        
    Returns:
        True if valid, raises SystemExit with error message if invalid
    """
    # Check if file exists
    if not os.path.exists(filepath):
        print(f"Error: Input file '{filepath}' does not exist.")
        print("Please check the file path and try again.")
        sys.exit(1)
    
    # Check if it's a file (not a directory)
    if not os.path.isfile(filepath):
        print(f"Error: '{filepath}' is not a file.")
        print("Please provide a path to a .engage source file.")
        sys.exit(1)
    
    # Check file extension
    if not filepath.lower().endswith('.engage'):
        print(f"Warning: Input file '{filepath}' does not have .engage extension.")
        print("The transpiler expects .engage files, but will attempt to process it anyway.")
    
    # Check if file is readable
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Try to read a small portion to verify readability
            f.read(1)
    except PermissionError:
        print(f"Error: Permission denied reading '{filepath}'.")
        print("Please check file permissions and try again.")
        sys.exit(1)
    except UnicodeDecodeError:
        print(f"Error: '{filepath}' contains invalid UTF-8 characters.")
        print("Please ensure the file is saved with UTF-8 encoding.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: Cannot read '{filepath}': {e}")
        sys.exit(1)
    
    return True

def generate_output_filename(input_filepath, output_arg=None):
    """
    Generate the output filename for the C++ file.
    
    Uses the provided output argument or generates a default name based on
    the input file with .cpp extension.
    
    Requirements: 4.3
    
    Args:
        input_filepath: Path to the input .engage file
        output_arg: Optional output filename from command line
        
    Returns:
        Output filename for the C++ file
    """
    if output_arg:
        # Use the specified output filename
        output_filename = output_arg
        
        # Add .cpp extension if not present
        if not output_filename.lower().endswith('.cpp'):
            output_filename += '.cpp'
    else:
        # Generate default output filename
        base_name = os.path.splitext(input_filepath)[0]
        output_filename = base_name + '.cpp'
    
    return output_filename

def read_engage_file(filepath):
    """
    Read an Engage source file with comprehensive error handling.
    
    Handles various file reading errors and provides clear error messages
    for different failure scenarios.
    
    Requirements: 4.1, 4.3
    
    Args:
        filepath: Path to the .engage file to read
        
    Returns:
        File contents as string
        
    Raises:
        SystemExit: On any file reading error with appropriate error message
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check if file is empty
        if not content.strip():
            print(f"Warning: Input file '{filepath}' is empty.")
            print("The transpiler will generate a minimal C++ program.")
            
        return content
        
    except FileNotFoundError:
        print(f"Error: Input file '{filepath}' not found.")
        print("Please check the file path and ensure the file exists.")
        sys.exit(1)
        
    except PermissionError:
        print(f"Error: Permission denied reading '{filepath}'.")
        print("Please check file permissions and try again.")
        print("You may need to run as administrator or change file permissions.")
        sys.exit(1)
        
    except UnicodeDecodeError as e:
        print(f"Error: '{filepath}' contains invalid UTF-8 characters.")
        print(f"Encoding error at position {e.start}: {e.reason}")
        print("Please ensure the file is saved with UTF-8 encoding.")
        sys.exit(1)
        
    except IsADirectoryError:
        print(f"Error: '{filepath}' is a directory, not a file.")
        print("Please provide a path to a .engage source file.")
        sys.exit(1)
        
    except OSError as e:
        print(f"Error: System error reading '{filepath}': {e}")
        print("This may be due to file system issues or file corruption.")
        sys.exit(1)
        
    except Exception as e:
        print(f"Error: Unexpected error reading '{filepath}': {e}")
        print("Please check the file and try again.")
        sys.exit(1)

def write_cpp_file(filepath, cpp_code):
    """
    Write C++ code to output file with comprehensive error handling.
    
    Creates output directories if needed and handles various file writing
    errors with clear error messages.
    
    Requirements: 4.1, 4.3
    
    Args:
        filepath: Path where to write the C++ file
        cpp_code: C++ code content to write
        
    Returns:
        True if successful
        
    Raises:
        SystemExit: On any file writing error with appropriate error message
    """
    try:
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(filepath)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
                print(f"Created output directory: {output_dir}")
            except OSError as e:
                print(f"Error: Cannot create output directory '{output_dir}': {e}")
                print("Please check permissions or create the directory manually.")
                sys.exit(1)
        
        # Check if output file already exists and warn user
        if os.path.exists(filepath):
            print(f"Warning: Output file '{filepath}' already exists and will be overwritten.")
        
        # Write the C++ code to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(cpp_code)
            
        # Verify the file was written correctly
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                written_content = f.read()
                if written_content != cpp_code:
                    print(f"Error: File verification failed for '{filepath}'.")
                    print("The written content doesn't match the generated code.")
                    sys.exit(1)
        except Exception:
            print(f"Warning: Could not verify written file '{filepath}'.")
            print("The file may have been written successfully, but verification failed.")
            
        return True
        
    except PermissionError:
        print(f"Error: Permission denied writing to '{filepath}'.")
        print("Please check file permissions or choose a different output location.")
        print("You may need to run as administrator or change directory permissions.")
        sys.exit(1)
        
    except OSError as e:
        if e.errno == 28:  # No space left on device
            print(f"Error: No space left on device when writing '{filepath}'.")
            print("Please free up disk space and try again.")
        elif e.errno == 36:  # File name too long
            print(f"Error: Output filename '{filepath}' is too long.")
            print("Please use a shorter filename.")
        else:
            print(f"Error: System error writing '{filepath}': {e}")
            print("This may be due to file system issues or insufficient permissions.")
        sys.exit(1)
        
    except UnicodeEncodeError as e:
        print(f"Error: Cannot encode C++ code to UTF-8 for '{filepath}'.")
        print(f"Encoding error: {e.reason}")
        print("This may indicate an issue with the generated C++ code.")
        sys.exit(1)
        
    except Exception as e:
        print(f"Error: Unexpected error writing '{filepath}': {e}")
        print("Please check the output location and try again.")
        sys.exit(1)

def validate_output_path(filepath):
    """
    Validate the output file path before attempting to write.
    
    Checks if the output path is valid and writable, providing early
    error detection before transpilation begins.
    
    Requirements: 4.1, 4.3
    
    Args:
        filepath: Path where the C++ file will be written
        
    Returns:
        True if valid, raises SystemExit with error message if invalid
    """
    # Check if the path is absolute or relative
    if os.path.isabs(filepath):
        # Absolute path - check if parent directory exists
        parent_dir = os.path.dirname(filepath)
        if parent_dir and not os.path.exists(parent_dir):
            print(f"Error: Output directory '{parent_dir}' does not exist.")
            print("Please create the directory or use a different output path.")
            return False
    
    # Check if we can write to the parent directory
    parent_dir = os.path.dirname(filepath) or '.'
    if not os.access(parent_dir, os.W_OK):
        print(f"Error: No write permission for directory '{parent_dir}'.")
        print("Please choose a different output location or check permissions.")
        return False
    
    # Check if output file exists and is writable
    if os.path.exists(filepath):
        if not os.access(filepath, os.W_OK):
            print(f"Error: Output file '{filepath}' exists but is not writable.")
            print("Please check file permissions or choose a different filename.")
            return False
    
    # Check for invalid characters in filename (Windows-specific)
    if os.name == 'nt':  # Windows
        invalid_chars = '<>:"|?*'
        filename = os.path.basename(filepath)
        for char in invalid_chars:
            if char in filename:
                print(f"Error: Invalid character '{char}' in filename '{filename}'.")
                print("Please use a filename without special characters.")
                return False
    
    return True

def print_usage_help():
    """
    Print helpful usage information and examples.
    
    Provides clear guidance on how to use the transpiler effectively.
    
    Requirements: 4.3
    """
    print("Engage Language Transpiler")
    print("=" * 25)
    print()
    print("This tool converts Engage language source files (.engage) to C++ code.")
    print()
    print("Basic Usage:")
    print("  python engage_transpiler.py filename.engage")
    print()
    print("Advanced Usage:")
    print("  python engage_transpiler.py -o output.cpp input.engage")
    print("  python engage_transpiler.py --verbose program.engage")
    print("  python engage_transpiler.py --help")
    print()
    print("After transpilation, compile the C++ code with:")
    print("  cl output.cpp        (Windows with MSVC)")
    print("  g++ -o output output.cpp  (Linux/Mac with GCC)")
    print("  clang++ -o output output.cpp  (Linux/Mac with Clang)")

# --- Main Execution Block for Transpiler ---
if __name__ == '__main__':
    # Create and parse command-line arguments
    parser = create_argument_parser()
    
    # Handle case where no arguments are provided
    if len(sys.argv) == 1:
        print_usage_help()
        sys.exit(0)
    
    try:
        args = parser.parse_args()
    except SystemExit as e:
        # argparse calls sys.exit() on error, we catch it to provide additional help
        if e.code != 0:  # Error occurred
            print("\nFor more help, use: python engage_transpiler.py --help")
        sys.exit(e.code)
    
    # Validate input file
    validate_input_file(args.input_file)
    
    # Generate output filename
    output_filename = generate_output_filename(args.input_file, args.output)
    
    # Validate output path before proceeding
    if not validate_output_path(output_filename):
        sys.exit(1)
    
    # Read input file with comprehensive error handling
    engage_code = read_engage_file(args.input_file)
    
    # Display transpilation start message
    print(f"Transpiling '{args.input_file}' to C++...")
    if args.verbose:
        print(f"Output file: {output_filename}")
        print(f"Input file size: {len(engage_code)} characters")

    try:
        # 1. Lex the code
        lexer = Lexer(engage_code)
        tokens = lexer.tokenize()
        
        if args.verbose and not args.no_debug:
            print("\n--- LEXER OUTPUT (Tokens) ---")
            for token in tokens:
                print(token)

        # 2. Parse the tokens into an AST
        parser = Parser(tokens)
        ast = parser.parse()
        
        if args.verbose and not args.no_debug:
            print("\n--- PARSER OUTPUT (AST) ---")
            # A simple way to pretty-print the nested AST
            def default_serializer(o):
                if isinstance(o, ASTNode):
                    # Create a dict of the node's attributes, excluding private ones
                    node_dict = {k: v for k, v in o.__dict__.items() if not k.startswith('_')}
                    # Prepend the node's class name for clarity
                    return {f"<{o.__class__.__name__}>": node_dict}
                if isinstance(o, Token):
                    return f"Token({o.type}, '{o.value}')"
                return repr(o)
            print(json.dumps(ast, default=default_serializer, indent=2))

        # 3. Transpile the AST to C++ with enhanced error handling
        transpiler = Transpiler()
        cpp_code, success, error_report = transpiler.transpile(ast)

        # 4. Display transpilation results
        if success:
            print(f"\n[SUCCESS] Successfully transpiled to '{output_filename}'")
            
            # Write output file
            write_cpp_file(output_filename, cpp_code)
            
            if args.verbose and not args.no_debug:
                print("\n--- GENERATED C++ CODE ---")
                print(cpp_code)
            
            # Show any warnings
            if transpiler.has_warnings():
                print("\n--- WARNINGS ---")
                print(error_report)
        else:
            print(f"\n[ERROR] Transpilation completed with errors")
            
            # Still write partial output if possible
            if cpp_code and cpp_code.strip() != "/* Transpilation failed */":
                write_cpp_file(output_filename, cpp_code)
                print(f"Partial C++ code written to '{output_filename}'")
            
            # Display detailed error report
            print("\n--- ERROR REPORT ---")
            print(error_report)
            sys.exit(1)
        
        # Display compilation instructions (only on success or with warnings)
        if success:
            print("\n--- COMPILATION INSTRUCTIONS ---")
            compilation_lines = transpiler._generate_compilation_instructions()
            for line in compilation_lines:
                print(line)

    except Exception as e:
        print(f"\n[FATAL ERROR] Transpilation failed with unexpected error: {e}")
        if args.verbose:
            import traceback
            print("\nDetailed error information:")
            traceback.print_exc()
        print("\nThis may be a bug in the transpiler. Please report this issue.")
        sys.exit(1)
