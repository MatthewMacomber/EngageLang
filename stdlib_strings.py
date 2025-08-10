# stdlib_strings.py
"""
Engage Standard Library - Strings Module

Provides string manipulation functions for the Engage programming language.
"""

from typing import Dict, Callable
from engage_stdlib import BaseModule


class StringsModule(BaseModule):
    """
    Strings module providing string manipulation functions.
    """
    
    def get_functions(self) -> Dict[str, Callable]:
        """Return all string manipulation functions."""
        return {
            'length': self._length,
            'substring': self._substring,
            'split': self._split,
            'join': self._join,
            'to_upper': self._to_upper,
            'to_lower': self._to_lower,
        }
    
    def _length(self, args):
        """Get the length of a string."""
        from engage_interpreter import String, Number, ResultValue
        
        if len(args) != 1:
            return ResultValue('Error', String("length() expects exactly one argument."))
        
        if not hasattr(args[0], 'value'):
            return ResultValue('Error', String("length() argument must have a value."))
        
        if not isinstance(args[0].value, str):
            return ResultValue('Error', String("length() expects a string argument."))
        
        try:
            return Number(len(args[0].value))
        except Exception as e:
            return ResultValue('Error', String(f"length() failed: {str(e)}"))
    
    def _substring(self, args):
        """Extract a substring from a string."""
        from engage_interpreter import String, Number, ResultValue
        
        if len(args) < 2 or len(args) > 3:
            return ResultValue('Error', String("substring() expects 2 or 3 arguments (string, start, [end])."))
        
        # Validate string argument
        if not hasattr(args[0], 'value'):
            return ResultValue('Error', String("substring() first argument must have a value."))
        
        if not isinstance(args[0].value, str):
            return ResultValue('Error', String("substring() first argument must be a string."))
        
        # Validate start index
        if not hasattr(args[1], 'value'):
            return ResultValue('Error', String("substring() start index must have a value."))
        
        if not isinstance(args[1].value, (int, float)):
            return ResultValue('Error', String("substring() start index must be a number."))
        
        string_val = args[0].value
        start = int(args[1].value)
        
        # Validate start index bounds
        if start < 0:
            return ResultValue('Error', String("substring() start index cannot be negative."))
        
        if start > len(string_val):
            return ResultValue('Error', String("substring() start index exceeds string length."))
        
        try:
            if len(args) == 3:
                # Validate end index
                if not hasattr(args[2], 'value'):
                    return ResultValue('Error', String("substring() end index must have a value."))
                
                if not isinstance(args[2].value, (int, float)):
                    return ResultValue('Error', String("substring() end index must be a number."))
                
                end = int(args[2].value)
                
                # Validate end index bounds
                if end < 0:
                    return ResultValue('Error', String("substring() end index cannot be negative."))
                
                if end < start:
                    return ResultValue('Error', String("substring() end index cannot be less than start index."))
                
                if end > len(string_val):
                    end = len(string_val)  # Clamp to string length
                
                result = string_val[start:end]
            else:
                result = string_val[start:]
            
            return String(result)
        except Exception as e:
            return ResultValue('Error', String(f"substring() failed: {str(e)}"))
    
    def _split(self, args):
        """Split a string by a delimiter."""
        from engage_interpreter import String, ResultValue
        
        if len(args) != 2:
            return ResultValue('Error', String("split() expects exactly two arguments (string, delimiter)."))
        
        # Validate string argument
        if not hasattr(args[0], 'value'):
            return ResultValue('Error', String("split() first argument must have a value."))
        
        if not isinstance(args[0].value, str):
            return ResultValue('Error', String("split() first argument must be a string."))
        
        # Validate delimiter argument
        if not hasattr(args[1], 'value'):
            return ResultValue('Error', String("split() second argument must have a value."))
        
        if not isinstance(args[1].value, str):
            return ResultValue('Error', String("split() second argument (delimiter) must be a string."))
        
        string_val = args[0].value
        delimiter = args[1].value
        
        try:
            parts = string_val.split(delimiter)
            # Return as a simple string representation for now
            # In a full implementation, this would return a Vector
            return String(str(parts))
        except Exception as e:
            return ResultValue('Error', String(f"split() failed: {str(e)}"))
    
    def _join(self, args):
        """Join strings with a delimiter."""
        from engage_interpreter import String, ResultValue
        
        if len(args) < 2:
            return ResultValue('Error', String("join() expects at least two arguments (delimiter, string1, [string2, ...])."))
        
        # Validate delimiter argument
        if not hasattr(args[0], 'value'):
            return ResultValue('Error', String("join() first argument (delimiter) must have a value."))
        
        if not isinstance(args[0].value, str):
            return ResultValue('Error', String("join() first argument (delimiter) must be a string."))
        
        delimiter = args[0].value
        strings = []
        
        # Validate all string arguments
        for i, arg in enumerate(args[1:], 1):
            if not hasattr(arg, 'value'):
                return ResultValue('Error', String(f"join() argument {i+1} must have a value."))
            
            # Convert to string if not already a string
            try:
                strings.append(str(arg.value))
            except Exception as e:
                return ResultValue('Error', String(f"join() failed to convert argument {i+1} to string: {str(e)}"))
        
        try:
            result = delimiter.join(strings)
            return String(result)
        except Exception as e:
            return ResultValue('Error', String(f"join() failed: {str(e)}"))
    
    def _to_upper(self, args):
        """Convert a string to uppercase."""
        from engage_interpreter import String, ResultValue
        
        if len(args) != 1:
            return ResultValue('Error', String("to_upper() expects exactly one argument."))
        
        if not hasattr(args[0], 'value'):
            return ResultValue('Error', String("to_upper() argument must have a value."))
        
        if not isinstance(args[0].value, str):
            return ResultValue('Error', String("to_upper() expects a string argument."))
        
        try:
            return String(args[0].value.upper())
        except Exception as e:
            return ResultValue('Error', String(f"to_upper() failed: {str(e)}"))
    
    def _to_lower(self, args):
        """Convert a string to lowercase."""
        from engage_interpreter import String, ResultValue
        
        if len(args) != 1:
            return ResultValue('Error', String("to_lower() expects exactly one argument."))
        
        if not hasattr(args[0], 'value'):
            return ResultValue('Error', String("to_lower() argument must have a value."))
        
        if not isinstance(args[0].value, str):
            return ResultValue('Error', String("to_lower() expects a string argument."))
        
        try:
            return String(args[0].value.lower())
        except Exception as e:
            return ResultValue('Error', String(f"to_lower() failed: {str(e)}"))