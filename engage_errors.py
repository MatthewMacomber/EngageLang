# engage_errors.py
# Enhanced error reporting system for the Engage programming language

import re
from typing import List, Optional, Dict, Any

class EngageError:
    """
    Enhanced error class with context information for better error reporting.
    Provides detailed error messages with line/column positions, source context,
    and helpful suggestions for common mistakes.
    """
    
    def __init__(self, 
                 message: str, 
                 line: int, 
                 column: int, 
                 file_path: Optional[str] = None,
                 error_type: str = "Error",
                 source_lines: Optional[List[str]] = None,
                 suggestions: Optional[List[str]] = None):
        """
        Initialize an EngageError with comprehensive context information.
        
        Args:
            message: The primary error message
            line: Line number where error occurred (1-based)
            column: Column number where error occurred (1-based)
            file_path: Path to the source file (optional)
            error_type: Type of error (Syntax, Runtime, Type, etc.)
            source_lines: List of source code lines for context
            suggestions: List of suggested fixes or common causes
        """
        self.message = message
        self.line = line
        self.column = column
        self.file_path = file_path
        self.error_type = error_type
        self.source_lines = source_lines or []
        self.suggestions = suggestions or []
        
    def add_suggestion(self, suggestion: str):
        """Add a suggestion to help fix the error."""
        if suggestion not in self.suggestions:
            self.suggestions.append(suggestion)
    
    def set_source_context(self, source_lines: List[str]):
        """Set the source code lines for context display."""
        self.source_lines = source_lines
    
    def get_context_lines(self, context_size: int = 2) -> List[tuple]:
        """
        Get source lines around the error with line numbers.
        
        Args:
            context_size: Number of lines to show before and after error line
            
        Returns:
            List of tuples (line_number, line_content, is_error_line)
        """
        if not self.source_lines:
            return []
        
        start_line = max(1, self.line - context_size)
        end_line = min(len(self.source_lines), self.line + context_size)
        
        context_lines = []
        for line_num in range(start_line, end_line + 1):
            if line_num <= len(self.source_lines):
                line_content = self.source_lines[line_num - 1]
                is_error_line = (line_num == self.line)
                context_lines.append((line_num, line_content, is_error_line))
        
        return context_lines
    
    def format_error(self, show_context: bool = True, show_suggestions: bool = True) -> str:
        """
        Format the error as a comprehensive, user-friendly message.
        
        Args:
            show_context: Whether to include source code context
            show_suggestions: Whether to include suggestions
            
        Returns:
            Formatted error message string
        """
        lines = []
        
        # Header with file and location
        if self.file_path:
            lines.append(f"{self.error_type} in {self.file_path}:")
        else:
            lines.append(f"{self.error_type}:")
        
        # Main error message with location
        lines.append(f"  Line {self.line}, Column {self.column}: {self.message}")
        
        # Source code context
        if show_context and self.source_lines:
            lines.append("")
            context_lines = self.get_context_lines()
            
            for line_num, line_content, is_error_line in context_lines:
                # Line number and content
                prefix = ">>> " if is_error_line else "    "
                lines.append(f"{prefix}{line_num:3d} | {line_content}")
                
                # Error pointer for the error line
                if is_error_line:
                    pointer_line = "    " + " " * 4  # Account for line number formatting
                    pointer_line += " " * (self.column - 1) + "^"
                    lines.append(pointer_line)
        
        # Suggestions
        if show_suggestions and self.suggestions:
            lines.append("")
            lines.append("Suggestions:")
            for suggestion in self.suggestions:
                lines.append(f"  • {suggestion}")
        
        return "\n".join(lines)
    
    def __str__(self) -> str:
        """String representation of the error."""
        return self.format_error()
    
    def __repr__(self) -> str:
        """Debug representation of the error."""
        return (f"EngageError(message={repr(self.message)}, "
                f"line={self.line}, column={self.column}, "
                f"type={repr(self.error_type)})")


class ErrorAggregator:
    """
    Aggregates multiple errors for batch reporting.
    Useful for collecting all syntax errors in a single parse pass.
    """
    
    def __init__(self):
        self.errors: List[EngageError] = []
        self.source_lines: Optional[List[str]] = None
        self.file_path: Optional[str] = None
    
    def set_source_context(self, source_lines: List[str], file_path: Optional[str] = None):
        """Set source context that will be applied to all errors."""
        self.source_lines = source_lines
        self.file_path = file_path
        
        # Apply to existing errors
        for error in self.errors:
            if not error.source_lines:
                error.set_source_context(source_lines)
            if not error.file_path:
                error.file_path = file_path
    
    def add_error(self, error: EngageError):
        """Add an error to the aggregator."""
        # Apply source context if available
        if self.source_lines and not error.source_lines:
            error.set_source_context(self.source_lines)
        if self.file_path and not error.file_path:
            error.file_path = self.file_path
            
        self.errors.append(error)
    
    def create_error(self, 
                    message: str, 
                    line: int, 
                    column: int, 
                    error_type: str = "Error",
                    suggestions: Optional[List[str]] = None) -> EngageError:
        """
        Create and add an error to the aggregator.
        
        Returns:
            The created EngageError instance
        """
        error = EngageError(
            message=message,
            line=line,
            column=column,
            file_path=self.file_path,
            error_type=error_type,
            source_lines=self.source_lines,
            suggestions=suggestions
        )
        self.add_error(error)
        return error
    
    def has_errors(self) -> bool:
        """Check if any errors have been collected."""
        return len(self.errors) > 0
    
    def get_error_count(self) -> int:
        """Get the total number of errors."""
        return len(self.errors)
    
    def get_errors_by_type(self, error_type: str) -> List[EngageError]:
        """Get all errors of a specific type."""
        return [error for error in self.errors if error.error_type == error_type]
    
    def clear(self):
        """Clear all collected errors."""
        self.errors.clear()
    
    def format_all_errors(self, show_context: bool = True, show_suggestions: bool = True) -> str:
        """
        Format all collected errors as a comprehensive report.
        
        Args:
            show_context: Whether to include source code context
            show_suggestions: Whether to include suggestions
            
        Returns:
            Formatted error report string
        """
        if not self.errors:
            return "No errors found."
        
        lines = []
        
        # Summary
        error_count = len(self.errors)
        lines.append(f"Found {error_count} error{'s' if error_count != 1 else ''}:")
        lines.append("")
        
        # Individual errors
        for i, error in enumerate(self.errors, 1):
            lines.append(f"Error {i}:")
            error_text = error.format_error(show_context, show_suggestions)
            # Indent the error text
            indented_lines = ["  " + line for line in error_text.split("\n")]
            lines.extend(indented_lines)
            
            if i < len(self.errors):  # Add separator between errors
                lines.append("")
                lines.append("-" * 50)
                lines.append("")
        
        return "\n".join(lines)
    
    def __str__(self) -> str:
        """String representation showing all errors."""
        return self.format_all_errors()


class SourceContextExtractor:
    """
    Utility class for extracting source code context around errors.
    Handles reading source files and providing context lines.
    """
    
    @staticmethod
    def extract_from_text(source_text: str) -> List[str]:
        """
        Extract source lines from text content.
        
        Args:
            source_text: The complete source code as a string
            
        Returns:
            List of source lines
        """
        return source_text.splitlines()
    
    @staticmethod
    def extract_from_file(file_path: str) -> List[str]:
        """
        Extract source lines from a file.
        
        Args:
            file_path: Path to the source file
            
        Returns:
            List of source lines, or empty list if file cannot be read
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read().splitlines()
        except (IOError, OSError, UnicodeDecodeError):
            return []
    
    @staticmethod
    def get_context_around_line(source_lines: List[str], 
                               line_number: int, 
                               context_size: int = 2) -> List[tuple]:
        """
        Get context lines around a specific line number.
        
        Args:
            source_lines: List of all source lines
            line_number: Target line number (1-based)
            context_size: Number of lines before and after to include
            
        Returns:
            List of tuples (line_number, line_content, is_target_line)
        """
        if not source_lines or line_number < 1:
            return []
        
        start_line = max(1, line_number - context_size)
        end_line = min(len(source_lines), line_number + context_size)
        
        context_lines = []
        for line_num in range(start_line, end_line + 1):
            if line_num <= len(source_lines):
                line_content = source_lines[line_num - 1]
                is_target_line = (line_num == line_number)
                context_lines.append((line_num, line_content, is_target_line))
        
        return context_lines


class ErrorSuggestionEngine:
    """
    Provides intelligent suggestions for common Engage programming errors.
    Analyzes error patterns and suggests likely fixes.
    """
    
    # Common keyword suggestions for typos
    KEYWORD_SUGGESTIONS = {
        'let': ['let', 'set'],
        'be': ['be', 'is'],
        'to': ['to', 'do'],
        'if': ['if', 'when'],
        'then': ['then', 'do'],
        'otherwise': ['otherwise', 'else'],
        'end': ['end', 'done'],
        'while': ['while', 'until'],
        'return': ['return', 'returns'],
        'function': ['to', 'define'],
        'define': ['define', 'create'],
        'new': ['new', 'create'],
        'with': ['with', 'using'],
        'property': ['property', 'field'],
        'record': ['record', 'class', 'type'],
        'Table': ['Table', 'Map', 'Dictionary'],
        'Vector': ['Vector', 'Array', 'List']
    }
    
    # Error message templates for common error types
    ERROR_TEMPLATES = {
        'undefined_variable': {
            'pattern': r"'(\w+)' is not defined",
            'template': "Variable '{name}' is not defined",
            'suggestions': [
                "Check the spelling of the variable name",
                "Make sure the variable is declared with 'let' before use",
                "Check if the variable is in the correct scope"
            ]
        },
        'undefined_function': {
            'pattern': r"'(\w+)' is not a function",
            'template': "'{name}' is not a function or is not defined",
            'suggestions': [
                "Check the spelling of the function name",
                "Make sure the function is defined with 'to' before calling it",
                "Check if you're trying to call a variable as a function"
            ]
        },
        'division_by_zero': {
            'pattern': r"Division by zero",
            'template': "Cannot divide by zero",
            'suggestions': [
                "Check that the divisor is not zero before performing division",
                "Add a condition to handle zero values",
                "Use a default value when the divisor might be zero"
            ]
        },
        'type_mismatch': {
            'pattern': r"Unsupported operand types for (\w+)",
            'template': "Cannot perform operation '{operation}' on these types",
            'suggestions': [
                "Check that both operands are the correct type for this operation",
                "Use type conversion functions if needed (like number())",
                "Make sure you're using the right operator for your data types"
            ]
        },
        'invalid_index': {
            'pattern': r"Vector indices must be (integers|numbers)",
            'template': "Vector index must be a number (integer)",
            'suggestions': [
                "Use a number for the vector index, like vector[0]",
                "Convert your index to a number using the number() function",
                "Check that your index expression evaluates to a number"
            ]
        },
        'invalid_key': {
            'pattern': r"Table keys must be strings",
            'template': "Table key must be a string",
            'suggestions': [
                "Use double quotes around your table key, like table[\"key\"]",
                "Convert your key to a string if needed",
                "Check that your key expression evaluates to a string"
            ]
        },
        'missing_end': {
            'pattern': r"Expected 'end'",
            'template': "Missing 'end' keyword to close block",
            'suggestions': [
                "Add 'end' to close your if/while/function/record block",
                "Check that all opened blocks have matching 'end' keywords",
                "Make sure your block structure is properly nested"
            ]
        },
        'missing_period': {
            'pattern': r"Expected period",
            'template': "Missing period (.) at end of statement",
            'suggestions': [
                "Add a period (.) at the end of your statement",
                "Check that your statement is complete before the line break",
                "Make sure you haven't forgotten any parts of your statement"
            ]
        },
        'wrong_argument_count': {
            'pattern': r"Function '(\w+)' takes (\d+) arguments but (\d+) were given",
            'template': "Function '{name}' expects {expected} arguments but got {actual}",
            'suggestions': [
                "Check the function definition to see how many parameters it expects",
                "Add missing arguments or remove extra ones",
                "Make sure you're calling the right function"
            ]
        },
        'cannot_convert': {
            'pattern': r"Cannot convert '(.+)' to number",
            'template': "Cannot convert '{value}' to a number",
            'suggestions': [
                "Check that the value contains only numeric characters",
                "Remove any non-numeric characters from the input",
                "Use a default value if conversion fails"
            ]
        }
    }
    
    # Common built-in function names for spell checking
    BUILTIN_FUNCTIONS = [
        'print', 'input', 'number', 'length', 'substring', 'split', 'join',
        'to_upper', 'to_lower', 'sqrt', 'pow', 'abs', 'min', 'max',
        'sin', 'cos', 'tan', 'read_file', 'write_file', 'file_exists',
        'create_directory', 'map', 'filter', 'reduce', 'sort',
        'type_of', 'is_number', 'is_string', 'is_table', 'is_vector'
    ]
    
    @staticmethod
    def suggest_for_undefined_variable(var_name: str, available_vars: List[str]) -> List[str]:
        """
        Suggest corrections for undefined variable names with enhanced spell checking.
        
        Args:
            var_name: The undefined variable name
            available_vars: List of available variable names in scope
            
        Returns:
            List of suggested variable names
        """
        suggestions = []
        
        # Exact case-insensitive match
        for var in available_vars:
            if var.lower() == var_name.lower() and var != var_name:
                suggestions.append(f"Did you mean '{var}' (check capitalization)?")
        
        # Enhanced spell checking with multiple algorithms
        close_matches = ErrorSuggestionEngine._enhanced_spell_check(var_name, available_vars)
        for match, reason in close_matches:
            suggestions.append(f"Did you mean '{match}'? ({reason})")
        
        # Common variable naming patterns
        if '_' not in var_name and any('_' in var for var in available_vars):
            snake_case = var_name.replace(' ', '_').lower()
            if snake_case in available_vars:
                suggestions.append(f"Did you mean '{snake_case}' (use underscores)?")
        
        # Check for common typos in variable names
        typo_suggestions = ErrorSuggestionEngine._check_common_variable_typos(var_name, available_vars)
        suggestions.extend(typo_suggestions)
        
        return suggestions[:4]  # Limit to top 4 suggestions
    
    @staticmethod
    def suggest_for_undefined_function(func_name: str, available_functions: List[str] = None) -> List[str]:
        """
        Suggest corrections for undefined function names with enhanced spell checking.
        
        Args:
            func_name: The undefined function name
            available_functions: List of available function names in scope
            
        Returns:
            List of suggested function names
        """
        suggestions = []
        all_functions = (available_functions or []) + ErrorSuggestionEngine.BUILTIN_FUNCTIONS
        
        # Exact case-insensitive match
        for func in all_functions:
            if func.lower() == func_name.lower() and func != func_name:
                suggestions.append(f"Did you mean '{func}' (check capitalization)?")
        
        # Enhanced spell checking for functions
        close_matches = ErrorSuggestionEngine._enhanced_spell_check(func_name, all_functions)
        for match, reason in close_matches:
            if match in ErrorSuggestionEngine.BUILTIN_FUNCTIONS:
                suggestions.append(f"Did you mean built-in function '{match}'? ({reason})")
            else:
                suggestions.append(f"Did you mean '{match}'? ({reason})")
        
        # Check for common function name patterns
        if func_name.endswith('_'):
            base_name = func_name[:-1]
            if base_name in all_functions:
                suggestions.append(f"Did you mean '{base_name}' (remove trailing underscore)?")
        
        # Check for missing 'to' keyword in function definitions
        if not suggestions:
            suggestions.append("If you're trying to define a function, use 'to function_name:'")
            suggestions.append("If you're trying to call a function, make sure it's defined first")
        
        return suggestions[:4]  # Limit to top 4 suggestions
    
    @staticmethod
    def suggest_for_syntax_error(error_message: str, context: str = "") -> List[str]:
        """
        Suggest fixes for syntax errors based on error patterns and templates.
        
        Args:
            error_message: The syntax error message
            context: Additional context about where the error occurred
            
        Returns:
            List of suggested fixes
        """
        suggestions = []
        error_lower = error_message.lower()
        
        # Check against error templates first
        template_suggestions = ErrorSuggestionEngine._get_template_suggestions(error_message)
        suggestions.extend(template_suggestions)
        
        # Missing period suggestions
        if "expected" in error_lower and "." in error_lower:
            suggestions.append("Make sure to end your statement with a period (.)")
            suggestions.append("Check if you have unfinished expressions before the line break")
        
        # Missing 'end' keyword
        if "expected" in error_lower and "end" in error_lower:
            suggestions.append("Make sure to close your block with 'end'")
            suggestions.append("Check if you have unmatched if/while/function/record definitions")
        
        # EOL/EOF errors
        if "end of line" in error_lower or "end of file" in error_lower:
            suggestions.append("Make sure your statement is complete before the line break")
            suggestions.append("Check for missing keywords or operators")
        
        # Keyword suggestions with enhanced spell checking
        if "expected keyword" in error_lower:
            for keyword, alternatives in ErrorSuggestionEngine.KEYWORD_SUGGESTIONS.items():
                if keyword in error_lower:
                    alt_list = "', '".join(alternatives)
                    suggestions.append(f"Did you mean one of: '{alt_list}'?")
                    break
        
        # Enhanced bracket/parentheses suggestions
        if "bracket" in error_lower or "parenthes" in error_lower:
            suggestions.append("Check for matching brackets [] and parentheses ()")
            suggestions.append("Make sure all opened brackets are properly closed")
            if "table" in context.lower():
                suggestions.append("For table access, use table[\"key\"] with string keys")
            if "vector" in context.lower():
                suggestions.append("For vector access, use vector[0] with numeric indices")
        
        # String literal issues
        if "string" in error_lower and "quote" in error_lower:
            suggestions.append("Make sure string literals are properly quoted with double quotes")
            suggestions.append("Check for unescaped quotes within string literals")
        
        # Function definition suggestions
        if "function" in error_lower and "definition" in error_lower:
            suggestions.append("Use 'to function_name:' to define a function")
            suggestions.append("Make sure to end function definitions with 'end'")
        
        # Record definition suggestions
        if "record" in error_lower:
            suggestions.append("Use 'to define RecordName:' to define a record")
            suggestions.append("Use 'property name with default_value.' for record properties")
        
        return suggestions[:4]  # Limit to top 4 suggestions
    
    @staticmethod
    def suggest_for_type_error(error_message: str, expected_type: str = "", actual_type: str = "") -> List[str]:
        """
        Suggest fixes for type errors.
        
        Args:
            error_message: The type error message
            expected_type: Expected type name
            actual_type: Actual type name
            
        Returns:
            List of suggested fixes
        """
        suggestions = []
        
        # Number conversion suggestions
        if "number" in error_message.lower():
            suggestions.append("Use the number() function to convert strings to numbers")
            suggestions.append("Check if your input contains non-numeric characters")
        
        # String concatenation suggestions
        if "concatenat" in error_message.lower():
            suggestions.append("Use 'concatenated with' to join strings")
            suggestions.append("Convert numbers to strings before concatenation if needed")
        
        # Table/Vector access suggestions
        if "table" in error_message.lower() and "key" in error_message.lower():
            suggestions.append("Table keys must be strings - use double quotes")
            suggestions.append("Check if the table exists and has been initialized")
        
        if "vector" in error_message.lower() and ("index" in error_message.lower() or "indices" in error_message.lower()):
            suggestions.append("Vector indices must be numbers (integers)")
            suggestions.append("Check if the index is within the vector bounds")
        
        # Record/instance suggestions
        if "record" in error_message.lower() or "instance" in error_message.lower():
            suggestions.append("Make sure the record is defined before creating instances")
            suggestions.append("Check property names and method calls for typos")
        
        return suggestions[:3]  # Limit to top 3 suggestions
    
    @staticmethod
    def _get_template_suggestions(error_message: str) -> List[str]:
        """
        Get suggestions based on error message templates.
        
        Args:
            error_message: The error message to match against templates
            
        Returns:
            List of suggestions from matching templates
        """
        suggestions = []
        
        for template_name, template_info in ErrorSuggestionEngine.ERROR_TEMPLATES.items():
            pattern = template_info['pattern']
            if re.search(pattern, error_message):
                suggestions.extend(template_info['suggestions'])
                break  # Use first matching template
        
        return suggestions
    
    @staticmethod
    def _enhanced_spell_check(target: str, candidates: List[str], max_distance: int = 3) -> List[tuple]:
        """
        Enhanced spell checking using multiple algorithms.
        
        Args:
            target: Target string to match
            candidates: List of candidate strings
            max_distance: Maximum edit distance to consider
            
        Returns:
            List of tuples (match, reason) sorted by relevance
        """
        matches = []
        
        # Levenshtein distance matches
        for candidate in candidates:
            distance = ErrorSuggestionEngine._levenshtein_distance(target, candidate)
            if distance <= max_distance and distance > 0:
                if distance == 1:
                    reason = "1 character difference"
                else:
                    reason = f"{distance} character differences"
                matches.append((distance, candidate, reason))
        
        # Prefix matches (for partial typing)
        for candidate in candidates:
            if candidate.lower().startswith(target.lower()) and candidate != target:
                matches.append((0.5, candidate, "starts with your input"))
        
        # Substring matches (for partial recall)
        for candidate in candidates:
            if target.lower() in candidate.lower() and candidate != target:
                matches.append((1.5, candidate, "contains your input"))
        
        # Special handling for short names (common abbreviations)
        if len(target) <= 4:
            for candidate in candidates:
                if candidate.startswith(target) and len(candidate) <= len(target) + 2:
                    matches.append((0.8, candidate, "short name match"))
        
        # Sort by distance/relevance and return top matches
        matches.sort(key=lambda x: x[0])
        return [(match[1], match[2]) for match in matches[:3]]
    
    @staticmethod
    def _check_common_variable_typos(var_name: str, available_vars: List[str]) -> List[str]:
        """
        Check for common variable naming typos and patterns.
        
        Args:
            var_name: The variable name to check
            available_vars: List of available variables
            
        Returns:
            List of suggestions for common typos
        """
        suggestions = []
        
        # Common typos: missing/extra characters
        common_typos = {
            'lenght': 'length',
            'widht': 'width',
            'heigth': 'height',
            'postion': 'position',
            'positon': 'position',
            'colum': 'column',
            'columm': 'column',
            'indx': 'index',
            'idx': 'index',
            'cnt': 'count',
            'num': 'number',
            'str': 'string',
            'val': 'value',
            'tmp': 'temp',
            'usr': 'user'
        }
        
        if var_name.lower() in common_typos:
            correct_form = common_typos[var_name.lower()]
            if correct_form in available_vars:
                suggestions.append(f"Did you mean '{correct_form}' (common typo)?")
        
        # Check for transposed characters
        for var in available_vars:
            if len(var) == len(var_name) and ErrorSuggestionEngine._is_transposition(var_name, var):
                suggestions.append(f"Did you mean '{var}' (transposed characters)?")
        
        return suggestions[:2]  # Limit to avoid overwhelming
    
    @staticmethod
    def _is_transposition(str1: str, str2: str) -> bool:
        """
        Check if two strings differ by exactly one character transposition.
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            True if strings differ by one transposition
        """
        if len(str1) != len(str2) or str1 == str2:
            return False
        
        differences = []
        for i, (c1, c2) in enumerate(zip(str1, str2)):
            if c1 != c2:
                differences.append(i)
        
        # Check if exactly 2 differences and they are adjacent transpositions
        if len(differences) == 2:
            i, j = differences
            if j == i + 1 and str1[i] == str2[j] and str1[j] == str2[i]:
                return True
        
        return False
    
    @staticmethod
    def _find_close_matches(target: str, candidates: List[str], max_distance: int = 2) -> List[str]:
        """
        Find close matches using simple edit distance (legacy method).
        
        Args:
            target: Target string to match
            candidates: List of candidate strings
            max_distance: Maximum edit distance to consider
            
        Returns:
            List of close matches sorted by distance
        """
        matches = []
        
        for candidate in candidates:
            distance = ErrorSuggestionEngine._levenshtein_distance(target, candidate)
            if distance <= max_distance and distance > 0:
                matches.append((distance, candidate))
        
        # Sort by distance and return just the strings
        matches.sort(key=lambda x: x[0])
        return [match[1] for match in matches[:3]]
    
    @staticmethod
    def _levenshtein_distance(s1: str, s2: str) -> int:
        """
        Calculate Levenshtein distance between two strings.
        
        Args:
            s1: First string
            s2: Second string
            
        Returns:
            Edit distance between the strings
        """
        if len(s1) < len(s2):
            return ErrorSuggestionEngine._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]


# Convenience functions for creating common error types
def create_syntax_error(message: str, line: int, column: int, 
                       file_path: Optional[str] = None,
                       source_lines: Optional[List[str]] = None) -> EngageError:
    """Create a syntax error with suggestions."""
    suggestions = ErrorSuggestionEngine.suggest_for_syntax_error(message)
    return EngageError(
        message=message,
        line=line,
        column=column,
        file_path=file_path,
        error_type="Syntax Error",
        source_lines=source_lines,
        suggestions=suggestions
    )

def create_runtime_error(message: str, line: int, column: int,
                        file_path: Optional[str] = None,
                        source_lines: Optional[List[str]] = None) -> EngageError:
    """Create a runtime error."""
    return EngageError(
        message=message,
        line=line,
        column=column,
        file_path=file_path,
        error_type="Runtime Error",
        source_lines=source_lines
    )

def create_type_error(message: str, line: int, column: int,
                     file_path: Optional[str] = None,
                     source_lines: Optional[List[str]] = None,
                     expected_type: str = "",
                     actual_type: str = "") -> EngageError:
    """Create a type error with suggestions."""
    suggestions = ErrorSuggestionEngine.suggest_for_type_error(message, expected_type, actual_type)
    return EngageError(
        message=message,
        line=line,
        column=column,
        file_path=file_path,
        error_type="Type Error",
        source_lines=source_lines,
        suggestions=suggestions
    )

def create_name_error(message: str, line: int, column: int,
                     file_path: Optional[str] = None,
                     source_lines: Optional[List[str]] = None,
                     undefined_name: str = "",
                     available_names: Optional[List[str]] = None,
                     is_function: bool = False) -> EngageError:
    """Create a name error with enhanced variable/function suggestions."""
    suggestions = []
    if undefined_name:
        if is_function:
            suggestions = ErrorSuggestionEngine.suggest_for_undefined_function(undefined_name, available_names)
        elif available_names:
            suggestions = ErrorSuggestionEngine.suggest_for_undefined_variable(undefined_name, available_names)
    
    return EngageError(
        message=message,
        line=line,
        column=column,
        file_path=file_path,
        error_type="Name Error",
        source_lines=source_lines,
        suggestions=suggestions
    )