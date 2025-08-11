# engage_values.py
# This file contains the core runtime value classes for the Engage language.
# It is designed to be imported by the interpreter, standard library, and other
# components without creating circular dependencies.

import queue

class Value:
    """Base class for all runtime values."""
    def __init__(self):
        self.set_context()
    def set_context(self, context=None):
        self.context = context
        return self
    def is_true(self):
        return False

class Number(Value):
    def __init__(self, value):
        super().__init__()
        self.value = value
    def __repr__(self):
        return str(self.value)
    def is_true(self):
        return self.value != 0

class String(Value):
    def __init__(self, value):
        super().__init__()
        self.value = value
    def __repr__(self):
        return f'"{self.value}"'
    def is_true(self):
        return len(self.value) > 0

class NoneValue(Value):
    def __init__(self):
        super().__init__()
        self.value = None
    def __repr__(self):
        return "None"
    def is_true(self):
        return False

class Function(Value):
    def __init__(self, name, body_node, arg_names):
        super().__init__()
        self.name = name or "<anonymous>"
        self.body_node = body_node
        self.arg_names = arg_names
    def __repr__(self):
        return f"<function {self.name}>"

class BuiltInFunction(Value):
    def __init__(self, name, func_ptr):
        super().__init__()
        self.name = name
        self.func_ptr = func_ptr
    def __repr__(self):
        return f"<built-in function {self.name}>"

class Channel(Value):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.queue = queue.Queue()
    def __repr__(self):
        return f"<channel {self.name}>"

class Fiber(Value):
    def __init__(self, name, body_node):
        super().__init__()
        self.name = name or "<anonymous_fiber>"
        self.body_node = body_node
        self.context = None
        self.ip = 0
        self.is_done = False
    def __repr__(self):
        status = "done" if self.is_done else "ready"
        return f"<fiber {self.name} ({status})>"

class Record(Value):
    """Represents the definition of a record (its class)."""
    def __init__(self, name, methods, default_props):
        super().__init__()
        self.name = name
        self.methods = methods
        self.default_props = default_props
    def __repr__(self):
        return f"<record {self.name}>"

class RecordInstance(Value):
    """Represents an instance of a record."""
    def __init__(self, record_class, context):
        super().__init__()
        self.record_class = record_class
        self.context = context
    def __repr__(self):
        props = []
        for key, val in self.context.symbols.items():
            if key != 'self':
                props.append(f"{key}: {repr(val)}")
        return f"<instance of {self.record_class.name} with {', '.join(props)}>"

class BoundMethod(Value):
    """Represents a method bound to a specific instance."""
    def __init__(self, instance, method):
        super().__init__()
        self.instance = instance
        self.method = method
    def __repr__(self):
        return f"<bound method {self.method.name} of {self.instance}>"

class ResultValue(Value):
    """Represents a Result type (Ok or Error)."""
    def __init__(self, type, value):
        super().__init__()
        self.type = type  # 'Ok' or 'Error'
        self.value = value

    def is_true(self):
        return self.type == 'Ok'

    def __repr__(self):
        return f"{self.type}({self.value})"

class Table(Value):
    """Represents a Table (hash map) data structure."""
    def __init__(self):
        super().__init__()
        self.data = {}

    def __repr__(self):
        return f"<Table with {len(self.data)} items>"

    def is_true(self):
        return len(self.data) > 0

    def get(self, key):
        """Get value by key, returns None if key doesn't exist."""
        if not isinstance(key, str):
            raise TypeError("Table keys must be strings")
        return self.data.get(key, None)

    def set(self, key, value):
        """Set value by key."""
        if not isinstance(key, str):
            raise TypeError("Table keys must be strings")
        self.data[key] = value

    def has_key(self, key):
        """Check if key exists in table."""
        if not isinstance(key, str):
            raise TypeError("Table keys must be strings")
        return key in self.data

    def keys(self):
        """Return list of all keys."""
        return list(self.data.keys())

    def values(self):
        """Return list of all values."""
        return list(self.data.values())

    def size(self):
        """Return number of items in table."""
        return len(self.data)

class Vector(Value):
    """Represents a Vector (dynamic array) data structure."""
    def __init__(self):
        super().__init__()
        self.data = []

    def __repr__(self):
        return f"<Vector with {len(self.data)} items>"

    def is_true(self):
        return len(self.data) > 0

    def get(self, index):
        """Get value by index, returns None if index is out of bounds."""
        if not isinstance(index, int):
            raise TypeError("Vector indices must be integers")
        if 0 <= index < len(self.data):
            return self.data[index]
        return None

    def set(self, index, value):
        """Set value by index."""
        if not isinstance(index, int):
            raise TypeError("Vector indices must be integers")
        if index < 0:
            raise IndexError("Vector index cannot be negative")
        # Extend the vector if necessary
        while len(self.data) <= index:
            self.data.append(None)
        self.data[index] = value

    def push(self, value):
        """Add value to the end of the vector."""
        self.data.append(value)
        return len(self.data)

    def pop(self):
        """Remove and return the last value from the vector."""
        if len(self.data) == 0:
            return None
        return self.data.pop()

    def length(self):
        """Return the number of items in the vector."""
        return len(self.data)

    def insert(self, index, value):
        """Insert value at the specified index."""
        if not isinstance(index, int):
            raise TypeError("Vector indices must be integers")
        if index < 0:
            raise IndexError("Vector index cannot be negative")
        if index >= len(self.data):
            # If index is beyond current length, extend and set
            while len(self.data) <= index:
                self.data.append(None)
            self.data[index] = value
        else:
            self.data.insert(index, value)

    def remove(self, index):
        """Remove and return value at the specified index."""
        if not isinstance(index, int):
            raise TypeError("Vector indices must be integers")
        if index < 0 or index >= len(self.data):
            return None
        return self.data.pop(index)

class ModuleValue(Value):
    """Represents an imported module as a value."""
    def __init__(self, name, exports):
        super().__init__()
        self.name = name
        self.exports = exports

    def __repr__(self):
        return f"<module {self.name} with {len(self.exports)} exports>"

    def is_true(self):
        return True

    def get_attribute(self, name):
        """Get an attribute from the module."""
        return self.exports.get(name)

class SymbolTable:
    def __init__(self, parent=None):
        self.symbols = {}
        self.parent = parent
    def get(self, name):
        value = self.symbols.get(name, None)
        if value is None and self.parent:
            return self.parent.get(name)
        return value
    def set(self, name, value):
        self.symbols[name] = value
