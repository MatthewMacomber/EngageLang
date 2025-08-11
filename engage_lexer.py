import re
from engage_errors import EngageError, ErrorAggregator, SourceContextExtractor, create_syntax_error

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
TT_EOL = 'EOL' # End of Line
TT_EOF = 'EOF' # End of File

# --- Language Definitions ---
KEYWORDS = [
    'create', 'let', 'be', 'with', 'the', 'value', 'as',
    'set', 'to', 'if', 'then', 'otherwise', 'end', 'switch', 'on',
    'case', 'default', 'repeat', 'times', 'while', 'for', 'each', 'in',
    'break', 'continue', 'returns', 'return', 'Ok', 'Error',
    'component', 'state', 'is', 'view', 'render', 'into', 'game_object',
    'on', 'step', 'draw', 'unsafe', 'pointer', 'dialect', 'interpret',
    'using', 'export', 'import', 'a',
    'run', 'concurrently', 'channel', 'named', 'send', 'through', 'receive', 'from',
    'define', 'fiber', 'yield',
    'record', 'new', 'self',
    'Table', 'Vector', 'Record', 'property'
]

OPERATORS = [
    'plus', '+', 'minus', '-', 'times', '*', 'divided by', '/', 'modulo', '%',
    'is', '==', 'is not', '!=', 'is greater than', '>', 'is less than', '<',
    'is greater than or equal to', '>=', 'is less than or equal to', '<=',
    'and', 'or', 'not', 'concatenated with',
    'call',
    'is an', 'or return error', 'the ok value of', 'the error message of'
]

PUNCTUATION = '.:,[]{}()<>='

class Lexer:
    """
    The Lexer is responsible for breaking the source code
    into a stream of tokens with enhanced error reporting.
    """
    def __init__(self, text, file_path=None):
        self.text = text
        self.file_path = file_path
        self.pos = 0
        self.current_char = self.text[self.pos] if self.pos < len(self.text) else None
        self.line = 1
        self.column = 1
        
        # Enhanced error reporting
        self.error_aggregator = ErrorAggregator()
        self.source_lines = SourceContextExtractor.extract_from_text(text)
        self.error_aggregator.set_source_context(self.source_lines, file_path)

    def advance(self):
        """Move the position pointer and update the current character."""
        if self.current_char == '\n':
            self.line += 1
            self.column = 0
        self.pos += 1
        self.column += 1
        self.current_char = self.text[self.pos] if self.pos < len(self.text) else None

    def skip_space_and_tabs(self):
        """Skip over any whitespace characters except newline."""
        while self.current_char is not None and self.current_char in ' \t\r':
            self.advance()

    def skip_comment(self):
        """Skip over single-line and multi-line comments."""
        if self.current_char == '/' and self.peek() == '/':
            while self.current_char is not None and self.current_char != '\n':
                self.advance()
            return True # Let the main loop handle the newline
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
        start_col = self.column
        while self.current_char is not None and self.current_char.isdigit():
            result += self.current_char
            self.advance()
        if self.current_char == '.':
            # Check if it's a decimal point or a member access dot
            if self.peek() and self.peek().isdigit():
                result += '.'
                self.advance()
                while self.current_char is not None and self.current_char.isdigit():
                    result += self.current_char
                    self.advance()
                return Token(TT_NUMBER, float(result), self.line, start_col)
        
        return Token(TT_NUMBER, int(result), self.line, start_col)


    def string(self):
        """Return a string literal, with support for escape sequences."""
        result = ''
        self.advance()  # consume the opening "
        start_col = self.column
        while self.current_char is not None and self.current_char != '"':
            if self.current_char == '\\':
                self.advance()  # consume the backslash
                if self.current_char is None:
                    # Unterminated string
                    break
                if self.current_char == 'n':
                    result += '\n'
                elif self.current_char == 't':
                    result += '\t'
                elif self.current_char == 'r':
                    result += '\r'
                elif self.current_char == '"':
                    result += '"'
                elif self.current_char == '\\':
                    result += '\\'
                else:
                    # For an invalid escape sequence, just add the character as is
                    result += self.current_char
            else:
                result += self.current_char
            self.advance()

        if self.current_char != '"':
            # Handle unterminated string error
            error = create_syntax_error(
                message="Unterminated string literal",
                line=self.line,
                column=start_col,
                file_path=self.file_path,
                source_lines=self.source_lines
            )
            error.add_suggestion("Make sure to close your string with a double quote (\").")
            self.error_aggregator.add_error(error)
            # We can return what we have so far or just an empty token
            return Token(TT_STRING, result, self.line, start_col)

        self.advance()  # consume the closing "
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
            if self.current_char in ' \t\r':
                self.skip_space_and_tabs()
                continue
            
            if self.current_char == '\n':
                line, col = self.line, self.column
                self.advance()
                return Token(TT_EOL, '\\n', line, col)

            if self.skip_comment():
                continue

            # Sort operators by length to match the longest one first (e.g., 'is not' before 'is')
            sorted_ops = sorted(OPERATORS, key=len, reverse=True)
            for op in sorted_ops:
                if self.text[self.pos:].startswith(op):
                    start_col = self.column
                    for _ in op: self.advance()
                    return Token(TT_OPERATOR, op, self.line, start_col)
            
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

            # Create enhanced error with suggestions
            error = create_syntax_error(
                message=f"Unrecognized character '{self.current_char}'",
                line=self.line,
                column=self.column,
                file_path=self.file_path,
                source_lines=self.source_lines
            )
            
            # Add specific suggestions for common character mistakes
            if self.current_char == '"':
                error.add_suggestion("Use double quotes (\") for string literals")
            elif self.current_char == "'":
                error.add_suggestion("Engage uses double quotes (\") for strings, not single quotes")
            elif self.current_char in '{}':
                error.add_suggestion("Engage uses 'record' definitions instead of curly braces")
            elif self.current_char == ';':
                error.add_suggestion("Engage uses periods (.) to end statements, not semicolons")
            elif self.current_char == '&':
                error.add_suggestion("Use 'and' instead of '&' for logical operations")
            elif self.current_char == '|':
                error.add_suggestion("Use 'or' instead of '|' for logical operations")
            
            self.error_aggregator.add_error(error)
            raise Exception(error.format_error())

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
    
    def has_errors(self):
        """Check if any lexical errors were encountered."""
        return self.error_aggregator.has_errors()
    
    def get_errors(self):
        """Get all lexical errors that were encountered."""
        return self.error_aggregator.errors
    
    def get_error_report(self):
        """Get a formatted report of all lexical errors."""
        return self.error_aggregator.format_all_errors()
    
    def clear_errors(self):
        """Clear all accumulated errors."""
        self.error_aggregator.clear()