# This code assumes the Lexer and Parser from the previous artifacts are in files
# named 'engage_lexer.py' and 'engage_parser.py'.
from engage_lexer import Lexer
from engage_parser import Parser, ASTNode, ProgramNode, VarAssignNode, VarAccessNode, BinOpNode, NumberNode, StringNode, FuncDefNode, FuncCallNode, ReturnNode, IfNode

# --- Runtime Value Classes ---
# These classes represent the actual values that our program will work with.

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

class Number(Value):
    """Represents a number value in our language."""
    def __init__(self, value):
        super().__init__()
        self.value = value
    def __repr__(self):
        return str(self.value)

class String(Value):
    """Represents a string value in our language."""
    def __init__(self, value):
        super().__init__()
        self.value = value
    def __repr__(self):
        return f'"{self.value}"'

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

# --- Symbol Table / Context ---
# Manages the scope of variables and functions.

class SymbolTable:
    """A table to store variables and their values."""
    def __init__(self, parent=None):
        self.symbols = {}
        self.parent = parent

    def get(self, name):
        """Get a value from the table or a parent table."""
        value = self.symbols.get(name, None)
        if value is None and self.parent:
            return self.parent.get(name)
        return value

    def set(self, name, value):
        """Set a value in the current table."""
        self.symbols[name] = value

    def remove(self, name):
        """Remove a value from the current table."""
        del self.symbols[name]

# --- Interpreter ---

class Interpreter:
    """
    Walks the AST and executes the code.
    The visit methods correspond to the ASTNode types.
    """
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
            # Handle return statements at the top level
            if isinstance(result, ReturnValue):
                return result.value
        return result

    def visit_VarAssignNode(self, node, context):
        """Visit a variable assignment node."""
        var_name = node.name_token.value
        value = self.visit(node.value_node, context)
        context.set(var_name, value)
        return value

    def visit_VarAccessNode(self, node, context):
        """Visit a variable access node."""
        var_name = node.name_token.value
        value = context.get(var_name)
        if value is None:
            raise NameError(f"'{var_name}' is not defined")
        return value

    def visit_BinOpNode(self, node, context):
        """Visit a binary operation node."""
        left = self.visit(node.left_node, context)
        right = self.visit(node.right_node, context)
        op = node.op_token.value

        if op in ('plus', '+'):
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
            return Number(1) if left.value > right.value else Number(0) # Using 1/0 for true/false
        # Add other operators here...
        
        raise TypeError(f"Unsupported operand types for {op}")

    def visit_NumberNode(self, node, context):
        return Number(node.value).set_context(context)

    def visit_StringNode(self, node, context):
        return String(node.value).set_context(context)

    def visit_FuncDefNode(self, node, context):
        """Visit a function definition node."""
        func_name = node.name_token.value
        body_node = node.body_nodes
        arg_names = [p.value for p in node.param_tokens]
        func_value = Function(func_name, body_node, arg_names)
        context.set(func_name, func_value)
        return func_value

    def visit_FuncCallNode(self, node, context):
        """Visit a function call node."""
        args = []
        # Evaluate all the argument nodes first
        for arg_node in node.arg_nodes:
            args.append(self.visit(arg_node, context))

        # Get the function to call
        func_to_call = self.visit(node.node_to_call, context)

        # Execute the function
        if isinstance(func_to_call, BuiltInFunction):
            return self.execute_builtin_function(func_to_call, args, context)
        elif isinstance(func_to_call, Function):
            return self.execute_user_function(func_to_call, args, context)
        else:
            raise TypeError(f"'{func_to_call}' is not a function")
    
    def execute_builtin_function(self, func, args, context):
        """Handles calling built-in functions like 'print'."""
        if func.name == 'print':
            for arg in args:
                print(arg.value)
            return Number(0) # Return a neutral value
        return Number(0)

    def execute_user_function(self, func, args, context):
        """Handles calling a user-defined function."""
        if len(args) != len(func.arg_names):
            raise TypeError(f"Function '{func.name}' takes {len(func.arg_names)} arguments but {len(args)} were given")

        # Create a new context (symbol table) for the function's scope
        func_context = SymbolTable(parent=context)
        
        # Populate the function's context with the arguments
        for i, arg_name in enumerate(func.arg_names):
            func_context.set(arg_name, args[i])

        # Execute the function body
        result = None
        for statement in func.body_node:
            result = self.visit(statement, func_context)
            # If we hit a return statement, exit the function immediately
            if isinstance(result, ReturnValue):
                return result.value
        
        # Implicit return of the last statement's value
        return result if result else Number(0)

    def visit_IfNode(self, node, context):
        """Visit an if/otherwise node."""
        # Handle 'if' and 'otherwise if' cases
        for condition_node, statements in node.cases:
            condition_value = self.visit(condition_node, context)
            if condition_value.value != 0: # Using 0 as false, non-zero as true
                result = None
                for statement in statements:
                    result = self.visit(statement, context)
                    if isinstance(result, ReturnValue):
                        return result
                return result if result else Number(0)

        # Handle 'otherwise' case
        if node.else_case:
            result = None
            for statement in node.else_case:
                result = self.visit(statement, context)
                if isinstance(result, ReturnValue):
                    return result
            return result if result else Number(0)
        
        return Number(0) # If no branch is taken

    def visit_ReturnNode(self, node, context):
        """Visit a return node."""
        value = self.visit(node.node_to_return, context) if node.node_to_return else Number(0)
        return ReturnValue(value)

# A simple wrapper to signal a return from a function
class ReturnValue:
    def __init__(self, value):
        self.value = value

# --- Global Environment Setup ---
global_symbol_table = SymbolTable()
global_symbol_table.set("print", BuiltInFunction("print")) # Add built-in print function

# --- Main Execution Function ---
def run(code, symbol_table):
    """Lex, parse, and interpret the code."""
    # Lexing
    lexer = Lexer(code)
    tokens = []
    while True:
        token = lexer.get_next_token()
        tokens.append(token)
        if token.type == 'EOF':
            break

    # Parsing
    parser = Parser(tokens)
    ast = parser.parse()
    if not ast:
        return None

    # Interpreting
    interpreter = Interpreter()
    result = interpreter.visit(ast, symbol_table)
    return result

# --- Example Usage ---
if __name__ == '__main__':
    engage_code = """
    to calculate_score with base_score, bonus:
        let final_score be base_score plus bonus.
        if final_score is greater than 100 then
            print with "Max score! Capping at 100.".
            return 100.
        end
        return final_score.
    end

    let player_score be 85.
    let score_bonus be 20.
    
    print with "Calculating final score...".
    let final_player_score be calculate_score with player_score, score_bonus.
    print with "Final score is:".
    print with final_player_score.
    """

    print("--- Running Engage Code ---")
    print(f"CODE:\n{engage_code}\n")
    print("--- OUTPUT ---")
    
    try:
        run(engage_code, global_symbol_table)
    except Exception as e:
        print(f"An error occurred: {e}")

