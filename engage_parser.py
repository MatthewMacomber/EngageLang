# This code assumes the Lexer from the 'engage_lexer_python' artifact is in a file
# named 'engage_lexer.py'.
from engage_lexer import Lexer, Token, TT_EOF, TT_KEYWORD, TT_IDENTIFIER, TT_NUMBER, TT_STRING, TT_OPERATOR, TT_PUNCTUATION

# --- AST Node Definitions ---
# The parser will build a tree of these nodes. Each class represents a
# different kind of construct in the Engage language.

class ASTNode:
    """Base class for all AST nodes."""
    pass

class ProgramNode(ASTNode):
    """Represents the entire program, a list of statements."""
    def __init__(self, statements):
        self.statements = statements
    def __repr__(self):
        return f"Program({self.statements})"

class VarAssignNode(ASTNode):
    """Represents a variable assignment, e.g., 'let score be 100'."""
    def __init__(self, name_token, value_node):
        self.name_token = name_token
        self.value_node = value_node
    def __repr__(self):
        return f"VarAssign({self.name_token.value}, {self.value_node})"

class VarAccessNode(ASTNode):
    """Represents accessing a variable's value."""
    def __init__(self, name_token):
        self.name_token = name_token
    def __repr__(self):
        return f"VarAccess({self.name_token.value})"

class BinOpNode(ASTNode):
    """Represents a binary operation, e.g., 'a plus b'."""
    def __init__(self, left_node, op_token, right_node):
        self.left_node = left_node
        self.op_token = op_token
        self.right_node = right_node
    def __repr__(self):
        return f"BinOp({self.left_node}, {self.op_token.value}, {self.right_node})"

class NumberNode(ASTNode):
    """Represents a number literal."""
    def __init__(self, token):
        self.token = token
        self.value = token.value
    def __repr__(self):
        return f"Number({self.value})"

class StringNode(ASTNode):
    """Represents a string literal."""
    def __init__(self, token):
        self.token = token
        self.value = token.value
    def __repr__(self):
        return f"String({self.value})"
        
class FuncDefNode(ASTNode):
    """Represents a function definition, e.g., 'to my_func with a, b: ... end'."""
    def __init__(self, name_token, param_tokens, body_nodes):
        self.name_token = name_token
        self.param_tokens = param_tokens
        self.body_nodes = body_nodes
    def __repr__(self):
        params = [p.value for p in self.param_tokens]
        return f"FuncDef(name={self.name_token.value}, params={params}, body={self.body_nodes})"

class FuncCallNode(ASTNode):
    """Represents a function call."""
    def __init__(self, node_to_call, arg_nodes):
        self.node_to_call = node_to_call
        self.arg_nodes = arg_nodes
    def __repr__(self):
        return f"FuncCall(name={self.node_to_call}, args={self.arg_nodes})"

class ReturnNode(ASTNode):
    """Represents a return statement."""
    def __init__(self, node_to_return):
        self.node_to_return = node_to_return
    def __repr__(self):
        return f"Return({self.node_to_return})"

class IfNode(ASTNode):
    """Represents an if/otherwise statement."""
    def __init__(self, cases, else_case):
        self.cases = cases # List of (condition, statements) tuples
        self.else_case = else_case # List of statements or None
    def __repr__(self):
        return f"If(cases={self.cases}, else_case={self.else_case})"

# --- Parser ---

class Parser:
    """
    The Parser takes a list of tokens and builds an Abstract Syntax Tree (AST).
    It uses a recursive descent parsing strategy.
    """
    def __init__(self, tokens):
        self.tokens = tokens
        self.token_idx = -1
        self.current_token = None
        self.advance()

    def advance(self):
        """Moves to the next token in the list."""
        self.token_idx += 1
        if self.token_idx < len(self.tokens):
            self.current_token = self.tokens[self.token_idx]
        return self.current_token

    def parse(self):
        """Top-level method that parses the entire program."""
        statements = []
        # Continue parsing statements until the end of the file
        while self.current_token.type != TT_EOF:
            statements.append(self.statement())
            # Statements should end with a period, but we can be lenient
            if self.current_token.type == TT_PUNCTUATION and self.current_token.value == '.':
                self.advance()
        return ProgramNode(statements)

    def statement(self):
        """Parses a single statement."""
        # Check for keywords to determine the statement type
        if self.current_token.type == TT_KEYWORD:
            if self.current_token.value == 'let':
                return self.variable_assignment()
            if self.current_token.value == 'to':
                return self.function_definition()
            if self.current_token.value == 'if':
                return self.if_statement()
            if self.current_token.value == 'return':
                return self.return_statement()
        
        # If it's not a keyword-based statement, it must be an expression
        return self.expression()

    def return_statement(self):
        """Parses 'return {expression}'"""
        self.advance() # Skip 'return'
        expr = self.expression()
        return ReturnNode(expr)

    def if_statement(self):
        """Parses 'if ... then ... otherwise ... end'"""
        cases = []
        else_case = None

        # --- Parse 'if' and 'otherwise if' cases ---
        while self.current_token.type == TT_KEYWORD and self.current_token.value in ('if', 'otherwise'):
            is_otherwise_if = self.current_token.value == 'otherwise'
            self.advance() # Skip 'if' or 'otherwise'
            if is_otherwise_if:
                if self.current_token.type != TT_KEYWORD or self.current_token.value != 'if':
                    raise SyntaxError("Expected 'if' after 'otherwise'")
                self.advance() # Skip 'if'

            condition = self.expression()

            if not (self.current_token.type == TT_KEYWORD and self.current_token.value == 'then'):
                raise SyntaxError("Expected 'then' after if condition")
            self.advance() # Skip 'then'

            # Parse the statements in the block
            statements = []
            while not (self.current_token.type == TT_KEYWORD and self.current_token.value in ('end', 'otherwise')):
                statements.append(self.statement())
                if self.current_token.type == TT_PUNCTUATION and self.current_token.value == '.':
                    self.advance()

            cases.append((condition, statements))

            if not (self.current_token.type == TT_KEYWORD and self.current_token.value in ('otherwise', 'end')):
                raise SyntaxError("Expected 'otherwise' or 'end'")

        # --- Parse 'otherwise' (else) case ---
        if self.current_token.type == TT_KEYWORD and self.current_token.value == 'otherwise':
            self.advance() # Skip 'otherwise'
            else_case = []
            while not (self.current_token.type == TT_KEYWORD and self.current_token.value == 'end'):
                else_case.append(self.statement())
                if self.current_token.type == TT_PUNCTUATION and self.current_token.value == '.':
                    self.advance()
        
        if not (self.current_token.type == TT_KEYWORD and self.current_token.value == 'end'):
            raise SyntaxError("Expected 'end' to close if statement")
        self.advance() # Skip 'end'

        return IfNode(cases, else_case)

    def function_definition(self):
        """Parses 'to {name} with {params}: ... end'"""
        self.advance() # Skip 'to'
        if self.current_token.type != TT_IDENTIFIER:
            raise SyntaxError("Expected function name")
        
        name_token = self.current_token
        self.advance()

        params = []
        if self.current_token.type == TT_KEYWORD and self.current_token.value == 'with':
            self.advance() # Skip 'with'
            while self.current_token.type == TT_IDENTIFIER:
                params.append(self.current_token)
                self.advance()
                if self.current_token.type == TT_PUNCTUATION and self.current_token.value == ',':
                    self.advance() # Skip comma

        if not (self.current_token.type == TT_PUNCTUATION and self.current_token.value == ':'):
            # For simplicity, we'll make the colon optional for now
            pass
        else:
            self.advance()

        # Parse the function body
        body = []
        while not (self.current_token.type == TT_KEYWORD and self.current_token.value == 'end'):
             body.append(self.statement())
             if self.current_token.type == TT_PUNCTUATION and self.current_token.value == '.':
                self.advance()

        if not (self.current_token.type == TT_KEYWORD and self.current_token.value == 'end'):
            raise SyntaxError("Expected 'end' to close function definition")
        self.advance() # Skip 'end'

        return FuncDefNode(name_token, params, body)

    def variable_assignment(self):
        """Parses 'let {name} be {expression}'"""
        self.advance() # Skip 'let'
        
        if self.current_token.type != TT_IDENTIFIER:
            raise SyntaxError("Expected identifier after 'let'")
        
        name_token = self.current_token
        self.advance()

        if not (self.current_token.type == TT_KEYWORD and self.current_token.value == 'be'):
            raise SyntaxError("Expected 'be' in variable assignment")
        self.advance() # Skip 'be'

        value_node = self.expression()
        return VarAssignNode(name_token, value_node)

    def expression(self):
        """Parses an expression, handling binary operations."""
        # For now, we'll parse simple terms. A full implementation would handle
        # operator precedence (e.g., using the shunting-yard algorithm or
        # breaking this into multiple methods like term, factor, etc.).
        node = self.term()

        while self.current_token.type == TT_OPERATOR and self.current_token.value in ('plus', '+', 'minus', '-', 'is greater than', '>'):
            op_token = self.current_token
            self.advance()
            right_node = self.term()
            node = BinOpNode(node, op_token, right_node)
        
        return node
    
    def term(self):
        """Parses a 'term' - a factor or a sequence of factors multiplied/divided."""
        # This is a simplified version. A full parser would have more levels
        # of precedence here (e.g., for `times` and `divided by`).
        return self.factor()

    def factor(self):
        """Parses a 'factor' - the highest precedence part of an expression."""
        token = self.current_token

        if token.type == TT_NUMBER:
            self.advance()
            return NumberNode(token)
        
        if token.type == TT_STRING:
            self.advance()
            return StringNode(token)

        if token.type == TT_IDENTIFIER:
            # Could be a variable access or a function call
            var_name = self.current_token
            self.advance()
            
            # Check for function call, e.g. `my_func with ...`
            if self.current_token.type == TT_KEYWORD and self.current_token.value == 'with':
                 self.advance() # skip 'with'
                 args = []
                 # Naive argument parsing. A real one would expect expressions.
                 while self.current_token.type in (TT_IDENTIFIER, TT_NUMBER, TT_STRING):
                     args.append(self.expression())
                     if self.current_token.type == TT_PUNCTUATION and self.current_token.value == ',':
                         self.advance()
                     else:
                         break
                 return FuncCallNode(VarAccessNode(var_name), args)

            return VarAccessNode(var_name)
        
        if token.type == TT_PUNCTUATION and token.value == '(':
            self.advance()
            expr = self.expression()
            if not (self.current_token.type == TT_PUNCTUATION and self.current_token.value == ')'):
                raise SyntaxError("Expected ')'")
            self.advance()
            return expr

        raise SyntaxError(f"Parser error: Unexpected token {token}")


# --- Main function to run the parser ---
def parse_code(code):
    """Takes source code and returns the root of the AST."""
    lexer = Lexer(code)
    tokens = []
    while True:
        token = lexer.get_next_token()
        tokens.append(token)
        if token.type == TT_EOF:
            break
    
    parser = Parser(tokens)
    return parser.parse()

# --- Example Usage ---
if __name__ == '__main__':
    engage_code = """
    to calculate_score with base_score, bonus:
        let final_score be base_score plus bonus.
        if final_score is greater than 100 then
            return 100.
        end
        return final_score.
    end

    let p_score be calculate_score with 85, 20.
    """

    print("--- Parsing Engage Code ---")
    print(f"CODE:\n{engage_code}\n")
    print("--- ABSTRACT SYNTAX TREE ---")
    
    try:
        ast = parse_code(engage_code)
        # The default __repr__ of the nodes will give a nice tree-like view
        print(ast)
    except Exception as e:
        print(e)
