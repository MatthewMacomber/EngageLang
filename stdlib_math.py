# stdlib_math.py
"""
Engage Standard Library - Math Module

Provides mathematical functions for the Engage programming language.
"""

import math
from typing import Dict, Callable
from engage_stdlib import BaseModule


class MathModule(BaseModule):
    """
    Math module providing mathematical functions.
    """
    
    def get_functions(self) -> Dict[str, Callable]:
        """Return all mathematical functions."""
        return {
            'sqrt': self._sqrt,
            'pow': self._pow,
            'abs': self._abs,
            'min': self._min,
            'max': self._max,
            'sin': self._sin,
            'cos': self._cos,
            'tan': self._tan,
        }
    
    def _sqrt(self, args):
        """Calculate the square root of a number."""
        from engage_interpreter import String, Number, ResultValue
        
        if len(args) != 1:
            return ResultValue('Error', String("sqrt() expects exactly one argument."))
        
        if not hasattr(args[0], 'value'):
            return ResultValue('Error', String("sqrt() argument must have a value."))
        
        if not isinstance(args[0].value, (int, float)):
            return ResultValue('Error', String("sqrt() expects a number argument."))
        
        value = args[0].value
        
        # Domain error check: negative numbers
        if value < 0:
            return ResultValue('Error', String("sqrt() domain error: cannot calculate square root of negative number."))
        
        try:
            result = math.sqrt(value)
            return Number(result)
        except Exception as e:
            return ResultValue('Error', String(f"sqrt() failed: {str(e)}"))
    
    def _pow(self, args):
        """Raise a number to a power."""
        from engage_interpreter import String, Number, ResultValue
        
        if len(args) != 2:
            return ResultValue('Error', String("pow() expects exactly two arguments (base, exponent)."))
        
        # Validate base argument
        if not hasattr(args[0], 'value'):
            return ResultValue('Error', String("pow() base argument must have a value."))
        
        if not isinstance(args[0].value, (int, float)):
            return ResultValue('Error', String("pow() base argument must be a number."))
        
        # Validate exponent argument
        if not hasattr(args[1], 'value'):
            return ResultValue('Error', String("pow() exponent argument must have a value."))
        
        if not isinstance(args[1].value, (int, float)):
            return ResultValue('Error', String("pow() exponent argument must be a number."))
        
        base = args[0].value
        exponent = args[1].value
        
        try:
            result = math.pow(base, exponent)
            return Number(result)
        except Exception as e:
            return ResultValue('Error', String(f"pow() failed: {str(e)}"))
    
    def _abs(self, args):
        """Calculate the absolute value of a number."""
        from engage_interpreter import String, Number, ResultValue
        
        if len(args) != 1:
            return ResultValue('Error', String("abs() expects exactly one argument."))
        
        if not hasattr(args[0], 'value'):
            return ResultValue('Error', String("abs() argument must have a value."))
        
        if not isinstance(args[0].value, (int, float)):
            return ResultValue('Error', String("abs() expects a number argument."))
        
        try:
            result = abs(args[0].value)
            return Number(result)
        except Exception as e:
            return ResultValue('Error', String(f"abs() failed: {str(e)}"))
    
    def _min(self, args):
        """Find the minimum value among the arguments."""
        from engage_interpreter import String, Number, ResultValue
        
        if len(args) < 2:
            return ResultValue('Error', String("min() expects at least two arguments."))
        
        values = []
        
        # Validate all arguments are numbers
        for i, arg in enumerate(args):
            if not hasattr(arg, 'value'):
                return ResultValue('Error', String(f"min() argument {i+1} must have a value."))
            
            if not isinstance(arg.value, (int, float)):
                return ResultValue('Error', String(f"min() argument {i+1} must be a number."))
            
            values.append(arg.value)
        
        try:
            result = min(values)
            return Number(result)
        except Exception as e:
            return ResultValue('Error', String(f"min() failed: {str(e)}"))
    
    def _max(self, args):
        """Find the maximum value among the arguments."""
        from engage_interpreter import String, Number, ResultValue
        
        if len(args) < 2:
            return ResultValue('Error', String("max() expects at least two arguments."))
        
        values = []
        
        # Validate all arguments are numbers
        for i, arg in enumerate(args):
            if not hasattr(arg, 'value'):
                return ResultValue('Error', String(f"max() argument {i+1} must have a value."))
            
            if not isinstance(arg.value, (int, float)):
                return ResultValue('Error', String(f"max() argument {i+1} must be a number."))
            
            values.append(arg.value)
        
        try:
            result = max(values)
            return Number(result)
        except Exception as e:
            return ResultValue('Error', String(f"max() failed: {str(e)}"))
    
    def _sin(self, args):
        """Calculate the sine of an angle in radians."""
        from engage_interpreter import String, Number, ResultValue
        
        if len(args) != 1:
            return ResultValue('Error', String("sin() expects exactly one argument."))
        
        if not hasattr(args[0], 'value'):
            return ResultValue('Error', String("sin() argument must have a value."))
        
        if not isinstance(args[0].value, (int, float)):
            return ResultValue('Error', String("sin() expects a number argument."))
        
        try:
            result = math.sin(args[0].value)
            return Number(result)
        except Exception as e:
            return ResultValue('Error', String(f"sin() failed: {str(e)}"))
    
    def _cos(self, args):
        """Calculate the cosine of an angle in radians."""
        from engage_interpreter import String, Number, ResultValue
        
        if len(args) != 1:
            return ResultValue('Error', String("cos() expects exactly one argument."))
        
        if not hasattr(args[0], 'value'):
            return ResultValue('Error', String("cos() argument must have a value."))
        
        if not isinstance(args[0].value, (int, float)):
            return ResultValue('Error', String("cos() expects a number argument."))
        
        try:
            result = math.cos(args[0].value)
            return Number(result)
        except Exception as e:
            return ResultValue('Error', String(f"cos() failed: {str(e)}"))
    
    def _tan(self, args):
        """Calculate the tangent of an angle in radians."""
        from engage_interpreter import String, Number, ResultValue
        
        if len(args) != 1:
            return ResultValue('Error', String("tan() expects exactly one argument."))
        
        if not hasattr(args[0], 'value'):
            return ResultValue('Error', String("tan() argument must have a value."))
        
        if not isinstance(args[0].value, (int, float)):
            return ResultValue('Error', String("tan() expects a number argument."))
        
        try:
            result = math.tan(args[0].value)
            return Number(result)
        except Exception as e:
            return ResultValue('Error', String(f"tan() failed: {str(e)}"))