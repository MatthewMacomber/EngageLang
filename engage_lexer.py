import re

class Token:
    """A simple class to represent a token."""
    def __init__(self, type, value, line, column):
        self.type = type
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self):
        """String representation of the token."""
        return f"Token({self.type}, {repr(self.value)}, line={self.line}, col={self.column})"

# --- Token Type Definitions ---
TT_KEYWORD = 'KEYWORD'
TT_IDENTIFIER = 'IDENTIFIER'
TT_NUMBER = 'NUMBER'
TT_STRING = 'STRING'
TT_OPERATOR = 'OPERATOR'
TT_PUNCTUATION = 'PUNCTUATION'
TT_EOF = 'EOF'

# --- Language Definitions ---
# This list now contains all keywords, including for concurrency.
KEYWORDS = [
    'create', 'let', 'be', 'with', 'the', 'value', 'define', 'as',
    'set', 'to', 'if', 'then', 'otherwise', 'end', 'switch', 'on',
    'case', 'default', 'repeat', 'times', 'while', 'for', 'each', 'in',
    'break', 'continue', 'returns', 'return', 'Ok', 'Error',
    'component', 'state', 'is', 'view', 'render', 'into', 'game_object',
    'on', 'step', 'draw', 'unsafe', 'pointer', 'dialect', 'interpret',
    'using', 'export', 'import', 'a',
    # Concurrency Keywords
    'run', 'concurrently', 'channel', 'named', 'send', 'through', 'receive', 'from'
]

# All operators, including multi-word ones.
OPERATORS = [
    'plus', '+', 'minus', '-', 'times', '*', 'divided by', '/', 'modulo', '%',
    'is', '==', 'is not', '!=', 'is greater than', '>', 'is less than', '<',
    'is greater than or equal to', '>=', 'is less than or equal to', '<=',
    'and', 'or', 'not', 'concatenated with'
]

PUNCTUATION = '.:,[]{}()<>='

class Lexer:
    """
    The Lexer is responsible for breaking the source code
    into a stream of tokens.
    """
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.current_char = self.text[self.pos] if self.pos < len(self.text) else None
        self.line = 1
        self.column = 1

    def advance(self):
        """Move the position pointer and update the current character."""
        if self.current_char == '\n':
            self.line += 1
            self.column = 0
        self.pos += 1
        self.column += 1
        self.current_char = self.text[self.pos] if self.pos < len(self.text) else None

    def skip_whitespace(self):
        """Skip over any whitespace characters."""
        while self.current_char is not None and self.current_char.isspace():
            self.advance()

    def skip_comment(self):
        """Skip over single-line and multi-line comments."""
        if self.current_char == '/' and self.peek() == '/':
            while self.current_char is not None and self.current_char != '\n':
                self.advance()
            self.advance()
            return True
        if self.current_char == '/' and self.peek() == '*':
            self.advance(); self.advance()
            while self.current_char is not None:
                if self.current_char == '*' and self.peek() == '/':
                    self.advance(); self.advance()
                    break
                self.advance()
            return True
        return False

    def peek(self):
        """Look at the next character without consuming the current one."""
        peek_pos = self.pos + 1
        return self.text[peek_pos] if peek_pos < len(self.text) else None

    def number(self):
        """Return a multidigit integer or float consumed from the input."""
        result = ''
        while self.current_char is not None and self.current_char.isdigit():
            result += self.current_char
            self.advance()
        if self.current_char == '.':
            result += '.'
            self.advance()
            while self.current_char is not None and self.current_char.isdigit():
                result += self.current_char
                self.advance()
        return Token(TT_NUMBER, float(result), self.line, self.column)

    def string(self):
        """Return a string literal."""
        result = ''
        self.advance()
        start_col = self.column
        while self.current_char is not None and self.current_char != '"':
            result += self.current_char
            self.advance()
        self.advance()
        return Token(TT_STRING, result, self.line, start_col)

    def identifier(self):
        """Handle identifiers and reserved keywords."""
        result = ''
        start_col = self.column
        while self.current_char is not None and (self.current_char.isalnum() or self.current_char == '_'):
            result += self.current_char
            self.advance()
        
        token_type = TT_KEYWORD if result in KEYWORDS else TT_IDENTIFIER
        if result in OPERATORS:
            token_type = TT_OPERATOR
        return Token(token_type, result, self.line, start_col)

    def get_next_token(self):
        """Lexical analyzer (also known as scanner or tokenizer)"""
        while self.current_char is not None:
            if self.current_char.isspace():
                self.skip_whitespace()
                continue
            if self.skip_comment():
                continue

            # --- START REFACTORED LOGIC ---
            # Handle multi-word operators by checking for the longest match first.
            # This is more robust than the previous implementation.
            longest_op = None
            for op in OPERATORS:
                if self.text[self.pos:].startswith(op):
                    if longest_op is None or len(op) > len(longest_op):
                        longest_op = op
            
            if longest_op and len(longest_op) > 1:
                start_col = self.column
                for _ in longest_op: self.advance()
                return Token(TT_OPERATOR, longest_op, self.line, start_col)
            # --- END REFACTORED LOGIC ---

            if self.current_char.isdigit():
                return self.number()
            if self.current_char == '"':
                return self.string()
            if self.current_char.isalnum() or self.current_char == '_':
                return self.identifier()
            if self.current_char in PUNCTUATION:
                token = Token(TT_PUNCTUATION, self.current_char, self.line, self.column)
                self.advance()
                return token

            raise Exception(f"Lexer error: Unrecognized character '{self.current_char}' on line {self.line}, column {self.column}")

        return Token(TT_EOF, None, self.line, self.column)

    def tokenize(self):
        """Helper method to return a list of all tokens."""
        tokens = []
        while True:
            token = self.get_next_token()
            tokens.append(token)
            if token.type == TT_EOF:
                break
        return tokens
