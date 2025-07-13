# This code assumes the Lexer from the 'engage_lexer_python' artifact is in a file
# named 'engage_lexer.py'.
from engage_lexer import Lexer, Token, TT_EOF, TT_KEYWORD, TT_IDENTIFIER, TT_NUMBER, TT_STRING, TT_OPERATOR, TT_PUNCTUATION

# --- AST Node Definitions ---

class ASTNode:
    """Base class for all AST nodes."""
    pass

class ProgramNode(ASTNode):
    def __init__(self, statements):
        self.statements = statements
    def __repr__(self):
        return f"Program({self.statements})"

class VarAssignNode(ASTNode):
    def __init__(self, name_token, value_node):
        self.name_token = name_token
        self.value_node = value_node
    def __repr__(self):
        return f"VarAssign(name={self.name_token.value}, value={self.value_node})"

class VarAccessNode(ASTNode):
    def __init__(self, name_token):
        self.name_token = name_token
    def __repr__(self):
        return f"VarAccess({self.name_token.value})"

class BinOpNode(ASTNode):
    def __init__(self, left_node, op_token, right_node):
        self.left_node = left_node
        self.op_token = op_token
        self.right_node = right_node
    def __repr__(self):
        return f"BinOp({self.left_node}, op='{self.op_token.value}', {self.right_node})"

class UnaryOpNode(ASTNode):
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
        self.cases = cases
        self.else_case = else_case
    def __repr__(self):
        return f"If(cases={self.cases}, else_case={self.else_case})"

class WhileNode(ASTNode):
    def __init__(self, condition_node, body_nodes):
        self.condition_node = condition_node
        self.body_nodes = body_nodes
    def __repr__(self):
        return f"While(condition={self.condition_node}, body={self.body_nodes})"

class TaskNode(ASTNode):
    def __init__(self, body_nodes):
        self.body_nodes = body_nodes
    def __repr__(self):
        return f"Task(body={self.body_nodes})"

class ChannelNode(ASTNode):
    def __init__(self, name_token):
        self.name_token = name_token
    def __repr__(self):
        return f"Channel(name={self.name_token.value})"

class SendNode(ASTNode):
    def __init__(self, value_node, channel_node):
        self.value_node = value_node
        self.channel_node = channel_node
    def __repr__(self):
        return f"Send(value={self.value_node}, channel={self.channel_node})"

class ReceiveNode(ASTNode):
    def __init__(self, channel_node):
        self.channel_node = channel_node
    def __repr__(self):
        return f"Receive(channel={self.channel_node})"

# --- Parser ---

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.token_idx = -1
        self.current_token = None
        self.advance()

    def advance(self):
        self.token_idx += 1
        if self.token_idx < len(self.tokens):
            self.current_token = self.tokens[self.token_idx]
        return self.current_token

    def consume(self, expected_type, expected_value=None):
        if self.current_token.type == expected_type and \
           (expected_value is None or self.current_token.value == expected_value):
            self.advance()
        else:
            raise SyntaxError(f"Expected token {expected_type} ('{expected_value}') but got {self.current_token.type} ('{self.current_token.value}')")

    def parse(self):
        statements = []
        while self.current_token.type != TT_EOF:
            statements.append(self.parse_statement())
            if self.current_token.type == TT_PUNCTUATION and self.current_token.value == '.':
                self.advance()
        return ProgramNode(statements)

    def parse_statement_list(self, end_keywords):
        statements = []
        while self.current_token.type != TT_EOF and \
              not (self.current_token.type == TT_KEYWORD and self.current_token.value in end_keywords):
            statements.append(self.parse_statement())
            if self.current_token.type == TT_PUNCTUATION and self.current_token.value == '.':
                self.advance()
        return statements

    def parse_statement(self):
        if self.is_name_token(self.current_token):
            if self.token_idx + 1 < len(self.tokens):
                next_token = self.tokens[self.token_idx + 1]
                if self.get_precedence(next_token) == 0 and next_token.value != 'with':
                     name_token = self.parse_name_token()
                     return FuncCallNode(VarAccessNode(name_token), [])

        if self.current_token.type == TT_KEYWORD:
            if self.current_token.value == 'let':
                return self.parse_variable_assignment()
            if self.current_token.value == 'to':
                return self.parse_function_definition()
            if self.current_token.value == 'if':
                return self.parse_if_statement()
            if self.current_token.value == 'return':
                return self.parse_return_statement()
            if self.current_token.value == 'while':
                return self.parse_while_statement()
            if self.current_token.value == 'run':
                return self.parse_task_statement()
            if self.current_token.value == 'create':
                if self.token_idx + 2 < len(self.tokens) and self.tokens[self.token_idx + 2].value == 'channel':
                    return self.parse_channel_statement()
            if self.current_token.value == 'send':
                return self.parse_send_statement()
        
        return self.parse_expression()

    # --- Statement Parsers ---

    def parse_task_statement(self):
        self.consume(TT_KEYWORD, 'run')
        self.consume(TT_KEYWORD, 'concurrently')
        self.consume(TT_PUNCTUATION, ':')
        body = self.parse_statement_list(['end'])
        self.consume(TT_KEYWORD, 'end')
        return TaskNode(body)

    def parse_channel_statement(self):
        self.consume(TT_KEYWORD, 'create')
        self.consume(TT_KEYWORD, 'a')
        self.consume(TT_KEYWORD, 'channel')
        self.consume(TT_KEYWORD, 'named')
        name_token = self.parse_name_token()
        return ChannelNode(name_token)

    def parse_send_statement(self):
        self.consume(TT_KEYWORD, 'send')
        value_node = self.parse_expression()
        self.consume(TT_KEYWORD, 'through')
        channel_node = self.parse_name_token()
        return SendNode(value_node, VarAccessNode(channel_node))

    def parse_return_statement(self):
        self.consume(TT_KEYWORD, 'return')
        expr = self.parse_expression()
        return ReturnNode(expr)

    def parse_while_statement(self):
        self.consume(TT_KEYWORD, 'while')
        condition = self.parse_expression()
        if self.current_token.type == TT_PUNCTUATION and self.current_token.value == ':':
            self.advance()
        body = self.parse_statement_list(['end'])
        self.consume(TT_KEYWORD, 'end')
        return WhileNode(condition, body)

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
                self.advance()
                condition = self.parse_expression()
                self.consume(TT_KEYWORD, 'then')
                statements = self.parse_statement_list(['otherwise', 'end'])
                cases.append((condition, statements))
            else:
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
        if not token or token.type != TT_OPERATOR: 
            return 0
        op = token.value
        if op in ('or'): return 1
        if op in ('and'): return 2
        if op in ('is', '==', 'is not', '!='): return 3
        if op in ('is greater than', '>', 'is less than', '<', '>=', '<='): return 4
        # --- START REFACTORED LOGIC ---
        if op in ('plus', '+', 'minus', '-', 'concatenated with'): return 5
        # --- END REFACTORED LOGIC ---
        if op in ('times', '*', 'divided by', '/'): return 6
        return 0
    
    def is_name_token(self, token):
        RESERVED_KEYWORDS = [
            'if', 'then', 'otherwise', 'end', 'let', 'be', 'to', 'with', 'return',
            'while', 'for', 'repeat', 'and', 'or', 'not',
            'run', 'send', 'create'
        ]
        if token.type == TT_IDENTIFIER:
            return True
        if token.type == TT_KEYWORD and token.value not in RESERVED_KEYWORDS:
            return True
        return False

    def parse_name_token(self):
        token = self.current_token
        if self.is_name_token(token):
            self.advance()
            return token
        raise SyntaxError(f"Expected a valid name but got {token.type}('{token.value}')")

    def parse_atom(self):
        token = self.current_token
        if token.type == TT_NUMBER:
            self.advance()
            return NumberNode(token)
        if token.type == TT_STRING:
            self.advance()
            return StringNode(token)
        if token.type == TT_KEYWORD and token.value == 'receive':
            self.advance()
            self.consume(TT_KEYWORD, 'from')
            channel_node = self.parse_name_token()
            return ReceiveNode(VarAccessNode(channel_node))

        if self.is_name_token(token):
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
        name_token = self.parse_name_token()
        self.consume(TT_KEYWORD, 'with')
        arg_nodes = []
        if self.current_token.type != TT_PUNCTUATION or self.current_token.value != '.':
             while True:
                arg_nodes.append(self.parse_expression())
                if self.current_token.type == TT_PUNCTUATION and self.current_token.value == ',':
                    self.advance()
                else:
                    break
        return FuncCallNode(VarAccessNode(name_token), arg_nodes)

    def parse_expression(self, precedence=0):
        left = self.parse_atom()
        while precedence < self.get_precedence(self.current_token):
            op_token = self.current_token
            self.advance()
            right = self.parse_expression(self.get_precedence(op_token))
            left = BinOpNode(left, op_token, right)
        return left
