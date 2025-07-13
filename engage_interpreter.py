# This code assumes the Lexer and Parser from the previous artifacts are in files
# named 'engage_lexer.py' and 'engage_parser.py'.
import sys
import threading
import queue
from engage_lexer import Lexer
from engage_parser import Parser, ASTNode, ProgramNode, VarAssignNode, VarAccessNode, BinOpNode, NumberNode, StringNode, FuncDefNode, FuncCallNode, ReturnNode, IfNode, UnaryOpNode, WhileNode, TaskNode, ChannelNode, SendNode, ReceiveNode

# --- Runtime Value Classes ---

class Value:
    """Base class for all runtime values."""
    def __init__(self):
        self.set_pos()
        self.set_context()
    def set_pos(self, pos_start=None, pos_end=None):
        self.pos_start = pos_start
        self.pos_end = pos_end
        return self
    def set_context(self, context=None):
        self.context = context
        return self
    def is_true(self):
        return False

class Number(Value):
    """Represents a number value in our language."""
    def __init__(self, value):
        super().__init__()
        self.value = value
    def __repr__(self):
        return str(self.value)
    def is_true(self):
        return self.value != 0

class String(Value):
    """Represents a string value in our language."""
    def __init__(self, value):
        super().__init__()
        self.value = value
    def __repr__(self):
        return f'"{self.value}"'
    def is_true(self):
        return len(self.value) > 0

class Function(Value):
    """Represents a function defined in Engage."""
    def __init__(self, name, body_node, arg_names):
        super().__init__()
        self.name = name or "<anonymous>"
        self.body_node = body_node
        self.arg_names = arg_names
    def __repr__(self):
        return f"<function {self.name}>"

class BuiltInFunction(Value):
    """Represents a function provided by the interpreter (e.g., print)."""
    def __init__(self, name):
        super().__init__()
        self.name = name
    def __repr__(self):
        return f"<built-in function {self.name}>"

class Channel(Value):
    """Represents a message queue for concurrent tasks."""
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.queue = queue.Queue()
    def __repr__(self):
        return f"<channel {self.name}>"

# --- Symbol Table / Context ---

class SymbolTable:
    """A table to store variables and their values."""
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
    def remove(self, name):
        del self.symbols[name]

# --- Interpreter ---

class Interpreter:
    """Walks the AST and executes the code."""
    def visit(self, node, context):
        """Dispatcher method to call the correct visit method for a node."""
        method_name = f'visit_{type(node).__name__}'
        method = getattr(self, method_name, self.no_visit_method)
        return method(node, context)

    def no_visit_method(self, node, context):
        raise Exception(f'No visit_{type(node).__name__} method defined')

    def visit_ProgramNode(self, node, context):
        """Visit the root of the program."""
        result = None
        for statement in node.statements:
            result = self.visit(statement, context)
            if isinstance(result, ReturnValue):
                return result.value
        return result

    def visit_VarAssignNode(self, node, context):
        var_name = node.name_token.value
        value = self.visit(node.value_node, context)
        context.set(var_name, value)
        return value

    def visit_VarAccessNode(self, node, context):
        var_name = node.name_token.value
        value = context.get(var_name)
        if value is None:
            raise NameError(f"'{var_name}' is not defined")
        return value

    def visit_BinOpNode(self, node, context):
        left = self.visit(node.left_node, context)
        right = self.visit(node.right_node, context)
        op = node.op_token.value
        if op in ('plus', '+', 'concatenated with'):
            if isinstance(left, String) or isinstance(right, String):
                return String(str(left.value) + str(right.value))
            return Number(left.value + right.value)
        elif op in ('minus', '-'):
            return Number(left.value - right.value)
        elif op in ('times', '*'):
            return Number(left.value * right.value)
        elif op in ('divided by', '/'):
            if right.value == 0:
                raise ZeroDivisionError("Division by zero")
            return Number(left.value / right.value)
        elif op in ('is greater than', '>'):
            return Number(1) if left.value > right.value else Number(0)
        elif op in ('is less than', '<'):
            return Number(1) if left.value < right.value else Number(0)
        elif op in ('is', '=='):
            return Number(1) if left.value == right.value else Number(0)
        elif op in ('is not', '!='):
            return Number(1) if left.value != right.value else Number(0)
        elif op == 'and':
            return Number(1) if left.is_true() and right.is_true() else Number(0)
        elif op == 'or':
            return Number(1) if left.is_true() or right.is_true() else Number(0)
        raise TypeError(f"Unsupported operand types for {op}")

    def visit_UnaryOpNode(self, node, context):
        op = node.op_token.value
        number = self.visit(node.node, context)
        if op == 'not':
            return Number(0) if number.is_true() else Number(1)
        raise TypeError(f"Unsupported unary operator: {op}")

    def visit_NumberNode(self, node, context):
        return Number(node.value).set_context(context)

    def visit_StringNode(self, node, context):
        return String(node.value).set_context(context)

    def visit_FuncDefNode(self, node, context):
        func_name = node.name_token.value
        body_node = node.body_nodes
        arg_names = [p.value for p in node.param_tokens]
        func_value = Function(func_name, body_node, arg_names)
        context.set(func_name, func_value)
        return func_value

    def visit_FuncCallNode(self, node, context):
        args = []
        for arg_node in node.arg_nodes:
            args.append(self.visit(arg_node, context))
        func_to_call = self.visit(node.node_to_call, context)
        if isinstance(func_to_call, BuiltInFunction):
            return self.execute_builtin_function(func_to_call, args, context)
        elif isinstance(func_to_call, Function):
            return self.execute_user_function(func_to_call, args, context)
        else:
            raise TypeError(f"'{func_to_call}' is not a function")
    
    def execute_builtin_function(self, func, args, context):
        if func.name == 'print':
            for arg in args:
                print(arg.value)
            return Number(0)
        elif func.name == 'input':
            text = input(args[0].value if args else "")
            return String(text)
        elif func.name == 'number':
            if not args: raise ValueError("number() expects one argument.")
            return Number(float(args[0].value))
        return Number(0)

    def execute_user_function(self, func, args, context):
        if len(args) != len(func.arg_names):
            raise TypeError(f"Function '{func.name}' takes {len(func.arg_names)} arguments but {len(args)} were given")
        func_context = SymbolTable(parent=context)
        for i, arg_name in enumerate(func.arg_names):
            func_context.set(arg_name, args[i])
        result = None
        for statement in func.body_node:
            result = self.visit(statement, func_context)
            if isinstance(result, ReturnValue):
                return result.value
        return result if result else Number(0)

    def visit_IfNode(self, node, context):
        for condition_node, statements in node.cases:
            condition_value = self.visit(condition_node, context)
            if condition_value.is_true():
                result = None
                for statement in statements:
                    result = self.visit(statement, context)
                    if isinstance(result, ReturnValue):
                        return result
                return result if result else Number(0)
        if node.else_case:
            result = None
            for statement in node.else_case:
                result = self.visit(statement, context)
                if isinstance(result, ReturnValue):
                    return result
            return result if result else Number(0)
        return Number(0)

    def visit_WhileNode(self, node, context):
        result = Number(0)
        while True:
            condition = self.visit(node.condition_node, context)
            if not condition.is_true():
                break
            for statement in node.body_nodes:
                result = self.visit(statement, context)
                if isinstance(result, ReturnValue):
                    return result
        return result

    def visit_ReturnNode(self, node, context):
        value = self.visit(node.node_to_return, context) if node.node_to_return else Number(0)
        return ReturnValue(value)

    # --- START REFACTORED LOGIC ---
    def visit_TaskNode(self, node, context):
        def task_target():
            task_interpreter = Interpreter()
            task_context = SymbolTable(parent=context)
            for statement in node.body_nodes:
                task_interpreter.visit(statement, task_context)

        thread = threading.Thread(target=task_target)
        thread.start()
        # In a real engine, we'd manage these threads.
        return Number(0)

    def visit_ChannelNode(self, node, context):
        channel_name = node.name_token.value
        channel = Channel(channel_name)
        context.set(channel_name, channel)
        return channel

    def visit_SendNode(self, node, context):
        channel = self.visit(node.channel_node, context)
        if not isinstance(channel, Channel):
            raise TypeError("Can only send to a channel")
        value = self.visit(node.value_node, context)
        channel.queue.put(value)
        return value

    def visit_ReceiveNode(self, node, context):
        channel = self.visit(node.channel_node, context)
        if not isinstance(channel, Channel):
            raise TypeError("Can only receive from a channel")
        value = channel.queue.get()
        return value
    # --- END REFACTORED LOGIC ---

# A simple wrapper to signal a return from a function
class ReturnValue:
    def __init__(self, value):
        self.value = value

# --- Global Environment Setup ---
global_symbol_table = SymbolTable()
global_symbol_table.set("print", BuiltInFunction("print"))
global_symbol_table.set("input", BuiltInFunction("input"))
global_symbol_table.set("number", BuiltInFunction("number"))


# --- Main Execution Function ---
def run(code, symbol_table):
    from engage_lexer import Lexer
    from engage_parser import Parser
    lexer = Lexer(code)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    ast = parser.parse()
    if not ast:
        return None
    interpreter = Interpreter()
    result = interpreter.visit(ast, symbol_table)
    return result

# --- Main Execution Block ---
if __name__ == '__main__':
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                engage_code = f.read()
            print(f"--- Running Engage Code from file: {filepath} ---")
        except FileNotFoundError:
            print(f"Error: File not found at '{filepath}'")
            sys.exit(1)
    else:
        print("--- No file provided. Running built-in Engage example code. ---")
        engage_code = """
        to fibonacci with n:
            if n is less than 2 then
                return n.
            otherwise
                let a be fibonacci with n minus 1.
                let b be fibonacci with n minus 2.
                return a plus b.
            end
        end
        print with "Calculating the 10th Fibonacci number...".
        let result be fibonacci with 10.
        print with result.
        """

    print(f"\nCODE:\n{engage_code}\n")
    print("--- OUTPUT ---")
    
    try:
        run(engage_code, global_symbol_table)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\nAn error occurred: {e}")
