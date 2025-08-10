# stdlib_types.py
"""
Engage Standard Library - Types Module

Provides type checking and conversion functions for the Engage programming language.
"""

from typing import Dict, Callable
from engage_stdlib import BaseModule


class TypesModule(BaseModule):
    """
    Types module providing type checking and conversion functions.
    """
    
    def get_functions(self) -> Dict[str, Callable]:
        """Return all type checking and conversion functions."""
        return {
            'type_of': self._type_of,
            'check_number': self._is_number,
            'check_string': self._is_string,
            'check_table': self._is_table,
            'check_vector': self._is_vector,
        }
    
    def _type_of(self, args):
        """Return the type name of a value."""
        from engage_interpreter import String, Number, NoneValue, Table, Vector, Record, RecordInstance, Function, BuiltInFunction, Channel, Fiber, ResultValue, BoundMethod
        
        if len(args) != 1:
            return ResultValue('Error', String("type_of() expects exactly one argument."))
        
        value = args[0]
        
        # Determine the type based on the value's class name
        class_name = value.__class__.__name__
        
        if class_name == "Number":
            return String("number")
        elif class_name == "String":
            return String("string")
        elif class_name == "Table":
            return String("table")
        elif class_name == "Vector":
            return String("vector")
        elif class_name == "Record":
            return String("record")
        elif class_name == "RecordInstance":
            return String("record_instance")
        elif class_name == "Function":
            return String("function")
        elif class_name == "BuiltInFunction":
            return String("builtin_function")
        elif class_name == "BoundMethod":
            return String("bound_method")
        elif class_name == "Channel":
            return String("channel")
        elif class_name == "Fiber":
            return String("fiber")
        elif class_name == "ResultValue":
            return String("result")
        elif class_name == "NoneValue":
            return String("none")
        else:
            return String("unknown")
    
    def _is_number(self, args):
        """Check if a value is a number."""
        from engage_interpreter import String, Number, ResultValue
        
        if len(args) != 1:
            return ResultValue('Error', String("check_number() expects exactly one argument."))
        
        value = args[0]
        result = value.__class__.__name__ == "Number"
        return Number(1 if result else 0)  # Return 1 for true, 0 for false
    
    def _is_string(self, args):
        """Check if a value is a string."""
        from engage_interpreter import String, Number, ResultValue
        
        if len(args) != 1:
            return ResultValue('Error', String("check_string() expects exactly one argument."))
        
        value = args[0]
        result = value.__class__.__name__ == "String"
        return Number(1 if result else 0)  # Return 1 for true, 0 for false
    
    def _is_table(self, args):
        """Check if a value is a table."""
        from engage_interpreter import String, Number, ResultValue
        
        if len(args) != 1:
            return ResultValue('Error', String("check_table() expects exactly one argument."))
        
        value = args[0]
        result = value.__class__.__name__ == "Table"
        return Number(1 if result else 0)  # Return 1 for true, 0 for false
    
    def _is_vector(self, args):
        """Check if a value is a vector."""
        from engage_interpreter import String, Number, ResultValue
        
        if len(args) != 1:
            return ResultValue('Error', String("check_vector() expects exactly one argument."))
        
        value = args[0]
        result = value.__class__.__name__ == "Vector"
        return Number(1 if result else 0)  # Return 1 for true, 0 for false