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
# Using constants for token types
TT_KEYWORD = 'KEYWORD'
TT_IDENTIFIER = 'IDENTIFIER'
TT_NUMBER = 'NUMBER'
TT_STRING = 'STRING'
TT_OPERATOR = 'OPERATOR'
TT_PUNCTUATION = 'PUNCTUATION'
TT_EOF = 'EOF' # End of File

# --- Language Definitions ---
# Based on the Engage Syntax Guide
KEYWORDS = [
    'create', 'let', 'be', 'with', 'the', 'value', 'define', 'as',
    'set', 'to', 'if', 'then', 'otherwise', 'end', 'switch', 'on',
    'case', 'default', 'repeat', 'times', 'while', 'for', 'each', 'in',
    'break', 'continue', 'returns', 'return', 'Ok', 'Error',
    'component', 'state', 'is', 'view', 'render', 'into', 'game_object',
    'on', 'step', 'draw', 'unsafe', 'pointer', 'dialect', 'interpret',
    'using', 'export', 'import', 'a' # 'a' is treated like a keyword for declaration
]

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
        if self.pos > len(self.text) - 1:
            self.current_char = None  # End of input
        else:
            self.current_char = self.text[self.pos]

    def skip_whitespace(self):
        """Skip over any whitespace characters."""
        while self.current_char is not None and self.current_char.isspace():
            self.advance()

    def skip_comment(self):
        """Skip over single-line and multi-line comments."""
        if self.current_char == '/' and self.peek() == '/':
            while self.current_char is not None and self.current_char != '\n':
                self.advance()
            self.advance() # Skip the newline
            return True
        if self.current_char == '/' and self.peek() == '*':
            self.advance() # consume /
            self.advance() # consume *
            while self.current_char is not None:
                if self.current_char == '*' and self.peek() == '/':
                    self.advance()
                    self.advance()
                    break
                self.advance()
            return True
        return False

    def peek(self):
        """Look at the next character without consuming the current one."""
        peek_pos = self.pos + 1
        if peek_pos > len(self.text) - 1:
            return None
        else:
            return self.text[peek_pos]

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
        self.advance()  # Skip the opening quote
        start_col = self.column
        while self.current_char is not None and self.current_char != '"':
            result += self.current_char
            self.advance()
        self.advance()  # Skip the closing quote
        return Token(TT_STRING, result, self.line, start_col)

    def identifier(self):
        """Handle identifiers and reserved keywords."""
        result = ''
        start_col = self.column
        # Identifiers can contain letters, numbers, and underscores
        while self.current_char is not None and (self.current_char.isalnum() or self.current_char == '_'):
            result += self.current_char
            self.advance()
        
        # Check for multi-word operators
        # This is a simple way to handle them; a more robust parser would be better.
        if result == 'is' and self.text[self.pos:self.pos+4] == ' not':
             result = 'is not'
             self.advance(); self.advance(); self.advance(); self.advance()
        elif result == 'is' and self.text[self.pos:self.pos+13] == ' greater than':
             # ... and so on for other multi-word operators
             pass # This part can be made more robust

        token_type = TT_KEYWORD if result in KEYWORDS else TT_IDENTIFIER
        
        # Re-classify operators that are also words (e.g., 'and', 'or', 'not')
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

            if self.current_char.isdigit():
                return self.number()

            if self.current_char == '"':
                return self.string()

            if self.current_char.isalnum() or self.current_char == '_':
                return self.identifier()
            
            # Handle multi-character operators like '==' or '>='
            # This logic can be expanded
            if self.current_char in '<>!=' and self.peek() == '=':
                op = self.current_char + self.peek()
                start_col = self.column
                self.advance()
                self.advance()
                return Token(TT_OPERATOR, op, self.line, start_col)

            if self.current_char in PUNCTUATION:
                token = Token(TT_PUNCTUATION, self.current_char, self.line, self.column)
                self.advance()
                return token

            # If we get here, it's a character we don't recognize
            raise Exception(f"Lexer error: Unrecognized character '{self.current_char}' on line {self.line}, column {self.column}")

        return Token(TT_EOF, None, self.line, self.column)

# --- Main function to run the lexer ---
def tokenize(code):
    """Takes source code and returns a list of tokens."""
    lexer = Lexer(code)
    tokens = []
    while True:
        token = lexer.get_next_token()
        tokens.append(token)
        if token.type == TT_EOF:
            break
    return tokens

# --- Example Usage ---
if __name__ == '__main__':
    engage_code = """
// Example Engage Program
define GAME_TITLE as "Chronicles of Engage".

/*
  This function calculates the player's final score.
*/
to calculate_score with base_score, bonus:
    let final_score be base_score plus bonus.
    if final_score is greater than 100 then
        print "Max score reached!".
    end
    return final_score.
end

let p_score be the result of calculate_score with 85, 20.
"""

    print("--- Lexing Engage Code ---")
    print(f"CODE:\n{engage_code}\n")
    print("--- TOKENS ---")
    
    try:
        all_tokens = tokenize(engage_code)
        for t in all_tokens:
            print(t)
    except Exception as e:
        print(e)
