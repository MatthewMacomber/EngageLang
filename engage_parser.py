# engage_parser.py (Rewritten from scratch)
# This parser is designed to be more robust and handle all current Engage features.

from engage_lexer import Token, TT_EOF, TT_KEYWORD, TT_IDENTIFIER, TT_NUMBER, TT_STRING, TT_OPERATOR, TT_PUNCTUATION, TT_EOL
from engage_errors import EngageError, ErrorAggregator, SourceContextExtractor, create_syntax_error, ErrorSuggestionEngine

# --- AST Node Definitions ---
# A complete set of nodes representing the Engage language grammar.

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

class SetNode(ASTNode):
    def __init__(self, target_node, value_node):
        self.target_node = target_node
        self.value_node = value_node
    def __repr__(self):
        return f"Set(target={self.target_node}, value={self.value_node})"

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

class FiberDefNode(ASTNode):
    def __init__(self, name_token, body_nodes):
        self.name_token = name_token
        self.body_nodes = body_nodes
    def __repr__(self):
        return f"FiberDef(name={self.name_token.value}, body={self.body_nodes})"

class YieldNode(ASTNode):
    def __init__(self, value_node):
        self.value_node = value_node
    def __repr__(self):
        return f"Yield(value={self.value_node})"

class RecordDefNode(ASTNode):
    def __init__(self, name_token, members):
        self.name_token = name_token
        self.members = members
    def __repr__(self):
        return f"RecordDef(name={self.name_token.value}, members={self.members})"

class NewInstanceNode(ASTNode):
    def __init__(self, name_token, properties):
        self.name_token = name_token
        self.properties = properties
    def __repr__(self):
        return f"NewInstance(name={self.name_token.value}, props={self.properties})"

class MemberAccessNode(ASTNode):
    def __init__(self, instance_node, member_token):
        self.instance_node = instance_node
        self.member_token = member_token
    def __repr__(self):
        return f"MemberAccess(instance={self.instance_node}, member='{self.member_token.value}')"

class SelfNode(ASTNode):
    def __repr__(self):
        return "Self"

class ResultNode(ASTNode):
    def __init__(self, type_token, value_node):
        self.type_token = type_token
        self.value_node = value_node
    def __repr__(self):
        return f"Result(type={self.type_token.value}, value={self.value_node})"

class TypeNameNode(ASTNode):
    def __init__(self, type_token):
        self.type_token = type_token
    def __repr__(self):
        return f"TypeName({self.type_token.value})"

class TableNode(ASTNode):
    def __init__(self):
        pass
    def __repr__(self):
        return "Table()"

class VectorNode(ASTNode):
    def __init__(self):
        pass
    def __repr__(self):
        return "Vector()"

class RecordNode(ASTNode):
    def __init__(self, name_token):
        self.name_token = name_token
    def __repr__(self):
        return f"Record({self.name_token.value})"

class PropertyDefNode(ASTNode):
    def __init__(self, name_token, default_value):
        self.name_token = name_token
        self.default_value = default_value
    def __repr__(self):
        return f"PropertyDef(name={self.name_token.value}, default={self.default_value})"

class IndexAccessNode(ASTNode):
    def __init__(self, object_node, index_node):
        self.object_node = object_node
        self.index_node = index_node
    def __repr__(self):
        return f"IndexAccess(object={self.object_node}, index={self.index_node})"

class IndexAssignNode(ASTNode):
    def __init__(self, object_node, index_node, value_node):
        self.object_node = object_node
        self.index_node = index_node
        self.value_node = value_node
    def __repr__(self):
        return f"IndexAssign(object={self.object_node}, index={self.index_node}, value={self.value_node})"

class ImportNode(ASTNode):
    def __init__(self, module_name_token, alias_token=None):
        self.module_name_token = module_name_token
        self.alias_token = alias_token
    def __repr__(self):
        alias = f" as {self.alias_token.value}" if self.alias_token else ""
        return f"Import(module={self.module_name_token.value}{alias})"

class FromImportNode(ASTNode):
    def __init__(self, module_name_token, import_names):
        self.module_name_token = module_name_token
        self.import_names = import_names  # List of (name_token, alias_token) tuples
    def __repr__(self):
        names = []
        for name_token, alias_token in self.import_names:
            name_str = name_token.value
            if alias_token:
                name_str += f" as {alias_token.value}"
            names.append(name_str)
        return f"FromImport(module={self.module_name_token.value}, names=[{', '.join(names)}])"

class ExportVarNode(ASTNode):
    def __init__(self, name_token, value_node):
        self.name_token = name_token
        self.value_node = value_node
    def __repr__(self):
        return f"ExportVar(name={self.name_token.value}, value={self.value_node})"

class ExportFuncNode(ASTNode):
    def __init__(self, name_token, param_tokens, body_nodes):
        self.name_token = name_token
        self.param_tokens = param_tokens
        self.body_nodes = body_nodes
    def __repr__(self):
        params = [p.value for p in self.param_tokens]
        return f"ExportFunc(name={self.name_token.value}, params={params}, body={self.body_nodes})"

# --- Parser ---

class Parser:
    def __init__(self, tokens, file_path=None, source_text=None):
        self.tokens = tokens
        self.token_idx = -1
        self.current_token = None
        self.file_path = file_path
        
        # Enhanced error reporting
        self.error_aggregator = ErrorAggregator()
        if source_text:
            source_lines = SourceContextExtractor.extract_from_text(source_text)
            self.error_aggregator.set_source_context(source_lines, file_path)
        elif file_path:
            source_lines = SourceContextExtractor.extract_from_file(file_path)
            self.error_aggregator.set_source_context(source_lines, file_path)
        
        # Track available variables for better error suggestions
        self.available_variables = set()
        
        # Error recovery state
        self.recovery_mode = False
        self.recovery_tokens = {TT_PUNCTUATION, TT_KEYWORD, TT_EOL}
        self.statement_keywords = {'let', 'set', 'to', 'if', 'return', 'while', 'run', 'create', 'send', 'define', 'yield'}
        
        self.advance()

    def advance(self):
        self.token_idx += 1
        if self.token_idx < len(self.tokens):
            self.current_token = self.tokens[self.token_idx]
        return self.current_token

    def consume(self, expected_type, expected_value=None):
        """
        Original consume method that raises exceptions.
        Used when error recovery is not desired (e.g., in critical parsing contexts).
        """
        if (self.current_token and 
            self.current_token.type == expected_type and 
            (expected_value is None or self.current_token.value == expected_value)):
            self.advance()
        else:
            # Create enhanced error with context and suggestions
            error_msg = self.create_context_aware_error_message(expected_type, expected_value)
            error = create_syntax_error(
                message=error_msg,
                line=self.current_token.line if self.current_token else 1,
                column=self.current_token.column if self.current_token else 1,
                file_path=self.file_path
            )
            
            # Add specific suggestions based on the error context
            self.add_consume_error_suggestions(error, expected_type, expected_value)
            
            self.error_aggregator.add_error(error)
            raise SyntaxError(error.format_error())

    def create_context_aware_error_message(self, expected_type, expected_value=None):
        """Create context-aware error messages for EOL token issues and other parsing errors.
        
        Args:
            expected_type: The expected token type
            expected_value: The expected token value (optional)
            
        Returns:
            str: A clear, context-aware error message
        """
        if not self.current_token:
            return "Unexpected end of input. Expected more tokens to complete the statement."
        
        current_type = self.current_token.type
        current_value = self.current_token.value
        
        # Handle EOL token specific errors
        if current_type == TT_EOL:
            if expected_type == TT_PUNCTUATION and expected_value == '.':
                return ("Unexpected end of line. Expected a period (.) to terminate the statement. "
                       "Make sure your statement is complete before the line break.")
            elif expected_type == TT_KEYWORD:
                return (f"Unexpected end of line. Expected keyword '{expected_value}' to continue the statement. "
                       f"Check if your statement syntax is correct.")
            elif expected_type == TT_IDENTIFIER:
                return ("Unexpected end of line. Expected an identifier (variable or function name). "
                       "Make sure your expression is complete before the line break.")
            elif expected_type == TT_OPERATOR:
                return ("Unexpected end of line in expression. Expected an operator to continue the expression. "
                       "Check if your expression is complete.")
            else:
                return (f"Unexpected end of line. Expected {expected_type}"
                       f"{f' ({expected_value})' if expected_value else ''} to continue parsing. "
                       "Make sure your statement is complete before the line break.")
        
        # Handle EOF token specific errors  
        elif current_type == TT_EOF:
            if expected_type == TT_PUNCTUATION and expected_value == '.':
                return ("Unexpected end of file. Expected a period (.) to terminate the statement. "
                       "Make sure your last statement ends with a period.")
            elif expected_type == TT_KEYWORD and expected_value == 'end':
                return ("Unexpected end of file. Expected 'end' keyword to close a block. "
                       "Check if you have unmatched if/while/function/record definitions.")
            else:
                return (f"Unexpected end of file. Expected {expected_type}"
                       f"{f' ({expected_value})' if expected_value else ''} to complete the statement. "
                       "Check if your code is complete.")
        
        # Handle other token type mismatches
        else:
            expected_desc = f"{expected_type}"
            if expected_value:
                expected_desc += f" ('{expected_value}')"
            
            actual_desc = f"{current_type} ('{current_value}')"
            
            # Provide specific guidance for common mistakes
            if expected_type == TT_PUNCTUATION and expected_value == '.' and current_type == TT_KEYWORD:
                return (f"Expected period (.) to end statement, but found keyword '{current_value}'. "
                       "Make sure to end your statement with a period before starting a new one.")
            elif expected_type == TT_KEYWORD and current_type == TT_IDENTIFIER:
                return (f"Expected keyword '{expected_value}' but found identifier '{current_value}'. "
                       "Check your statement syntax - you might be missing a keyword.")
            else:
                return f"Expected {expected_desc} but got {actual_desc}."
    
    def add_consume_error_suggestions(self, error, expected_type, expected_value=None):
        """Add specific suggestions for consume() errors."""
        if expected_type == TT_PUNCTUATION and expected_value == '.':
            error.add_suggestion("Make sure to end your statement with a period (.)")
            error.add_suggestion("Check if your expression is complete")
        elif expected_type == TT_KEYWORD and expected_value == 'end':
            error.add_suggestion("Make sure to close your block with 'end'")
            error.add_suggestion("Check for unmatched if/while/function/record definitions")
        elif expected_type == TT_KEYWORD and expected_value:
            # Suggest similar keywords
            suggestions = ErrorSuggestionEngine.suggest_for_syntax_error(f"expected keyword {expected_value}")
            for suggestion in suggestions:
                error.add_suggestion(suggestion)
        elif expected_type == TT_IDENTIFIER:
            error.add_suggestion("Expected a variable or function name")
            error.add_suggestion("Check your spelling and make sure the identifier is valid")

    def skip_eols(self):
        """Skips any EOL tokens."""
        while self.current_token and self.current_token.type == TT_EOL:
            self.advance()

    def handle_unexpected_eol(self, context):
        """Handle unexpected EOL tokens with clear error messages.
        
        Args:
            context: String describing the parsing context where EOL was unexpected
            
        Raises:
            SyntaxError: With a context-aware error message
        """
        if self.current_token and self.current_token.type == TT_EOL:
            raise SyntaxError(f"Unexpected end of line in {context}. "
                            "Make sure your statement is complete before the line break.")
        elif self.current_token and self.current_token.type == TT_EOF:
            raise SyntaxError(f"Unexpected end of file in {context}. "
                            "Check if your code is complete.")
        else:
            raise SyntaxError(f"Unexpected token in {context}: {self.current_token}")

    def handle_eof_after_eol(self):
        """Handle EOF tokens that appear after EOL tokens gracefully.
        
        Returns:
            bool: True if EOF was handled gracefully, False if there are more tokens
        """
        # Skip any remaining EOL tokens
        self.skip_eols()
        
        # Check if we've reached EOF
        if self.current_token and self.current_token.type == TT_EOF:
            return True
        
        return False

    def validate_expression_context(self, context="expression"):
        """Validate that the current token is appropriate for expression parsing.
        
        Args:
            context: String describing the parsing context
            
        Raises:
            SyntaxError: If current token is inappropriate for expressions
        """
        if not self.current_token:
            raise SyntaxError(f"Unexpected end of input while parsing {context}.")
        
        if self.current_token.type == TT_EOL:
            raise SyntaxError(f"Unexpected end of line while parsing {context}. "
                            "Expected an expression or value.")
        
        if self.current_token.type == TT_EOF:
            raise SyntaxError(f"Unexpected end of file while parsing {context}. "
                            "Expected an expression or value.")

    def parse(self):
        """
        Main entry point. Parses a list of statements with error recovery.
        Continues parsing even after syntax errors to collect multiple errors.
        """
        statements = []
        self.skip_eols()
        
        while self.current_token and self.current_token.type != TT_EOF:
            try:
                self.exit_recovery_mode()  # Start each statement in normal mode
                stmt = self.parse_statement_with_recovery()
                if stmt is not None:  # Only add valid statements
                    statements.append(stmt)
                self.skip_eols()
            except SyntaxError:
                # If we get a syntax error, enter recovery mode
                self.enter_recovery_mode()
                self.recover_to_statement_boundary()
                self.skip_eols()
                continue
        
        return ProgramNode(statements)

    def parse_statement_list(self, end_keywords):
        """Helper to parse statements within a block (e.g., if, to, record)."""
        statements = []
        self.skip_eols()
        while self.current_token and self.current_token.type != TT_EOF and \
              not (self.current_token.type == TT_KEYWORD and self.current_token.value in end_keywords):
            try:
                stmt = self.parse_statement_with_recovery()
                if stmt is not None:
                    statements.append(stmt)
                self.skip_eols()
            except SyntaxError:
                # Recovery within blocks - try to continue to next statement or block end
                self.enter_recovery_mode()
                self.recover_to_statement_boundary()
                self.skip_eols()
                # Check if we've reached a block end during recovery
                if (self.current_token and 
                    self.current_token.type == TT_KEYWORD and 
                    self.current_token.value in end_keywords):
                    break
        return statements
    
    def parse_statement_with_recovery(self):
        """
        Parse a statement with error recovery support.
        Returns None if the statement couldn't be parsed due to errors.
        """
        if not self.current_token or self.current_token.type == TT_EOF:
            return None
        
        try:
            return self.parse_statement()
        except SyntaxError as e:
            # If we're already in recovery mode, don't re-enter
            if not self.recovery_mode:
                self.enter_recovery_mode()
            # Re-raise to trigger recovery at higher level
            raise

    def parse_statement(self):
        """Parses a single statement and its terminating period."""
        if self.current_token.type == TT_KEYWORD:
            if self.current_token.value == 'let': return self.parse_variable_assignment()
            if self.current_token.value == 'set': return self.parse_set_statement()
            if self.current_token.value == 'to':
                # Check if it's "to define" (record definition), "to export" (export function), or regular function definition
                if self.token_idx + 1 < len(self.tokens) and self.tokens[self.token_idx + 1].value == 'define':
                    return self.parse_record_definition()
                elif self.token_idx + 1 < len(self.tokens) and self.tokens[self.token_idx + 1].value == 'export':
                    return self.parse_export_function()
                else:
                    return self.parse_function_definition()
            if self.current_token.value == 'if': return self.parse_if_statement()
            if self.current_token.value == 'return': return self.parse_return_statement()
            if self.current_token.value == 'while': return self.parse_while_statement()
            if self.current_token.value == 'run': return self.parse_task_statement()
            if self.current_token.value == 'create':
                if self.token_idx + 2 < len(self.tokens) and self.tokens[self.token_idx + 2].value == 'channel':
                    return self.parse_channel_statement()
            if self.current_token.value == 'send': return self.parse_send_statement()
            if self.current_token.value == 'define':
                if self.token_idx + 2 < len(self.tokens) and self.tokens[self.token_idx + 2].value == 'fiber':
                    return self.parse_fiber_definition()
                if self.token_idx + 2 < len(self.tokens) and self.tokens[self.token_idx + 2].value == 'record':
                    return self.parse_record_definition()
            if self.current_token.value == 'yield': return self.parse_yield_statement()
            if self.current_token.value == 'import': return self.parse_import_statement()
            if self.current_token.value == 'from': return self.parse_from_import_statement()
            if self.current_token.value == 'export': return self.parse_export_statement()
        
        # If it's not a keyword-based statement, it must be an expression statement (like a function call).
        expr = self.parse_expression()
        self.skip_eols()  # Skip any EOL tokens before the period
        self.consume(TT_PUNCTUATION, '.')
        
        if isinstance(expr, FuncCallNode):
            return expr
        if isinstance(expr, (VarAccessNode, MemberAccessNode)):
            return FuncCallNode(expr, [])
        
        raise SyntaxError(f"Invalid statement. Standalone expressions like '{expr}' are not allowed.")

    # --- Statement Parsers ---

    def parse_set_statement(self):
        self.consume(TT_KEYWORD, 'set')
        # Parse the full target expression, which may include index access
        target_node = self.parse_expression()
        if not isinstance(target_node, (VarAccessNode, MemberAccessNode, IndexAccessNode)):
            raise SyntaxError("Invalid target for 'set' statement. Must be a variable, member, or indexed element.")
        self.consume(TT_KEYWORD, 'to')
        value_node = self.parse_expression()
        self.skip_eols()  # Skip any EOL tokens before the period
        self.consume(TT_PUNCTUATION, '.')
        
        # If it's an index access, create an IndexAssignNode instead of SetNode
        if isinstance(target_node, IndexAccessNode):
            return IndexAssignNode(target_node.object_node, target_node.index_node, value_node)
        else:
            return SetNode(target_node, value_node)

    def parse_record_definition(self):
        # Support both syntaxes: "to define RecordName:" and "define a record named RecordName:"
        if self.current_token.value == 'to':
            self.consume(TT_KEYWORD, 'to')
            self.consume(TT_KEYWORD, 'define')
            name_token = self.parse_name_token()
        else:
            self.consume(TT_KEYWORD, 'define'); self.consume(TT_KEYWORD, 'a'); self.consume(TT_KEYWORD, 'record'); self.consume(TT_KEYWORD, 'named')
            name_token = self.parse_name_token()
        self.consume(TT_PUNCTUATION, ':')
        members = self.parse_record_members(['end'])
        self.consume(TT_KEYWORD, 'end')
        return RecordDefNode(name_token, members)

    def parse_record_members(self, end_keywords):
        """Parse record members, including property definitions."""
        members = []
        self.skip_eols()
        while self.current_token and self.current_token.type != TT_EOF and \
              not (self.current_token.type == TT_KEYWORD and self.current_token.value in end_keywords):
            if self.current_token.type == TT_KEYWORD and self.current_token.value == 'property':
                members.append(self.parse_property_definition())
            else:
                members.append(self.parse_statement())
            self.skip_eols()
        return members

    def parse_property_definition(self):
        if not self.safe_consume(TT_KEYWORD, 'property'):
            return None
        
        try:
            name_token = self.parse_name_token()
        except SyntaxError:
            name_token = Token(TT_IDENTIFIER, "<error_property>", 0, 0)
        
        default_value = None
        # Support both "property name be value" and "property name with value"
        if (self.current_token and 
            self.current_token.type == TT_KEYWORD and 
            self.current_token.value in ('be', 'with')):
            self.advance()
            
            # Check if there's actually a value to parse
            if (self.current_token and 
                self.current_token.type not in (TT_EOL, TT_EOF) and
                not (self.current_token.type == TT_KEYWORD and self.current_token.value == 'end') and
                not (self.current_token.type == TT_PUNCTUATION and self.current_token.value == '.')):
                try:
                    default_value = self.parse_expression()
                except SyntaxError:
                    # Use a placeholder default value
                    default_value = StringNode(Token(TT_STRING, "", 0, 0))
            else:
                # No value provided after 'with' or 'be', use empty string as default
                default_value = StringNode(Token(TT_STRING, "", 0, 0))
        
        self.skip_eols()
        if not self.safe_consume(TT_PUNCTUATION, '.'):
            # Period is important but continue anyway
            pass
        
        return PropertyDefNode(name_token, default_value)

    def parse_fiber_definition(self):
        self.consume(TT_KEYWORD, 'define'); self.consume(TT_KEYWORD, 'a'); self.consume(TT_KEYWORD, 'fiber'); self.consume(TT_KEYWORD, 'named')
        name_token = self.parse_name_token()
        self.consume(TT_PUNCTUATION, ':')
        body = self.parse_statement_list(['end'])
        self.consume(TT_KEYWORD, 'end')
        return FiberDefNode(name_token, body)

    def parse_yield_statement(self):
        self.consume(TT_KEYWORD, 'yield')
        value_node = self.parse_expression() if self.current_token.value != '.' else None
        self.skip_eols()  # Skip any EOL tokens before the period
        self.consume(TT_PUNCTUATION, '.')
        return YieldNode(value_node)

    def parse_import_statement(self):
        """Parse import statement: import "module" as alias"""
        self.consume(TT_KEYWORD, 'import')
        
        # Expect a string literal for the module name
        if self.current_token.type != TT_STRING:
            raise SyntaxError(f"Expected string literal for module name, got {self.current_token.type}")
        
        module_name_token = self.current_token
        self.advance()
        
        alias_token = None
        # Check for optional "as alias"
        if (self.current_token and 
            self.current_token.type == TT_KEYWORD and 
            self.current_token.value == 'as'):
            self.consume(TT_KEYWORD, 'as')
            
            if self.current_token.type != TT_IDENTIFIER:
                raise SyntaxError(f"Expected identifier for import alias, got {self.current_token.type}")
            
            alias_token = self.current_token
            self.advance()
        
        self.skip_eols()  # Skip any EOL tokens before the period
        self.consume(TT_PUNCTUATION, '.')
        return ImportNode(module_name_token, alias_token)

    def parse_from_import_statement(self):
        """Parse from import statement: from "module" import function1, function2"""
        self.consume(TT_KEYWORD, 'from')
        
        # Expect a string literal for the module name
        if self.current_token.type != TT_STRING:
            raise SyntaxError(f"Expected string literal for module name, got {self.current_token.type}")
        
        module_name_token = self.current_token
        self.advance()
        
        self.consume(TT_KEYWORD, 'import')
        
        # Parse the list of names to import
        import_names = []
        
        while True:
            if self.current_token.type != TT_IDENTIFIER:
                raise SyntaxError(f"Expected identifier for import name, got {self.current_token.type}")
            
            name_token = self.current_token
            self.advance()
            
            alias_token = None
            # Check for optional "as alias"
            if (self.current_token and 
                self.current_token.type == TT_KEYWORD and 
                self.current_token.value == 'as'):
                self.consume(TT_KEYWORD, 'as')
                
                if self.current_token.type != TT_IDENTIFIER:
                    raise SyntaxError(f"Expected identifier for import alias, got {self.current_token.type}")
                
                alias_token = self.current_token
                self.advance()
            
            import_names.append((name_token, alias_token))
            
            # Check for comma to continue or period to end
            if (self.current_token and 
                self.current_token.type == TT_PUNCTUATION and 
                self.current_token.value == ','):
                self.advance()  # consume comma
                continue
            else:
                break
        
        self.skip_eols()  # Skip any EOL tokens before the period
        self.consume(TT_PUNCTUATION, '.')
        return FromImportNode(module_name_token, import_names)

    def parse_export_statement(self):
        """Parse export statement: export let variable or to export function"""
        self.consume(TT_KEYWORD, 'export')
        
        # Check what follows the export keyword
        if (self.current_token and 
            self.current_token.type == TT_KEYWORD and 
            self.current_token.value == 'let'):
            # Export variable: export let variable be value
            return self.parse_export_variable()
        elif (self.current_token and 
              self.current_token.type == TT_KEYWORD and 
              self.current_token.value == 'to'):
            # Export function: to export function_name with params:
            return self.parse_export_function()
        else:
            raise SyntaxError(f"Expected 'let' or 'to' after 'export', got {self.current_token.type} '{self.current_token.value}'")

    def parse_export_variable(self):
        """Parse export variable statement: export let variable be value"""
        self.consume(TT_KEYWORD, 'let')
        
        name_token = self.parse_name_token()
        self.consume(TT_KEYWORD, 'be')
        value_node = self.parse_expression()
        
        self.skip_eols()  # Skip any EOL tokens before the period
        self.consume(TT_PUNCTUATION, '.')
        return ExportVarNode(name_token, value_node)

    def parse_export_function(self):
        """Parse export function statement: to export function_name with params:"""
        self.consume(TT_KEYWORD, 'to')
        self.consume(TT_KEYWORD, 'export')
        
        name_token = self.parse_name_token()
        
        # Parse parameters (same logic as regular function definition)
        param_tokens = []
        if (self.current_token and 
            self.current_token.type == TT_KEYWORD and 
            self.current_token.value == 'with'):
            self.advance()
            while self.current_token and self.is_name_token(self.current_token):
                try:
                    param_tokens.append(self.parse_name_token())
                except SyntaxError:
                    # Skip invalid parameter and continue
                    self.advance()
                    continue
                
                if (self.current_token and 
                    self.current_token.type == TT_PUNCTUATION and 
                    self.current_token.value == ','):
                    self.advance()
                else:
                    break
        
        self.consume(TT_PUNCTUATION, ':')
        body_nodes = self.parse_statement_list(['end'])
        self.consume(TT_KEYWORD, 'end')
        
        return ExportFuncNode(name_token, param_tokens, body_nodes)

    def parse_task_statement(self):
        self.consume(TT_KEYWORD, 'run'); self.consume(TT_KEYWORD, 'concurrently'); self.consume(TT_PUNCTUATION, ':')
        body = self.parse_statement_list(['end'])
        self.consume(TT_KEYWORD, 'end')
        return TaskNode(body)

    def parse_channel_statement(self):
        self.consume(TT_KEYWORD, 'create'); self.consume(TT_KEYWORD, 'a'); self.consume(TT_KEYWORD, 'channel'); self.consume(TT_KEYWORD, 'named')
        name_token = self.parse_name_token()
        self.skip_eols()  # Skip any EOL tokens before the period
        self.consume(TT_PUNCTUATION, '.')
        return ChannelNode(name_token)

    def parse_send_statement(self):
        self.consume(TT_KEYWORD, 'send')
        value_node = self.parse_expression()
        self.consume(TT_KEYWORD, 'through')
        channel_node = self.parse_name_token()
        self.skip_eols()  # Skip any EOL tokens before the period
        self.consume(TT_PUNCTUATION, '.')
        return SendNode(value_node, VarAccessNode(channel_node))

    def parse_return_statement(self):
        self.consume(TT_KEYWORD, 'return')
        
        # Validate that we have a valid expression after 'return'
        self.validate_expression_context("return value")
        expr = self.parse_expression()
        
        self.skip_eols()  # Skip any EOL tokens before the period
        self.consume(TT_PUNCTUATION, '.')
        return ReturnNode(expr)

    def parse_while_statement(self):
        self.consume(TT_KEYWORD, 'while')
        condition = self.parse_expression()
        if self.current_token.type == TT_PUNCTUATION and self.current_token.value == ':':
            self.advance()
        self.skip_eols()
        body = self.parse_statement_list(['end'])
        self.consume(TT_KEYWORD, 'end')
        return WhileNode(condition, body)

    def parse_if_statement(self):
        cases = []
        else_case = None
        
        if not self.safe_consume(TT_KEYWORD, 'if'):
            return None
        
        # Parse the initial condition
        try:
            condition = self.parse_expression()
        except SyntaxError:
            # Use a placeholder condition
            condition = NumberNode(Token(TT_NUMBER, 1, 0, 0))  # Default to true
        
        self.skip_eols()  # Skip any EOL tokens before 'then'
        if not self.safe_consume(TT_KEYWORD, 'then'):
            # 'then' is important but try to continue
            pass
        
        self.skip_eols()
        statements = self.parse_statement_list(['otherwise', 'end'])
        cases.append((condition, statements))
        
        # Handle otherwise clauses
        while (self.current_token and 
               self.current_token.type == TT_KEYWORD and 
               self.current_token.value == 'otherwise'):
            self.advance()
            if (self.current_token and 
                self.current_token.type == TT_KEYWORD and 
                self.current_token.value == 'if'):
                self.advance()
                try:
                    condition = self.parse_expression()
                except SyntaxError:
                    condition = NumberNode(Token(TT_NUMBER, 1, 0, 0))
                
                self.skip_eols()  # Skip any EOL tokens before 'then'
                if not self.safe_consume(TT_KEYWORD, 'then'):
                    pass
                
                self.skip_eols()
                statements = self.parse_statement_list(['otherwise', 'end'])
                cases.append((condition, statements))
            else:
                self.skip_eols()
                else_case = self.parse_statement_list(['end'])
                break
        
        if not self.safe_consume(TT_KEYWORD, 'end'):
            # Missing 'end' is serious but we can still return the if statement
            pass
        
        return IfNode(cases, else_case)

    def parse_function_definition(self):
        if not self.safe_consume(TT_KEYWORD, 'to'):
            return None
        
        try:
            name_token = self.parse_name_token()
        except SyntaxError:
            # Use placeholder name if parsing fails
            name_token = Token(TT_IDENTIFIER, "<error_function>", 0, 0)
        
        params = []
        if self.current_token and self.current_token.type == TT_KEYWORD and self.current_token.value == 'with':
            self.advance()
            while self.current_token and self.is_name_token(self.current_token):
                try:
                    params.append(self.parse_name_token())
                except SyntaxError:
                    # Skip invalid parameter and continue
                    self.advance()
                    continue
                
                if (self.current_token and 
                    self.current_token.type == TT_PUNCTUATION and 
                    self.current_token.value == ','):
                    self.advance()
                else:
                    break
        
        if not self.safe_consume(TT_PUNCTUATION, ':'):
            # Colon is important but try to continue
            pass
        
        self.skip_eols()
        body = self.parse_statement_list(['end'])
        
        if not self.safe_consume(TT_KEYWORD, 'end'):
            # Missing 'end' is a serious error, but we can still return the function
            pass
        
        return FuncDefNode(name_token, params, body)

    def parse_variable_assignment(self):
        if not self.safe_consume(TT_KEYWORD, 'let'):
            return None
        
        try:
            name_token = self.parse_name_token()
            # Track the variable for better error suggestions
            self.track_variable(name_token.value)
        except SyntaxError:
            # If we can't parse the name, try to recover
            name_token = Token(TT_IDENTIFIER, "<error>", 0, 0)
        
        if not self.safe_consume(TT_KEYWORD, 'be'):
            # Try to recover by looking for an expression
            pass
        
        # Try to parse the value expression
        value_node = None
        try:
            self.validate_expression_context("variable assignment value")
            value_node = self.parse_expression()
        except SyntaxError:
            # Create a placeholder value node
            value_node = NumberNode(Token(TT_NUMBER, 0, 0, 0))
        
        self.skip_eols()  # Skip any EOL tokens before the period
        if not self.safe_consume(TT_PUNCTUATION, '.'):
            # Period is critical for statement termination, but continue anyway
            pass
            
        return VarAssignNode(name_token, value_node)

    # --- Expression Parser (Pratt Parser) ---

    def get_precedence(self, token):
        if not token: return 0
        # EOL tokens should have the lowest precedence to terminate expressions
        if token.type == TT_EOL: return -1
        if token.value == 'with': return 7
        if token.type == TT_PUNCTUATION and token.value == '.':
            # Only give high precedence to '.' if it's followed by a member name
            next_token = self.peek_token()
            if next_token and self.is_name_token(next_token):
                return 8  # Member access
            else:
                return 0  # Statement terminator or function call - don't continue expression
        if token.type == TT_PUNCTUATION and token.value == '[': return 9  # High precedence for indexing
        if token.type != TT_OPERATOR: return 0
        op = token.value
        if op in ('or', 'or return error'): return 1
        if op in ('and'): return 2
        if op in ('is', 'is not', 'is greater than', 'is less than', 'is an'): return 3
        if op in ('plus', 'minus', 'concatenated with'): return 4
        if op in ('times', 'divided by'): return 5
        return 0
    
    def is_name_token(self, token):
        RESERVED_KEYWORDS = [
            'if', 'then', 'otherwise', 'end', 'let', 'be', 'to', 'with', 'return',
            'while', 'for', 'repeat', 'and', 'or', 'not',
            'run', 'send', 'create', 'define', 'yield', 'new', 'set'
        ]
        if token.type == TT_IDENTIFIER:
            return True
        if token.type == TT_KEYWORD and token.value not in RESERVED_KEYWORDS:
            return True
        return False

    def is_valid_expression_token(self, token):
        """Check if a token can continue an expression.
        
        Returns True if the token can be part of an ongoing expression,
        False if it should terminate expression parsing.
        """
        if not token:
            return False
            
        # EOL and EOF tokens always terminate expressions
        if token.type in (TT_EOL, TT_EOF):
            return False
            
        # Note: We don't treat '.' as invalid here because it can be used for member access
        # Statement termination is handled at a higher level
            
        # Block terminators that should end expressions
        if token.type == TT_KEYWORD and token.value in ['then', 'otherwise', 'end', ':']:
            return False
            
        # Keywords that start new statements should terminate expressions
        if token.type == TT_KEYWORD and token.value in ['let', 'set', 'if', 'while', 'return', 'to']:
            return False
            
        return True

    def safe_token_check(self, token, expected_type, expected_value=None):
        """Safely check token properties without causing errors.
        
        Args:
            token: Token to check (can be None)
            expected_type: Expected token type
            expected_value: Expected token value (optional)
            
        Returns:
            bool: True if token matches expectations, False otherwise
        """
        if not token:
            return False
            
        # Check if token has required attributes
        if not hasattr(token, 'type') or not hasattr(token, 'value'):
            return False
            
        if token.type != expected_type:
            return False
            
        if expected_value is not None and token.value != expected_value:
            return False
            
        return True
    
    def is_valid_token_index(self, index):
        """Check if the given index is valid for the tokens list.
        
        Args:
            index: Token index to check
            
        Returns:
            bool: True if index is valid, False otherwise
        """
        return 0 <= index < len(self.tokens)
    
    def has_errors(self):
        """Check if any parsing errors were encountered."""
        return self.error_aggregator.has_errors()
    
    def get_errors(self):
        """Get all parsing errors that were encountered."""
        return self.error_aggregator.errors
    
    def get_error_report(self):
        """Get a formatted report of all parsing errors."""
        return self.error_aggregator.format_all_errors()
    
    def clear_errors(self):
        """Clear all accumulated errors."""
        self.error_aggregator.clear()
    
    def track_variable(self, var_name):
        """Track a variable name for better error suggestions."""
        self.available_variables.add(var_name)
    
    def has_errors(self):
        """Check if any errors have been collected during parsing."""
        return self.error_aggregator.has_errors()
    
    def get_error_report(self):
        """Get a formatted report of all parsing errors."""
        return self.error_aggregator.format_all_errors()
    
    def enter_recovery_mode(self):
        """Enter error recovery mode to continue parsing after errors."""
        self.recovery_mode = True
    
    def exit_recovery_mode(self):
        """Exit error recovery mode when parsing can continue normally."""
        self.recovery_mode = False
    
    def recover_to_statement_boundary(self):
        """
        Recover to the next statement boundary after a syntax error.
        Advances tokens until we find a likely statement start or end.
        """
        recovery_count = 0
        max_recovery_tokens = 50  # Prevent infinite loops
        
        while (self.current_token and 
               self.current_token.type != TT_EOF and 
               recovery_count < max_recovery_tokens):
            
            # Look for statement boundaries
            if (self.current_token.type == TT_PUNCTUATION and 
                self.current_token.value == '.'):
                # Found end of statement, advance past it
                self.advance()
                self.skip_eols()
                break
            
            # Look for statement keywords that indicate new statements
            if (self.current_token.type == TT_KEYWORD and 
                self.current_token.value in self.statement_keywords):
                # Found start of new statement
                break
            
            # Look for block end keywords
            if (self.current_token.type == TT_KEYWORD and 
                self.current_token.value == 'end'):
                # Found block end, don't consume it
                break
            
            # Skip EOL tokens during recovery
            if self.current_token.type == TT_EOL:
                self.advance()
                continue
            
            self.advance()
            recovery_count += 1
        
        # If we hit the recovery limit, we might be in an infinite loop
        if recovery_count >= max_recovery_tokens:
            # Force advance to EOF to prevent infinite loops
            while self.current_token and self.current_token.type != TT_EOF:
                self.advance()
    
    def recover_to_block_boundary(self):
        """
        Recover to the next block boundary (end keyword or EOF).
        Used when parsing block structures like if/while/function definitions.
        """
        recovery_count = 0
        max_recovery_tokens = 100  # Allow more tokens for block recovery
        
        while (self.current_token and 
               self.current_token.type != TT_EOF and 
               recovery_count < max_recovery_tokens):
            
            # Look for block end keyword
            if (self.current_token.type == TT_KEYWORD and 
                self.current_token.value == 'end'):
                break
            
            # Skip EOL tokens during recovery
            if self.current_token.type == TT_EOL:
                self.advance()
                continue
            
            self.advance()
            recovery_count += 1
        
        # If we hit the recovery limit, force to EOF
        if recovery_count >= max_recovery_tokens:
            while self.current_token and self.current_token.type != TT_EOF:
                self.advance()
    
    def safe_consume(self, expected_type, expected_value=None):
        """
        Safely consume a token with error recovery.
        Records the error but continues parsing instead of raising an exception.
        
        Returns:
            bool: True if token was consumed successfully, False if error occurred
        """
        if (self.current_token and 
            self.current_token.type == expected_type and 
            (expected_value is None or self.current_token.value == expected_value)):
            self.advance()
            return True
        else:
            # Create enhanced error with context and suggestions
            error_msg = self.create_context_aware_error_message(expected_type, expected_value)
            error = create_syntax_error(
                message=error_msg,
                line=self.current_token.line if self.current_token else 1,
                column=self.current_token.column if self.current_token else 1,
                file_path=self.file_path
            )
            
            # Add specific suggestions based on the error context
            self.add_consume_error_suggestions(error, expected_type, expected_value)
            
            self.error_aggregator.add_error(error)
            self.enter_recovery_mode()
            return False
    
    def create_name_error_with_suggestions(self, undefined_name, line, column):
        """Create a name error with variable suggestions."""
        from engage_errors import create_name_error
        return create_name_error(
            message=f"'{undefined_name}' is not defined",
            line=line,
            column=column,
            file_path=self.file_path,
            undefined_name=undefined_name,
            available_names=list(self.available_variables)
        )
    
    def peek_token(self, offset=1):
        """Safely peek at a token at the given offset from current position.
        
        Args:
            offset: Number of positions ahead to look (default: 1)
            
        Returns:
            Token or None: The token at the offset position, or None if invalid
        """
        peek_index = self.token_idx + offset
        if self.is_valid_token_index(peek_index):
            return self.tokens[peek_index]
        return None
    
    def has_more_tokens(self):
        """Check if there are more tokens available to parse.
        
        Returns:
            bool: True if more tokens are available, False otherwise
        """
        return (self.current_token is not None and 
                self.current_token.type != TT_EOF and
                self.token_idx < len(self.tokens) - 1)

    def parse_name_token(self):
        token = self.current_token
        if self.is_name_token(token):
            self.advance()
            return token
        raise SyntaxError(f"Expected a valid name but got {token.type}('{token.value}')")

    def parse_atom(self):
        token = self.current_token
        
        # Handle EOL tokens in expressions with user-friendly error
        if token.type == TT_EOL:
            raise SyntaxError("Unexpected end of line while parsing expression. "
                            "Expected a value, variable, or expression.")
        
        # Handle EOF tokens in expressions with user-friendly error
        if token.type == TT_EOF:
            raise SyntaxError("Unexpected end of file while parsing expression. "
                            "Expected a value, variable, or expression.")
        
        if token.type == TT_NUMBER: self.advance(); return NumberNode(token)
        if token.type == TT_STRING: self.advance(); return StringNode(token)
        if token.type == TT_KEYWORD and token.value == 'receive':
            self.advance(); self.consume(TT_KEYWORD, 'from')
            channel_node = self.parse_name_token()
            return ReceiveNode(VarAccessNode(channel_node))
        if token.type == TT_KEYWORD and token.value == 'new': return self.parse_new_instance()
        if token.type == TT_KEYWORD and token.value == 'Table': self.advance(); return TableNode()
        if token.type == TT_KEYWORD and token.value == 'Vector': self.advance(); return VectorNode()
        if token.type == TT_KEYWORD and token.value == 'Record': return self.parse_record_constructor()
        if token.type == TT_KEYWORD and token.value == 'self': self.advance(); return SelfNode()
        if token.type == TT_KEYWORD and token.value in ('Ok', 'Error'): return self.parse_result_constructor()

        if self.is_name_token(token) or token.value == 'print':
            self.advance()
            return VarAccessNode(token)
            
        if token.value == '(':
            self.advance(); expr = self.parse_expression(); self.consume(TT_PUNCTUATION, ')')
            return expr
        if token.type == TT_OPERATOR and token.value in ('not', 'call', 'the ok value of', 'the error message of'):
            self.advance(); return UnaryOpNode(token, self.parse_expression(7))
        
        # Provide user-friendly error message for unexpected tokens
        if token.type == TT_KEYWORD:
            raise SyntaxError(f"Unexpected keyword '{token.value}' in expression. "
                            "Expected a value, variable, or expression.")
        elif token.type == TT_PUNCTUATION:
            raise SyntaxError(f"Unexpected punctuation '{token.value}' in expression. "
                            "Expected a value, variable, or expression.")
        else:
            raise SyntaxError(f"Unexpected {token.type.lower()} '{token.value}' in expression. "
                            "Expected a value, variable, or expression.")

    def parse_new_instance(self):
        self.consume(TT_KEYWORD, 'new')
        name_token = self.parse_name_token()
        properties = {}
        if self.current_token.value == 'with':
            self.advance()
            while self.current_token.type != TT_EOF and self.current_token.value != '.':
                prop_name = self.parse_name_token()
                # Handle both "prop value" and "prop: value" syntax
                if self.current_token.type == TT_PUNCTUATION and self.current_token.value == ':':
                    self.advance()  # consume the colon
                prop_value = self.parse_expression()
                properties[prop_name.value] = prop_value
                if self.current_token.value == ',': self.advance()
                else: break
        return NewInstanceNode(name_token, properties)
    
    def parse_result_constructor(self):
        type_token = self.current_token  # 'Ok' or 'Error'
        self.advance()
        if self.current_token.value == 'with':
            self.advance()
            value_node = self.parse_expression()
            return ResultNode(type_token, value_node)
        else:
            # No 'with' clause, so it's just the type without a value
            return ResultNode(type_token, None)

    def parse_record_constructor(self):
        self.consume(TT_KEYWORD, 'Record')
        name_token = self.parse_name_token()
        return RecordNode(name_token)
    
    def parse_function_call(self, node_to_call):
        self.consume(TT_KEYWORD, 'with')
        arg_nodes = []
        
        # Check if we have valid tokens for arguments (not EOL, EOF, or statement terminators)
        if self.current_token and self.is_valid_expression_token(self.current_token):
            while self.is_valid_expression_token(self.current_token):
                # Parse the argument expression with precedence 2 to prevent 'or return error' (precedence 1) 
                # from being consumed as part of the argument
                # Pass context that we're parsing function arguments
                arg_nodes.append(self.parse_expression(2, in_function_args=True))
                
                # After parsing an argument, check for EOL tokens which should terminate argument parsing
                if self.current_token and self.current_token.type == TT_EOL:
                    # EOL token terminates argument parsing per Requirement 2.4
                    break
                
                # Check for comma to continue with next argument
                if self.current_token and self.current_token.type == TT_PUNCTUATION and self.current_token.value == ',':
                    self.advance()
                    # After comma, check if next token is valid for continuing arguments
                    # If we encounter EOL after comma, we should also terminate
                    if not self.current_token or not self.is_valid_expression_token(self.current_token):
                        break
                else:
                    # No comma found, end of arguments
                    break
                    
        return FuncCallNode(node_to_call, arg_nodes)

    def parse_expression(self, precedence=0, in_function_args=False):
        left = self.parse_atom()
        
        # Main expression parsing loop with proper EOL handling
        while True:
            # Skip any EOL tokens before checking for operators
            if self.current_token and self.current_token.type == TT_EOL:
                # Look ahead to see if there's a valid operator after the EOL tokens
                saved_pos = self.token_idx
                self.skip_eols()
                
                # Check if we have a valid operator after EOL tokens
                if (self.current_token and 
                    self.current_token.type != TT_EOF and
                    self.is_valid_expression_token(self.current_token) and 
                    precedence < self.get_precedence(self.current_token)):
                    # Continue parsing with the operator after EOL
                    pass
                else:
                    # No valid operator after EOL, restore position and terminate expression
                    self.token_idx = saved_pos
                    self.current_token = self.tokens[self.token_idx] if self.token_idx < len(self.tokens) else None
                    break
            
            # Check standard termination conditions
            if (not self.current_token or 
                self.current_token.type == TT_EOF or
                not self.is_valid_expression_token(self.current_token) or 
                precedence >= self.get_precedence(self.current_token)):
                break
                
            if self.current_token.value == '.':
                # Check if this is member access, function call, or statement termination
                next_token = self.peek_token()
                if next_token and self.is_name_token(next_token):
                    # This is member access: obj.member
                    self.advance()
                    member_token = self.parse_name_token()
                    left = MemberAccessNode(left, member_token)
                    continue
                elif isinstance(left, VarAccessNode):
                    # This could be a function call with no arguments: func.
                    # We need to check if we're at the end of an expression context
                    # Look ahead to see what comes after the period
                    if (not next_token or 
                        next_token.type in (TT_EOF, TT_EOL) or
                        next_token.type == TT_KEYWORD and next_token.value in ['then', 'otherwise', 'end']):
                        # If we're parsing function arguments, don't treat period as function call
                        # The period is likely the statement terminator
                        if in_function_args:
                            break  # End expression parsing, don't convert to function call
                        else:
                            # This looks like a function call with no arguments
                            left = FuncCallNode(left, [])
                            # Don't consume the period here - let the statement parser handle it
                            break  # End expression parsing
                    else:
                        # This is a statement terminator in a larger context
                        break
                else:
                    # This is a statement terminator, not member access
                    break
            
            if self.current_token.value == '[':
                # Handle index access
                self.advance()  # consume '['
                index_node = self.parse_expression()
                self.consume(TT_PUNCTUATION, ']')
                left = IndexAccessNode(left, index_node)
                continue
            
            if self.current_token.value == 'with':
                left = self.parse_function_call(left)
                continue

            # Handle 'or return error' as a special postfix operator
            if self.current_token.value == 'or return error':
                op_token = self.current_token
                self.advance()
                # Create a binary operation with a dummy right operand
                # The VM will handle this specially and not evaluate the right side
                dummy_right = VarAccessNode(Token('IDENTIFIER', 'error', op_token.line, op_token.column))
                left = BinOpNode(left, op_token, dummy_right)
                continue

            op_token = self.current_token
            self.advance()
            
            # Skip EOL tokens after operator before parsing right operand
            self.skip_eols()
            
            # Special handling for 'is an' operator with type names
            if op_token.value == 'is an':
                # Check if the right operand is a type name (Error or Ok)
                if (self.current_token and 
                    self.current_token.type == TT_KEYWORD and 
                    self.current_token.value in ('Error', 'Ok')):
                    # Create a TypeNameNode instead of parsing as a variable
                    type_token = self.current_token
                    self.advance()
                    right = TypeNameNode(type_token)
                else:
                    # Parse normally for other cases
                    right = self.parse_expression(self.get_precedence(op_token), in_function_args)
            else:
                right = self.parse_expression(self.get_precedence(op_token), in_function_args)
            
            left = BinOpNode(left, op_token, right)
        
        return left
