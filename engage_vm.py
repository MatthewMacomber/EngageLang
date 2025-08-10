# engage_vm.py
import sys
import pickle
import os
import threading
import queue

from engage_lexer import Lexer
from engage_parser import Parser, ASTNode, ProgramNode, VarAssignNode, SetNode, VarAccessNode, BinOpNode, NumberNode, StringNode, FuncDefNode, FuncCallNode, ReturnNode, IfNode, UnaryOpNode, WhileNode, TaskNode, ChannelNode, SendNode, ReceiveNode, FiberDefNode, YieldNode, RecordDefNode, NewInstanceNode, MemberAccessNode, SelfNode, TypeNameNode

IMAGE_FILENAME = "engage.image"

# --- Runtime Value Classes ---

class Value:
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
    def __getstate__(self):
        state = self.__dict__.copy(); del state['queue']; return state
    def __setstate__(self, state):
        self.__dict__.update(state); self.queue = queue.Queue()

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
    def __init__(self, name, methods, default_props):
        super().__init__()
        self.name = name
        self.methods = methods
        self.default_props = default_props
    def __repr__(self):
        return f"<record {self.name}>"

class RecordInstance(Value):
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
    def __init__(self, instance, method):
        super().__init__()
        self.instance = instance
        self.method = method
    def __repr__(self):
        return f"<bound method {self.method.name} of {self.instance}>"

class ResultValue(Value):
    def __init__(self, type, value):
        super().__init__()
        self.type = type # 'Ok' or 'Error'
        self.value = value
    
    def is_true(self):
        return self.type == 'Ok'
    
    def __repr__(self):
        return f"{self.type}({repr(self.value)})"

# --- Symbol Table / Context ---

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

# --- Interpreter ---

class Interpreter:
    def visit(self, node, context):
        method_name = f'visit_{type(node).__name__}'
        method = getattr(self, method_name, self.no_visit_method)
        return method(node, context)

    def no_visit_method(self, node, context):
        raise Exception(f'No visit_{type(node).__name__} method defined')
    
    def visit_ProgramNode(self, node, context):
        result = None
        for statement in node.statements:
            result = self.visit(statement, context)
            if isinstance(result, (ReturnValue, YieldValue)):
                return result.value
        return result

    def visit_VarAssignNode(self, node, context):
        var_name = node.name_token.value
        value = self.visit(node.value_node, context)
        context.set(var_name, value)
        return value

    def visit_SetNode(self, node, context):
        target_node = node.target_node
        value_to_set = self.visit(node.value_node, context)

        if isinstance(target_node, VarAccessNode):
            var_name = target_node.name_token.value
            if context.get(var_name) is None:
                if context.parent is None:
                    context.set(var_name, value_to_set)
                else:
                    raise NameError(f"Cannot 'set' variable '{var_name}' before it is declared with 'let'.")
            else:
                 context.set(var_name, value_to_set)
        elif isinstance(target_node, MemberAccessNode):
            instance = self.visit(target_node.instance_node, context)
            if not isinstance(instance, RecordInstance):
                raise TypeError("Can only set members of a record instance")
            member_name = target_node.member_token.value
            instance.context.set(member_name, value_to_set)
        else:
            raise TypeError("Invalid target for 'set' statement.")
        return value_to_set

    def visit_VarAccessNode(self, node, context):
        var_name = node.name_token.value
        value = context.get(var_name)
        if value is None: raise NameError(f"'{var_name}' is not defined")
        return value

    def visit_BinOpNode(self, node, context):
        op = node.op_token.value
        
        # Handle 'or return error' specially - don't evaluate right side
        if op == 'or return error':
            left = self.visit(node.left_node, context)
            if isinstance(left, ResultValue) and left.type == 'Error':
                raise ReturnException(left)
            return left
        
        # Handle 'is an' specially - don't evaluate right side as it's a type name
        if op == 'is an':
            left = self.visit(node.left_node, context)
            
            # Handle TypeNameNode (new approach)
            if isinstance(node.right_node, TypeNameNode):
                type_name = node.right_node.type_token.value
                if type_name == 'Error':
                    return Number(1) if isinstance(left, ResultValue) and left.type == 'Error' else Number(0)
                elif type_name == 'Ok':
                    return Number(1) if isinstance(left, ResultValue) and left.type == 'Ok' else Number(0)
            
            # Handle VarAccessNode (backward compatibility)
            elif isinstance(node.right_node, VarAccessNode):
                type_name = node.right_node.name_token.value
                if type_name == 'Error':
                    return Number(1) if isinstance(left, ResultValue) and left.type == 'Error' else Number(0)
                elif type_name == 'Ok':
                    return Number(1) if isinstance(left, ResultValue) and left.type == 'Ok' else Number(0)
            
            return Number(0)  # Default case: not an instance of the specified type

        # For all other operations, evaluate both sides
        left = self.visit(node.left_node, context); right = self.visit(node.right_node, context)
        if op in ('plus', '+', 'concatenated with'):
            if isinstance(left, String) or isinstance(right, String): return String(str(left.value) + str(right.value))
            return Number(left.value + right.value)
        elif op in ('minus', '-'): return Number(left.value - right.value)
        elif op in ('times', '*'): return Number(left.value * right.value)
        elif op in ('divided by', '/'):
            if right.value == 0: raise ZeroDivisionError("Division by zero")
            return Number(left.value / right.value)
        elif op in ('is greater than', '>'): return Number(1) if left.value > right.value else Number(0)
        elif op in ('is less than', '<'): return Number(1) if left.value < right.value else Number(0)
        elif op in ('is', '=='): return Number(1) if left.value == right.value else Number(0)
        elif op in ('is not', '!='): return Number(1) if left.value != right.value else Number(0)
        elif op == 'and': return Number(1) if left.is_true() and right.is_true() else Number(0)
        elif op == 'or': return Number(1) if left.is_true() or right.is_true() else Number(0)
        raise TypeError(f"Unsupported operand types for {op}")

    def visit_UnaryOpNode(self, node, context):
        op = node.op_token.value
        if op == 'call':
            fiber = self.visit(node.node, context)
            if not isinstance(fiber, Fiber): raise TypeError(f"Can only 'call' a fiber, not {type(fiber).__name__}")
            return self.execute_fiber(fiber, context)
        
        value = self.visit(node.node, context)
        if op == 'not': return Number(0) if value.is_true() else Number(1)
        if op == 'the ok value of':
            if not isinstance(value, ResultValue) or value.type != 'Ok':
                raise TypeError("Attempted to get the 'ok value' of a non-Ok result.")
            return value.value
        if op == 'the error message of':
            if not isinstance(value, ResultValue) or value.type != 'Error':
                raise TypeError("Attempted to get the 'error message' of a non-Error result.")
            return value.value

        raise TypeError(f"Unsupported unary operator: {op}")

    def visit_NumberNode(self, node, context): return Number(node.value).set_context(context)
    def visit_StringNode(self, node, context): return String(node.value).set_context(context)
    def visit_FuncDefNode(self, node, context):
        func_name = node.name_token.value
        func_value = Function(func_name, node.body_nodes, [p.value for p in node.param_tokens])
        context.set(func_name, func_value)
        return func_value

    def visit_FuncCallNode(self, node, context):
        args = [self.visit(arg_node, context) for arg_node in node.arg_nodes]
        callee = self.visit(node.node_to_call, context)
        if isinstance(callee, BoundMethod):
            return self.execute_user_function(callee.method, args, context, callee.instance)
        elif isinstance(callee, BuiltInFunction): return callee.func_ptr(args)
        elif isinstance(callee, Function): return self.execute_user_function(callee, args, context)
        else: raise TypeError(f"'{callee}' is not a function")

    def execute_user_function(self, func, args, context, instance=None):
        if len(args) != len(func.arg_names): raise TypeError(f"Function '{func.name}' takes {len(func.arg_names)} arguments but {len(args)} were given")
        func_context = SymbolTable(parent=context)
        if instance:
            func_context.set("self", instance)
        for i, arg_name in enumerate(func.arg_names): func_context.set(arg_name, args[i])
        result = None
        try:
            for statement in func.body_node:
                result = self.visit(statement, func_context)
                if isinstance(result, ReturnValue): return result.value
        except ReturnException as e:
            # Handle early return from error propagation
            return e.value
        return result if result else Number(0)

    def visit_IfNode(self, node, context):
        for condition_node, statements in node.cases:
            if self.visit(condition_node, context).is_true():
                result = None
                for statement in statements:
                    result = self.visit(statement, context)
                    if isinstance(result, (ReturnValue, YieldValue)): return result
                return result if result else Number(0)
        if node.else_case:
            result = None
            for statement in node.else_case:
                result = self.visit(statement, context)
                if isinstance(result, (ReturnValue, YieldValue)): return result
            return result if result else Number(0)
        return Number(0)

    def visit_WhileNode(self, node, context):
        result = Number(0)
        while self.visit(node.condition_node, context).is_true():
            for statement in node.body_nodes:
                result = self.visit(statement, context)
                if isinstance(result, (ReturnValue, YieldValue)): return result
        return result

    def visit_ReturnNode(self, node, context): return ReturnValue(self.visit(node.node_to_return, context) if node.node_to_return else Number(0))
    def visit_TaskNode(self, node, context):
        def task_target():
            task_interpreter = Interpreter(); task_context = SymbolTable(parent=context)
            for statement in node.body_nodes: task_interpreter.visit(statement, task_context)
        thread = threading.Thread(target=task_target); thread.daemon = True; thread.start()
        return Number(0)

    def visit_ChannelNode(self, node, context):
        channel_name = node.name_token.value; channel = Channel(channel_name); context.set(channel_name, channel)
        return channel

    def visit_SendNode(self, node, context):
        channel = self.visit(node.channel_node, context)
        if not isinstance(channel, Channel): raise TypeError("Can only send to a channel")
        value = self.visit(node.value_node, context); channel.queue.put(value)
        return value

    def visit_ReceiveNode(self, node, context):
        channel = self.visit(node.channel_node, context)
        if not isinstance(channel, Channel): raise TypeError("Can only receive from a channel")
        return channel.queue.get()

    def visit_FiberDefNode(self, node, context):
        fiber_name = node.name_token.value; fiber = Fiber(fiber_name, node.body_nodes); context.set(fiber_name, fiber)
        return fiber

    def execute_fiber(self, fiber, context):
        if fiber.is_done: return Number(0)
        if fiber.context is None: fiber.context = SymbolTable(parent=context)
        while fiber.ip < len(fiber.body_node):
            statement = fiber.body_node[fiber.ip]
            result = self.visit(statement, fiber.context)
            if isinstance(result, YieldValue):
                fiber.ip += 1; return result.value
            if isinstance(result, ReturnValue):
                fiber.is_done = True; return result.value
            fiber.ip += 1
        fiber.is_done = True
        return Number(0)

    def visit_YieldNode(self, node, context): return YieldValue(self.visit(node.value_node, context) if node.value_node else Number(0))
    
    def visit_RecordDefNode(self, node, context):
        record_name = node.name_token.value
        methods = {}
        default_props = {}
        temp_context = SymbolTable(parent=context)
        for member in node.members:
            if isinstance(member, FuncDefNode):
                method_name = member.name_token.value
                methods[method_name] = Function(method_name, member.body_nodes, [p.value for p in member.param_tokens])
            elif isinstance(member, VarAssignNode):
                prop_name = member.name_token.value
                default_props[prop_name] = self.visit(member.value_node, temp_context)

        record_class = Record(record_name, methods, default_props)
        context.set(record_name, record_class)
        return record_class

    def visit_NewInstanceNode(self, node, context):
        class_name = node.name_token.value
        record_class = context.get(class_name)
        if not isinstance(record_class, Record): raise TypeError(f"'{class_name}' is not a record type.")
        
        instance_context = SymbolTable(parent=context)
        for name, value in record_class.default_props.items():
            instance_context.set(name, value)
        
        instance = RecordInstance(record_class, instance_context)
        
        for prop_name, prop_value_node in node.properties.items():
            value = self.visit(prop_value_node, context)
            instance.context.set(prop_name, value)
            
        return instance

    def visit_MemberAccessNode(self, node, context):
        instance = self.visit(node.instance_node, context)
        member_name = node.member_token.value
        
        if isinstance(instance, RecordInstance):
            prop = instance.context.get(member_name)
            if prop: return prop
            
            method = instance.record_class.methods.get(member_name)
            if method: return BoundMethod(instance, method)
            
            raise AttributeError(f"Record '{instance.record_class.name}' has no member '{member_name}'")
        
        raise TypeError(f"Cannot access members of type {type(instance).__name__}")

    def visit_SelfNode(self, node, context):
        self_value = context.get("self")
        if self_value is None: raise NameError("'self' can only be used inside a method.")
        return self_value
    
    def visit_ResultNode(self, node, context):
        result_type = node.type_token.value  # 'Ok' or 'Error'
        if node.value_node:
            value = self.visit(node.value_node, context)
        else:
            value = None
        return ResultValue(result_type, value)

    def visit_TypeNameNode(self, node, context):
        # TypeNameNode represents a type name like 'Error' or 'Ok'
        # We don't need to evaluate it as a variable, just return the type name
        return node.type_token.value

class ReturnValue:
    def __init__(self, value): self.value = value
class YieldValue:
    def __init__(self, value): self.value = value

class ReturnException(Exception):
    """Exception used to handle early returns from error propagation."""
    def __init__(self, value):
        self.value = value
        super().__init__()

# --- Built-in Functions ---
def builtin_print(args):
    for arg in args: print(arg.value)
    return Number(0)
def builtin_input(args): return String(input(args[0].value if args else ""))
def builtin_number(args):
    if not args: 
        return ResultValue('Error', String("number() expects one argument."))
    try:
        return ResultValue('Ok', Number(float(args[0].value)))
    except (ValueError, TypeError):
        return ResultValue('Error', String(f"Cannot convert '{args[0].value}' to number"))

# --- Image Management ---
def bootstrap_image():
    print("Bootstrapping new image...")
    st = SymbolTable()
    st.set("print", BuiltInFunction("print", builtin_print))
    st.set("input", BuiltInFunction("input", builtin_input))
    st.set("number", BuiltInFunction("number", builtin_number))
    st.set("Error", String("Error"))
    return st
def save_image(symbol_table):
    with open(IMAGE_FILENAME, 'wb') as f: pickle.dump(symbol_table, f)
    print(f"Environment saved to {IMAGE_FILENAME}")
def load_image():
    if not os.path.exists(IMAGE_FILENAME): return bootstrap_image()
    try:
        with open(IMAGE_FILENAME, 'rb') as f: symbol_table = pickle.load(f)
        print(f"Environment loaded from {IMAGE_FILENAME}"); return symbol_table
    except Exception as e:
        print(f"Warning: Could not load image file ({e}). Starting fresh."); return bootstrap_image()

# --- Main Execution Block (REPL) ---
def run(code_string, context):
    try:
        lexer = Lexer(code_string); tokens = lexer.tokenize()
        parser = Parser(tokens); ast = parser.parse()
        interpreter = Interpreter(); result = interpreter.visit(ast, context)
        return result
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        # import traceback
        # traceback.print_exc() # Uncomment for full debug trace
        return None

if __name__ == '__main__':
    global_symbol_table = load_image()
    print("\nWelcome to the Engage Live Environment (VM).")
    print("Type Engage code. To submit a multi-line block, enter a blank line.")
    print("Type '_run <filepath>' to execute a file.")
    print("Type '_save' to snapshot, or '_quit' to save and exit.")
    
    buffer = []
    
    while True:
        try:
            prompt = "engage> " if not buffer else "...     "
            line = input(prompt)

            if not buffer:
                if line.strip() == '_quit': save_image(global_symbol_table); break
                if line.strip() == '_save': save_image(global_symbol_table); continue
                if line.strip().startswith('_run '):
                    filepath = line.strip().split(' ', 1)[1]
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            file_code = f.read()
                        print(f"--- Running file: {filepath} ---")
                        run(file_code, global_symbol_table)
                        print(f"--- Finished file: {filepath} ---")
                    except FileNotFoundError:
                        print(f"Error: File not found at '{filepath}'", file=sys.stderr)
                    continue

            if not line.strip() and buffer:
                full_code = "\n".join(buffer)
                buffer = []
                result = run(full_code, global_symbol_table)
                if result is not None:
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
