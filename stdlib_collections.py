# stdlib_collections.py
"""
Engage Standard Library - Collections Module

Provides data manipulation functions for the Engage programming language.
Supports operations on Tables, Vectors, and other collection types.
"""

from typing import Dict, Callable
from engage_stdlib import BaseModule


class CollectionsModule(BaseModule):
    """
    Collections module providing data manipulation functions.
    """
    
    def get_functions(self) -> Dict[str, Callable]:
        """Return all collection manipulation functions."""
        return {
            'map': self._map,
            'filter': self._filter,
            'reduce': self._reduce,
            'sort': self._sort,
        }
    
    def _map(self, args):
        """Apply a function to each element of a collection."""
        from engage_interpreter import String, Vector, Table, Function, BuiltInFunction, ResultValue, BoundMethod
        
        if len(args) != 2:
            return ResultValue('Error', String("map() expects exactly two arguments (function, collection)."))
        
        func_arg = args[0]
        collection_arg = args[1]
        
        # Validate function argument
        if not isinstance(func_arg, (Function, BuiltInFunction, BoundMethod)):
            return ResultValue('Error', String("map() first argument must be a function."))
        
        # Handle Vector collections
        if collection_arg.__class__.__name__ == 'Vector':
            try:
                # Create a new vector of the same class as the input
                result_vector = collection_arg.__class__()
                for item in collection_arg.data:
                    if item is not None:
                        # Call the function with the item
                        if isinstance(func_arg, Function):
                            # For user-defined functions, we need to call them through the interpreter
                            # For now, we'll return an error as this requires interpreter context
                            return ResultValue('Error', String("map() with user-defined functions not yet supported."))
                        elif isinstance(func_arg, (BuiltInFunction, BoundMethod)):
                            # Call built-in function
                            func_result = func_arg.func_ptr([item])
                            if isinstance(func_result, ResultValue) and func_result.type == 'Error':
                                return func_result
                            result_vector.push(func_result)
                        else:
                            result_vector.push(item)
                    else:
                        result_vector.push(item)
                return result_vector
            except Exception as e:
                return ResultValue('Error', String(f"map() failed: {str(e)}"))
        
        # Handle Table collections
        elif collection_arg.__class__.__name__ == 'Table':
            try:
                # Create a new table of the same class as the input
                result_table = collection_arg.__class__()
                for key, value in collection_arg.data.items():
                    if value is not None:
                        # Call the function with the value
                        if isinstance(func_arg, Function):
                            return ResultValue('Error', String("map() with user-defined functions not yet supported."))
                        elif isinstance(func_arg, (BuiltInFunction, BoundMethod)):
                            func_result = func_arg.func_ptr([value])
                            if isinstance(func_result, ResultValue) and func_result.type == 'Error':
                                return func_result
                            result_table.set(key, func_result)
                        else:
                            result_table.set(key, value)
                    else:
                        result_table.set(key, value)
                return result_table
            except Exception as e:
                return ResultValue('Error', String(f"map() failed: {str(e)}"))
        
        else:
            return ResultValue('Error', String("map() second argument must be a Vector or Table."))
    
    def _filter(self, args):
        """Filter elements of a collection based on a predicate function."""
        from engage_interpreter import String, Vector, Table, Function, BuiltInFunction, ResultValue, BoundMethod, Number
        
        if len(args) != 2:
            return ResultValue('Error', String("filter() expects exactly two arguments (predicate_function, collection)."))
        
        func_arg = args[0]
        collection_arg = args[1]
        
        # Validate function argument
        if not isinstance(func_arg, (Function, BuiltInFunction, BoundMethod)):
            return ResultValue('Error', String("filter() first argument must be a function."))
        
        # Handle Vector collections
        if collection_arg.__class__.__name__ == 'Vector':
            try:
                # Create a new vector of the same class as the input
                result_vector = collection_arg.__class__()
                for item in collection_arg.data:
                    if item is not None:
                        # Call the predicate function with the item
                        if isinstance(func_arg, Function):
                            return ResultValue('Error', String("filter() with user-defined functions not yet supported."))
                        elif isinstance(func_arg, (BuiltInFunction, BoundMethod)):
                            func_result = func_arg.func_ptr([item])
                            if isinstance(func_result, ResultValue) and func_result.type == 'Error':
                                return func_result
                            # Check if result is truthy
                            if self._is_truthy(func_result):
                                result_vector.push(item)
                return result_vector
            except Exception as e:
                return ResultValue('Error', String(f"filter() failed: {str(e)}"))
        
        # Handle Table collections
        elif collection_arg.__class__.__name__ == 'Table':
            try:
                # Create a new table of the same class as the input
                result_table = collection_arg.__class__()
                for key, value in collection_arg.data.items():
                    if value is not None:
                        # Call the predicate function with the value
                        if isinstance(func_arg, Function):
                            return ResultValue('Error', String("filter() with user-defined functions not yet supported."))
                        elif isinstance(func_arg, (BuiltInFunction, BoundMethod)):
                            func_result = func_arg.func_ptr([value])
                            if isinstance(func_result, ResultValue) and func_result.type == 'Error':
                                return func_result
                            # Check if result is truthy
                            if self._is_truthy(func_result):
                                result_table.set(key, value)
                return result_table
            except Exception as e:
                return ResultValue('Error', String(f"filter() failed: {str(e)}"))
        
        else:
            return ResultValue('Error', String("filter() second argument must be a Vector or Table."))
    
    def _reduce(self, args):
        """Reduce a collection to a single value using an accumulator function."""
        from engage_interpreter import String, Vector, Table, Function, BuiltInFunction, ResultValue, BoundMethod
        
        if len(args) < 2 or len(args) > 3:
            return ResultValue('Error', String("reduce() expects 2 or 3 arguments (function, collection, [initial_value])."))
        
        func_arg = args[0]
        collection_arg = args[1]
        initial_value = args[2] if len(args) == 3 else None
        
        # Validate function argument
        if not isinstance(func_arg, (Function, BuiltInFunction, BoundMethod)):
            return ResultValue('Error', String("reduce() first argument must be a function."))
        
        # Handle Vector collections
        if collection_arg.__class__.__name__ == 'Vector':
            try:
                if len(collection_arg.data) == 0:
                    if initial_value is not None:
                        return initial_value
                    else:
                        return ResultValue('Error', String("reduce() of empty Vector without initial value."))
                
                # Start with initial value or first element
                if initial_value is not None:
                    accumulator = initial_value
                    start_index = 0
                else:
                    accumulator = collection_arg.data[0]
                    start_index = 1
                
                # Apply function to each remaining element
                for i in range(start_index, len(collection_arg.data)):
                    item = collection_arg.data[i]
                    if item is not None:
                        if isinstance(func_arg, Function):
                            return ResultValue('Error', String("reduce() with user-defined functions not yet supported."))
                        elif isinstance(func_arg, (BuiltInFunction, BoundMethod)):
                            func_result = func_arg.func_ptr([accumulator, item])
                            if isinstance(func_result, ResultValue) and func_result.type == 'Error':
                                return func_result
                            accumulator = func_result
                
                return accumulator
            except Exception as e:
                return ResultValue('Error', String(f"reduce() failed: {str(e)}"))
        
        # Handle Table collections (reduce over values)
        elif collection_arg.__class__.__name__ == 'Table':
            try:
                values = list(collection_arg.data.values())
                if len(values) == 0:
                    if initial_value is not None:
                        return initial_value
                    else:
                        return ResultValue('Error', String("reduce() of empty Table without initial value."))
                
                # Start with initial value or first value
                if initial_value is not None:
                    accumulator = initial_value
                    start_index = 0
                else:
                    accumulator = values[0]
                    start_index = 1
                
                # Apply function to each remaining value
                for i in range(start_index, len(values)):
                    value = values[i]
                    if value is not None:
                        if isinstance(func_arg, Function):
                            return ResultValue('Error', String("reduce() with user-defined functions not yet supported."))
                        elif isinstance(func_arg, (BuiltInFunction, BoundMethod)):
                            func_result = func_arg.func_ptr([accumulator, value])
                            if isinstance(func_result, ResultValue) and func_result.type == 'Error':
                                return func_result
                            accumulator = func_result
                
                return accumulator
            except Exception as e:
                return ResultValue('Error', String(f"reduce() failed: {str(e)}"))
        
        else:
            return ResultValue('Error', String("reduce() second argument must be a Vector or Table."))
    
    def _sort(self, args):
        """Sort elements of a collection."""
        from engage_interpreter import String, Vector, Table, Function, BuiltInFunction, ResultValue, BoundMethod, Number
        
        if len(args) < 1 or len(args) > 2:
            return ResultValue('Error', String("sort() expects 1 or 2 arguments (collection, [compare_function])."))
        
        collection_arg = args[0]
        compare_func = args[1] if len(args) == 2 else None
        
        # Validate compare function if provided
        if compare_func is not None and not isinstance(compare_func, (Function, BuiltInFunction, BoundMethod)):
            return ResultValue('Error', String("sort() second argument must be a function."))
        
        # Handle Vector collections
        if collection_arg.__class__.__name__ == 'Vector':
            try:
                # Create a new vector of the same class as the input
                result_vector = collection_arg.__class__()
                # Copy all non-None elements
                items_to_sort = [item for item in collection_arg.data if item is not None]
                
                if compare_func is None:
                    # Default sort - try to sort by value
                    try:
                        # Sort numbers and strings separately
                        numbers = []
                        strings = []
                        others = []
                        
                        for item in items_to_sort:
                            if hasattr(item, 'value'):
                                if isinstance(item.value, (int, float)):
                                    numbers.append(item)
                                elif isinstance(item.value, str):
                                    strings.append(item)
                                else:
                                    others.append(item)
                            else:
                                others.append(item)
                        
                        # Sort each category
                        numbers.sort(key=lambda x: x.value)
                        strings.sort(key=lambda x: x.value)
                        
                        # Combine sorted results
                        sorted_items = numbers + strings + others
                        
                        for item in sorted_items:
                            result_vector.push(item)
                        
                    except Exception:
                        # If default sort fails, return original order
                        for item in items_to_sort:
                            result_vector.push(item)
                else:
                    # Custom sort with compare function
                    return ResultValue('Error', String("sort() with custom compare function not yet supported."))
                
                return result_vector
            except Exception as e:
                return ResultValue('Error', String(f"sort() failed: {str(e)}"))
        
        # Handle Table collections (sort by values, return new table with same keys)
        elif collection_arg.__class__.__name__ == 'Table':
            try:
                # Create a new table of the same class as the input
                result_table = collection_arg.__class__()
                
                # Get key-value pairs and sort by values
                items = [(key, value) for key, value in collection_arg.data.items() if value is not None]
                
                if compare_func is None:
                    # Default sort by values
                    try:
                        # Sort by value
                        items.sort(key=lambda x: x[1].value if hasattr(x[1], 'value') else str(x[1]))
                    except Exception:
                        # If sort fails, keep original order
                        pass
                else:
                    # Custom sort with compare function
                    return ResultValue('Error', String("sort() with custom compare function not yet supported."))
                
                # Rebuild table with sorted values
                for key, value in items:
                    result_table.set(key, value)
                
                return result_table
            except Exception as e:
                return ResultValue('Error', String(f"sort() failed: {str(e)}"))
        
        else:
            return ResultValue('Error', String("sort() first argument must be a Vector or Table."))
    
    def _is_truthy(self, value):
        """Helper function to determine if a value is truthy."""
        from engage_interpreter import Number, String
        
        if value.__class__.__name__ == 'Number':
            return value.value != 0
        elif value.__class__.__name__ == 'String':
            return len(value.value) > 0
        elif value.__class__.__name__ in ['Vector', 'Table']:
            return value.is_true()
        else:
            return bool(value)