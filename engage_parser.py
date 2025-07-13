# This code assumes the Lexer from the 'engage_lexer_python' artifact is in a file
# named 'engage_lexer.py'.
from engage_lexer import Lexer, Token, TT_EOF, TT_KEYWORD, TT_IDENTIFIER, TT_NUMBER, TT_STRING, TT_OPERATOR, TT_PUNCTUATION

# --- AST Node Definitions ---
# These classes define the structure of the Abstract Syntax Tree.

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
        return f"VarAssign(name={self.name_token.value}, value={self.value_node})"

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
        return f"BinOp({self.left_node}, op='{self.op_token.value}', {self.right_node})"

class UnaryOpNode(ASTNode):
    """Represents a unary operation, e.g., 'not true'."""
    def __init__(self, op_token, node):
        self.op_token = op_token
        self.node = node
    def __repr__(self):
        return f"UnaryOp(op='{self.op_token.value}', {self.node})"

class NumberNode(ASTNode):
    def __init__(self, token):
        self.token = token
        self.value = token.value
    def __repr__(self):
        return f"Number({self.value})"

class StringNode(ASTNode):
    def __init__(self, token):
        self.token = token
        self.value = token.value
    def __repr__(self):
        return f"String({repr(self.value)})"
        
class FuncDefNode(ASTNode):
    def __init__(self, name_token, param_tokens, body_nodes):
        self.name_token = name_token
        self.param_tokens = param_tokens
        self.body_nodes = body_nodes
    def __repr__(self):
        params = [p.value for p in self.param_tokens]
        return f"FuncDef(name={self.name_token.value}, params={params}, body={self.body_nodes})"

class FuncCallNode(ASTNode):
    def __init__(self, node_to_call, arg_nodes):
        self.node_to_call = node_to_call
        self.arg_nodes = arg_nodes
    def __repr__(self):
        return f"FuncCall(name={self.node_to_call}, args={self.arg_nodes})"

class ReturnNode(ASTNode):
    def __init__(self, node_to_return):
        self.node_to_return = node_to_return
    def __repr__(self):
        return f"Return({self.node_to_return})"

class IfNode(ASTNode):
    def __init__(self, cases, else_case):
        self.cases = cases # List of (condition, statements) tuples
        self.else_case = else_case # List of statements or None
    def __repr__(self):
        return f"If(cases={self.cases}, else_case={self.else_case})"

# --- Parser ---

class Parser:
    """
    The Parser takes a list of tokens and builds an Abstract Syntax Tree (AST).
    This version uses a Pratt Parser for handling expressions, which correctly
    manages operator precedence.
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

    def consume(self, expected_type, expected_value=None):
        """Consumes the current token if it matches expectations, otherwise raises an error."""
        if self.current_token.type == expected_type and \
           (expected_value is None or self.current_token.value == expected_value):
            self.advance()
        else:
            raise SyntaxError(f"Expected token {expected_type} ('{expected_value}') but got {self.current_token.type} ('{self.current_token.value}')")

    def parse(self):
        """Top-level method that parses the entire program."""
        statements = []
        while self.current_token.type != TT_EOF:
            statements.append(self.parse_statement())
            # Top-level statements should end with a period for clarity.
            if self.current_token.type == TT_PUNCTUATION and self.current_token.value == '.':
                self.advance()
        return ProgramNode(statements)

    def parse_statement_list(self, end_keywords):
        """Parses a list of statements until one of the end_keywords is found."""
        statements = []
        while self.current_token.type != TT_EOF and \
              not (self.current_token.type == TT_KEYWORD and self.current_token.value in end_keywords):
            statements.append(self.parse_statement())
            if self.current_token.type == TT_PUNCTUATION and self.current_token.value == '.':
                self.advance()
        return statements

    def parse_statement(self):
        """Parses a single statement by dispatching based on the current token."""
        if self.current_token.type == TT_KEYWORD:
            if self.current_token.value == 'let':
                return self.parse_variable_assignment()
            if self.current_token.value == 'to':
                return self.parse_function_definition()
            if self.current_token.value == 'if':
                return self.parse_if_statement()
            if self.current_token.value == 'return':
                return self.parse_return_statement()
        
        # If it's not a keyword-based statement, it must be an expression.
        return self.parse_expression()

    # --- Statement Parsers ---

    def parse_return_statement(self):
        self.consume(TT_KEYWORD, 'return')
        expr = self.parse_expression()
        return ReturnNode(expr)

    def parse_if_statement(self):
        cases = []
        else_case = None
        self.consume(TT_KEYWORD, 'if')
        
        condition = self.parse_expression()
        self.consume(TT_KEYWORD, 'then')
        statements = self.parse_statement_list(['otherwise', 'end'])
        cases.append((condition, statements))

        while self.current_token.type == TT_KEYWORD and self.current_token.value == 'otherwise':
            self.advance()
            if self.current_token.type == TT_KEYWORD and self.current_token.value == 'if':
                self.advance() # 'otherwise if'
                condition = self.parse_expression()
                self.consume(TT_KEYWORD, 'then')
                statements = self.parse_statement_list(['otherwise', 'end'])
                cases.append((condition, statements))
            else: # 'otherwise' (else)
                else_case = self.parse_statement_list(['end'])
                break
        
        self.consume(TT_KEYWORD, 'end')
        return IfNode(cases, else_case)

    def parse_function_definition(self):
        self.consume(TT_KEYWORD, 'to')
        name_token = self.parse_name_token()

        params = []
        if self.current_token.type == TT_KEYWORD and self.current_token.value == 'with':
            self.advance()
            while self.is_name_token(self.current_token):
                params.append(self.parse_name_token())
                if self.current_token.type == TT_PUNCTUATION and self.current_token.value == ',':
                    self.advance()
                else:
                    break
        
        self.consume(TT_PUNCTUATION, ':')
        body = self.parse_statement_list(['end'])
        self.consume(TT_KEYWORD, 'end')
        return FuncDefNode(name_token, params, body)

    def parse_variable_assignment(self):
        self.consume(TT_KEYWORD, 'let')
        name_token = self.parse_name_token()
        self.consume(TT_KEYWORD, 'be')
        value_node = self.parse_expression()
        return VarAssignNode(name_token, value_node)

    # --- Expression Parser (Pratt Parser) ---

    def get_precedence(self, token):
        """Returns the precedence level for a given operator token."""
        op = token.value
        if op in ('or'): return 1
        if op in ('and'): return 2
        if op in ('is', '==', 'is not', '!='): return 3
        if op in ('is greater than', '>', 'is less than', '<', '>=', '<='): return 4
        if op in ('plus', '+', 'minus', '-'): return 5
        if op in ('times', '*', 'divided by', '/'): return 6
        return 0 # Not an operator
    
    def is_name_token(self, token):
        """
        Checks if a token can be considered a name. This works around the lexer
        classifying common variable names like 'a' or 'n' as keywords.
        """
        # A specific list of keywords that are reserved for control flow and structure.
        RESERVED_KEYWORDS = [
            'if', 'then', 'otherwise', 'end', 'let', 'be', 'to', 'with', 'return',
            'while', 'for', 'repeat', 'and', 'or', 'not'
        ]
        if token.type == TT_IDENTIFIER:
            return True
        # Allow keywords to be names if they aren't structurally important.
        if token.type == TT_KEYWORD and token.value not in RESERVED_KEYWORDS:
            return True
        return False

    def parse_name_token(self):
        """Consumes and returns a token that represents a name."""
        token = self.current_token
        if self.is_name_token(token):
            self.advance()
            return token
        raise SyntaxError(f"Expected a valid name but got {token.type}('{token.value}')")

    def parse_atom(self):
        """Parses the most basic elements of an expression (literals, identifiers)."""
        token = self.current_token
        if token.type == TT_NUMBER:
            self.advance()
            return NumberNode(token)
        if token.type == TT_STRING:
            self.advance()
            return StringNode(token)
        
        # Use the helper to check if the token is a valid name.
        if self.is_name_token(token):
            # Check if it's a function call by peeking for 'with'
            if self.token_idx + 1 < len(self.tokens) and self.tokens[self.token_idx + 1].value == 'with':
                return self.parse_function_call()
            self.advance()
            return VarAccessNode(token)
            
        if token.value == '(':
            self.advance()
            expr = self.parse_expression()
            self.consume(TT_PUNCTUATION, ')')
            return expr
        if token.type == TT_OPERATOR and token.value == 'not':
            self.advance()
            return UnaryOpNode(token, self.parse_expression(7))
            
        raise SyntaxError(f"Unexpected token in expression: {token}")
    
    def parse_function_call(self):
        """Parses a function call expression."""
        name_token = self.parse_name_token()
        self.consume(TT_KEYWORD, 'with')
        
        arg_nodes = []
        if not (self.current_token.type == TT_PUNCTUATION and self.current_token.value == '.'):
             while True:
                arg_nodes.append(self.parse_expression())
                if self.current_token.type == TT_PUNCTUATION and self.current_token.value == ',':
                    self.advance()
                else:
                    break
        
        return FuncCallNode(VarAccessNode(name_token), arg_nodes)

    def parse_expression(self, precedence=0):
        """Parses a full expression with correct operator precedence."""
        left = self.parse_atom()

        while True:
            op_token = self.current_token
            potential_op = op_token.value
            
            if op_token.type == TT_OPERATOR and op_token.value == 'is':
                if self.token_idx + 1 < len(self.tokens):
                    next_token = self.tokens[self.token_idx + 1]
                    if next_token.value == 'not':
                        potential_op = 'is not'
                    elif next_token.value == 'greater' or next_token.value == 'less':
                        if self.token_idx + 2 < len(self.tokens) and self.tokens[self.token_idx + 2].value == 'than':
                            potential_op = f'is {next_token.value} than'

            temp_op_token = Token(TT_OPERATOR, potential_op, op_token.line, op_token.column)
            
            if not (precedence < self.get_precedence(temp_op_token)):
                break

            self.advance()
            if potential_op == 'is not':
                self.advance()
            elif potential_op in ('is greater than', 'is less than'):
                self.advance()
                self.advance()

            right = self.parse_expression(self.get_precedence(temp_op_token))
            left = BinOpNode(left, temp_op_token, right)
        
        return left

# --- Main function to run the parser ---
def parse_code(code):
    """Takes source code and returns the root of the AST."""
    from engage_lexer import Lexer # Assuming lexer is in another file
    
    # Add a tokenize method to the Lexer for convenience
    def lexer_tokenize(self):
        tokens = []
        while True:
            token = self.get_next_token()
            tokens.append(token)
            if token.type == TT_EOF:
                break
        return tokens
    Lexer.tokenize = lexer_tokenize

    lexer = Lexer(code)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()

# --- Example Usage ---
if __name__ == '__main__':
    # This example requires the engage_lexer.py file to be present
    # to run successfully.
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

    print("--- Parsing Engage Code ---")
    print(f"CODE:\n{engage_code}\n")
    print("--- ABSTRACT SYNTAX TREE ---")
    
    try:
        ast = parse_code(engage_code)
        import json
        def default(o):
            if isinstance(o, Token):
                return f"Token({o.type}, '{o.value}')"
            return o.__dict__
        print(json.dumps(ast, default=default, indent=2))
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\nParser Error: {e}")
