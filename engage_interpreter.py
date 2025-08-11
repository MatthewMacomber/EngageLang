# engage_interpreter.py
import sys
import threading
import queue

# This code assumes the Lexer and Parser from the previous artifacts are in files
# named 'engage_lexer.py' and 'engage_parser.py'.
from engage_lexer import Lexer
from engage_parser import Parser, ASTNode, ProgramNode, VarAssignNode, SetNode, VarAccessNode, BinOpNode, NumberNode, StringNode, FuncDefNode, FuncCallNode, ReturnNode, IfNode, UnaryOpNode, WhileNode, TaskNode, ChannelNode, SendNode, ReceiveNode, FiberDefNode, YieldNode, RecordDefNode, NewInstanceNode, MemberAccessNode, SelfNode, TypeNameNode, TableNode, VectorNode, IndexAccessNode, IndexAssignNode, PropertyDefNode, ImportNode, FromImportNode, ExportVarNode, ExportFuncNode
from engage_errors import EngageError, ErrorAggregator, create_runtime_error, create_type_error, create_name_error, EngageRuntimeError
from engage_modules import get_module_system, ModuleNotFoundError, CircularDependencyError

# Import the core value classes
from engage_values import Value, Number, String, NoneValue, Function, BuiltInFunction, Channel, Fiber, Record, RecordInstance, BoundMethod, ResultValue, Table, Vector, ModuleValue, SymbolTable


# Import standard library system
from engage_stdlib import get_standard_library
from stdlib_strings import StringsModule
from stdlib_math import MathModule
from stdlib_files import FilesModule
from stdlib_collections import CollectionsModule
from stdlib_types import TypesModule

# Import UI and Game systems
try:
    from engage_ui_components import ui_manager, UI_BUILTIN_FUNCTIONS
    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False
    ui_manager = None
    UI_BUILTIN_FUNCTIONS = {}

try:
    from engage_game_objects import game_manager, GAME_BUILTIN_FUNCTIONS
    GAME_AVAILABLE = True
except ImportError:
    GAME_AVAILABLE = False
    game_manager = None
    GAME_BUILTIN_FUNCTIONS = {}

# --- Call Stack Frame for Stack Traces ---

class CallFrame:
    """Represents a single frame in the call stack for stack trace generation."""

    def __init__(self, function_name, line=None, column=None, file_path=None, local_vars=None, context=None):
        self.function_name = function_name
        self.line = line
        self.column = column
        self.file_path = file_path
        self.local_vars = local_vars or {}
        self.context = context  # Reference to the symbol table context
        self.call_site_line = None  # Line where this function was called from
        self.call_site_column = None  # Column where this function was called from

    def update_location(self, line, column):
        """Update the current execution location within this frame."""
        self.line = line
        self.column = column

    def set_call_site(self, line, column):
        """Set the location where this function was called from."""
        self.call_site_line = line
        self.call_site_column = column

    def get_local_variables_snapshot(self):
        """Get a snapshot of current local variables."""
        if self.context:
            snapshot = {}
            for name, value in self.context.symbols.items():
                try:
                    # Convert value to string representation for display
                    if hasattr(value, 'value'):
                        snapshot[name] = str(value.value)
                    else:
                        snapshot[name] = str(value)
                except:
                    snapshot[name] = "<unprintable>"
            return snapshot
        return self.local_vars

    def format_frame(self, show_locals=False):
        """Format this frame as a string with optional local variables."""
        lines = []

        # Main frame line
        location = ""
        if self.file_path:
            location += f" in {self.file_path}"
        if self.line:
            location += f" at line {self.line}"
        if self.column:
            location += f", column {self.column}"

        frame_line = f"  {self.function_name}(){location}"
        lines.append(frame_line)

        # Show local variables if requested
        if show_locals:
            local_vars = self.get_local_variables_snapshot()
            if local_vars:
                lines.append("    Local variables:")
                for name, value in local_vars.items():
                    lines.append(f"      {name} = {value}")

        return "\n".join(lines)

    def __repr__(self):
        return self.format_frame(show_locals=False)

class StackTrace:
    """Enhanced stack trace management for generating detailed error reports."""

    def __init__(self):
        self.frames = []
        self.max_frames = 50  # Prevent infinite recursion in stack traces

    def push_frame(self, function_name, line=None, column=None, file_path=None, local_vars=None, context=None):
        """Push a new frame onto the call stack."""
        if len(self.frames) >= self.max_frames:
            # Prevent stack overflow in error reporting
            return None

        frame = CallFrame(function_name, line, column, file_path, local_vars, context)
        self.frames.append(frame)
        return frame

    def pop_frame(self):
        """Pop the top frame from the call stack."""
        if self.frames:
            return self.frames.pop()
        return None

    def get_current_frame(self):
        """Get the current (top) frame without removing it."""
        return self.frames[-1] if self.frames else None

    def update_current_location(self, line, column):
        """Update the current execution location in the top frame."""
        if self.frames:
            self.frames[-1].update_location(line, column)

    def get_depth(self):
        """Get the current call stack depth."""
        return len(self.frames)

    def format_stack_trace(self, show_locals=False, max_frames=None):
        """Format the stack trace as a comprehensive string."""
        if not self.frames:
            return "No stack trace available"

        lines = ["Stack trace (most recent call last):"]

        # Determine how many frames to show
        frames_to_show = self.frames
        if max_frames and len(self.frames) > max_frames:
            # Show first few and last few frames with ellipsis in between
            first_frames = self.frames[:max_frames//2]
            last_frames = self.frames[-(max_frames//2):]
            frames_to_show = first_frames + [None] + last_frames  # None represents ellipsis

        for frame in frames_to_show:
            if frame is None:
                lines.append(f"  ... ({len(self.frames) - max_frames} more frames) ...")
            else:
                lines.append(frame.format_frame(show_locals))

        return "\n".join(lines)

    def format_compact_trace(self):
        """Format a compact version of the stack trace for inline error messages."""
        if not self.frames:
            return "at <unknown>"

        # Show just the most recent frame
        frame = self.frames[-1]
        location = f"at {frame.function_name}()"
        if frame.file_path:
            location += f" in {frame.file_path}"
        if frame.line:
            location += f":{frame.line}"

        return location

    def get_call_chain(self):
        """Get a list of function names in the call chain."""
        return [frame.function_name for frame in self.frames]

    def clear(self):
        """Clear the call stack."""
        self.frames.clear()

    def copy(self):
        """Create a copy of the current stack trace."""
        new_trace = StackTrace()
        new_trace.frames = self.frames.copy()
        return new_trace

# --- Interpreter ---

class Interpreter:
    def __init__(self, file_path=None):
        self.file_path = file_path
        self.stack_trace = StackTrace()
        self.error_aggregator = ErrorAggregator()
        self.current_exports = {}  # Track exports for module system

        # Initialize standard library
        self._initialize_standard_library()

    def visit(self, node, context):
        method_name = f'visit_{type(node).__name__}'
        method = getattr(self, method_name, self.no_visit_method)

        # Track current node for better error reporting
        current_line = getattr(node, 'line', None) or (getattr(node, 'token', None) and node.token.line)
        current_column = getattr(node, 'column', None) or (getattr(node, 'token', None) and node.token.column)

        # Update current location in stack trace if we have a frame
        if current_line and current_column:
            self.stack_trace.update_current_location(current_line, current_column)

        try:
            return method(node, context)
        except Exception as e:
            # Enhance runtime errors with location information and stack trace
            if not isinstance(e, EngageRuntimeError):
                # Determine error type based on exception type
                error_type = "Runtime Error"
                if isinstance(e, NameError):
                    error_type = "Name Error"
                elif isinstance(e, TypeError):
                    error_type = "Type Error"
                elif isinstance(e, ZeroDivisionError):
                    error_type = "Division Error"
                elif isinstance(e, AttributeError):
                    error_type = "Attribute Error"
                elif isinstance(e, IndexError):
                    error_type = "Index Error"

                enhanced_error = EngageRuntimeError(
                    message=str(e),
                    line=current_line,
                    column=current_column,
                    file_path=self.file_path,
                    stack_trace=self.stack_trace,
                    error_type=error_type
                )
                raise enhanced_error from e
            raise

    def no_visit_method(self, node, context):
        raise Exception(f'No visit_{type(node).__name__} method defined')

    def visit_ProgramNode(self, node, context):
        result = None
        error_count = 0
        max_errors = 10  # Limit runtime errors to prevent infinite loops

        for statement in node.statements:
            try:
                result = self.visit(statement, context)
                if isinstance(result, (ReturnValue, YieldValue)):
                    return result.value
            except EngageRuntimeError as e:
                error_count += 1

                # Print the error but continue execution
                print(f"\nRuntime Error {error_count}:")
                print(e.format_compact_error())
                print("Continuing execution...\n")

                # If we hit too many errors, stop execution
                if error_count >= max_errors:
                    print(f"Too many runtime errors ({max_errors}). Stopping execution.")
                    break

                # Continue with next statement
                continue
            except Exception as e:
                # Handle unexpected errors
                error_count += 1
                print(f"\nUnexpected Error {error_count}: {e}")
                print("Continuing execution...\n")

                if error_count >= max_errors:
                    print(f"Too many errors ({max_errors}). Stopping execution.")
                    break
                continue

        return result

    def _initialize_standard_library(self):
        """Initialize the standard library modules."""
        stdlib = get_standard_library()

        # Register all standard library modules
        stdlib.register_module('strings', StringsModule)
        stdlib.register_module('math', MathModule)
        stdlib.register_module('files', FilesModule)
        stdlib.register_module('collections', CollectionsModule)
        stdlib.register_module('types', TypesModule)

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
                raise NameError(f"Cannot 'set' variable '{var_name}' before it is declared with 'let'.")
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
        if value is None:
            # Create enhanced name error with suggestions
            available_vars = self.get_available_variables(context)
            error = create_name_error(
                message=f"'{var_name}' is not defined",
                line=node.name_token.line,
                column=node.name_token.column,
                file_path=self.file_path,
                undefined_name=var_name,
                available_names=available_vars
            )
            raise NameError(error.format_error())
        return value

    def get_available_variables(self, context):
        """Get list of available variable names in the current context."""
        variables = []
        current_context = context
        while current_context:
            variables.extend(current_context.symbols.keys())
            current_context = current_context.parent
        return list(set(variables))  # Remove duplicates

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
            if not isinstance(value, ResultValue):
                raise TypeError(f"Cannot extract 'ok value' from {type(value).__name__}. Expected a Result type.")
            if value.type != 'Ok':
                raise TypeError("Cannot extract 'ok value' from an Error result. Use 'the error message of' instead.")
            extracted = value.value if value.value is not None else NoneValue()
            return extracted
        if op == 'the error message of':
            if not isinstance(value, ResultValue):
                raise TypeError(f"Cannot extract 'error message' from {type(value).__name__}. Expected a Result type.")
            if value.type != 'Error':
                raise TypeError("Cannot extract 'error message' from an Ok result. Use 'the ok value of' instead.")
            return value.value if value.value is not None else NoneValue()
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

        # Special handling for MemberAccessNode in function call context
        if isinstance(node.node_to_call, MemberAccessNode):
            instance = self.visit(node.node_to_call.instance_node, context)
            member_name = node.node_to_call.member_token.value

            if isinstance(instance, RecordInstance):
                method = instance.record_class.methods.get(member_name)
                if method:
                    return self.execute_user_function(method, args, context, instance)
                else:
                    raise AttributeError(f"Record '{instance.record_class.name}' has no method '{member_name}'")

        callee = self.visit(node.node_to_call, context)
        if isinstance(callee, BoundMethod):
            return self.execute_user_function(callee.method, args, context, callee.instance)
        elif isinstance(callee, BuiltInFunction):
            return callee.func_ptr(args)
        elif isinstance(callee, Function):
            return self.execute_user_function(callee, args, context)
        else:
            raise TypeError(f"'{callee}' is not a function")

    def execute_user_function(self, func, args, context, instance=None):
        if len(args) != len(func.arg_names):
            raise TypeError(f"Function '{func.name}' takes {len(func.arg_names)} arguments but {len(args)} were given")

        # Create function context and local variables for stack trace
        func_context = SymbolTable(parent=context)
        local_vars = {}

        if instance:
            func_context.set("self", instance)
            local_vars["self"] = f"<instance of {instance.record_class.name}>"

        for i, arg_name in enumerate(func.arg_names):
            func_context.set(arg_name, args[i])
            # Store argument values for stack trace
            try:
                if hasattr(args[i], 'value'):
                    local_vars[arg_name] = str(args[i].value)
                else:
                    local_vars[arg_name] = str(args[i])
            except:
                local_vars[arg_name] = "<unprintable>"

        # Push function frame onto call stack with context reference
        frame = self.stack_trace.push_frame(
            function_name=func.name,
            file_path=self.file_path,
            local_vars=local_vars,
            context=func_context
        )

        if not frame:
            # Stack overflow protection
            raise RuntimeError("Maximum call stack depth exceeded")

        result = None
        try:
            for statement in func.body_node:
                # Update frame line information if available
                current_line = getattr(statement, 'line', None) or (getattr(statement, 'token', None) and statement.token.line)
                current_column = getattr(statement, 'column', None) or (getattr(statement, 'token', None) and statement.token.column)

                if current_line and current_column:
                    frame.update_location(current_line, current_column)

                result = self.visit(statement, func_context)
                if isinstance(result, ReturnValue):
                    self.stack_trace.pop_frame()
                    return result.value
        except ReturnException as e:
            # Handle early return from error propagation
            self.stack_trace.pop_frame()
            return e.value
        except Exception as e:
            # Don't pop frame here - let the error bubble up with stack trace intact
            # The frame will be included in the error report
            raise

        self.stack_trace.pop_frame()
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

    def visit_YieldNode(self, node, context):
        return YieldValue(self.visit(node.value_node, context) if node.value_node else Number(0))

    def visit_ImportNode(self, node, context):
        """Handle import statements."""
        module_name = node.module_name.value
        alias = node.alias.value if node.alias else None

        try:
            # Get the module system
            module_system = get_module_system()

            # Import the module
            exports = module_system.import_module(module_name, self.file_path, self)

            if alias:
                # Import as alias - create a module object
                module_obj = ModuleValue(module_name, exports)
                context.set(alias, module_obj)
            else:
                # Import all exports directly into current namespace
                for name, value in exports.items():
                    context.set(name, value)

            return NoneValue()

        except (ModuleNotFoundError, CircularDependencyError) as e:
            raise EngageRuntimeError(
                message=str(e),
                line=getattr(node, 'line', None),
                column=getattr(node, 'column', None),
                file_path=self.file_path,
                stack_trace=self.stack_trace,
                error_type="Import Error"
            )

    def visit_FromImportNode(self, node, context):
        """Handle from...import statements."""
        module_name = node.module_name.value

        try:
            # Get the module system
            module_system = get_module_system()

            # Import the module
            exports = module_system.import_module(module_name, self.file_path, self)

            # Import specific symbols
            for import_item in node.import_items:
                symbol_name = import_item.name.value
                alias = import_item.alias.value if import_item.alias else symbol_name

                if symbol_name in exports:
                    context.set(alias, exports[symbol_name])
                else:
                    raise EngageRuntimeError(
                        message=f"Module '{module_name}' has no symbol '{symbol_name}'",
                        line=getattr(node, 'line', None),
                        column=getattr(node, 'column', None),
                        file_path=self.file_path,
                        stack_trace=self.stack_trace,
                        error_type="Import Error"
                    )

            return NoneValue()

        except (ModuleNotFoundError, CircularDependencyError) as e:
            raise EngageRuntimeError(
                message=str(e),
                line=getattr(node, 'line', None),
                column=getattr(node, 'column', None),
                file_path=self.file_path,
                stack_trace=self.stack_trace,
                error_type="Import Error"
            )

    def visit_ExportVarNode(self, node, context):
        """Handle export variable statements."""
        var_name = node.name_token.value
        value = self.visit(node.value_node, context)

        # Set in current context
        context.set(var_name, value)

        # Add to exports
        if not hasattr(self, 'current_exports'):
            self.current_exports = {}
        self.current_exports[var_name] = value

        return value

    def visit_ExportFuncNode(self, node, context):
        """Handle export function statements."""
        func_name = node.name_token.value
        func_value = Function(func_name, node.body_nodes, [p.value for p in node.param_tokens])

        # Set in current context
        context.set(func_name, func_value)

        # Add to exports
        if not hasattr(self, 'current_exports'):
            self.current_exports = {}
        self.current_exports[func_name] = func_value

        return func_value

    def visit_PropertyDefNode(self, node, context):
        """Handle property definitions within records."""
        # This is typically called within a record context
        # The actual property handling is done in visit_RecordDefNode
        return None

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
            elif isinstance(member, PropertyDefNode):
                # Handle PropertyDefNode
                prop_name = member.name_token.value
                if member.default_value:
                    default_props[prop_name] = self.visit(member.default_value, temp_context)
                else:
                    default_props[prop_name] = NoneValue()

        record_class = Record(record_name, methods, default_props)
        context.set(record_name, record_class)
        return record_class

    def visit_NewInstanceNode(self, node, context):
        class_name = node.name_token.value

        # Handle built-in data structure types
        if class_name == "Table":
            return Table()
        elif class_name == "Vector":
            return Vector()

        # Handle user-defined record types
        record_class = context.get(class_name)
        if not isinstance(record_class, Record):
            raise TypeError(f"'{class_name}' is not a record type.")

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

        # Handle built-in data structure methods
        if isinstance(instance, Table):
            if member_name == "keys":
                return BuiltInFunction("keys", lambda args: [String(k) for k in instance.keys()])
            elif member_name == "values":
                return BuiltInFunction("values", lambda args: list(instance.values()))
            elif member_name == "has_key":
                return BuiltInFunction("has_key", lambda args: Number(1) if instance.has_key(args[0].value) else Number(0))
            elif member_name == "size":
                return Number(instance.size())
            else:
                raise AttributeError(f"Table has no attribute '{member_name}'")

        elif isinstance(instance, Vector):
            if member_name == "push":
                return BuiltInFunction("push", lambda args: instance.push(args[0]) if args else None)
            elif member_name == "pop":
                return BuiltInFunction("pop", lambda args: instance.pop())
            elif member_name == "length":
                return Number(instance.length())
            elif member_name == "insert":
                return BuiltInFunction("insert", lambda args: instance.insert(args[0].value, args[1]) if len(args) >= 2 else None)
            elif member_name == "remove":
                return BuiltInFunction("remove", lambda args: instance.remove(args[0].value) if args else None)
            else:
                raise AttributeError(f"Vector has no attribute '{member_name}'")

        elif isinstance(instance, RecordInstance):
            prop = instance.context.get(member_name)
            if prop: return prop

            method = instance.record_class.methods.get(member_name)
            if method:
                # If method has no parameters, call it automatically
                if len(method.arg_names) == 0:
                    return self.execute_user_function(method, [], context, instance)
                else:
                    return BoundMethod(instance, method)

            raise AttributeError(f"Record '{instance.record_class.name}' has no member '{member_name}'")

        elif isinstance(instance, ModuleValue):
            # Handle module member access
            member_value = instance.get_attribute(member_name)
            if member_value is not None:
                return member_value

            available_exports = list(instance.exports.keys())
            raise AttributeError(f"Module '{instance.name}' has no export '{member_name}'. Available exports: {', '.join(available_exports)}")

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

    def visit_TableNode(self, node, context):
        """Create a new Table instance."""
        return Table()

    def visit_VectorNode(self, node, context):
        """Create a new Vector instance."""
        return Vector()

    def visit_IndexAccessNode(self, node, context):
        """Handle bracket notation access like table["key"] or vector[0]."""
        obj = self.visit(node.object_node, context)
        index = self.visit(node.index_node, context)

        if isinstance(obj, Table):
            if not isinstance(index, String):
                raise TypeError("Table keys must be strings")
            value = obj.get(index.value)
            return value if value is not None else NoneValue()
        elif isinstance(obj, Vector):
            if not isinstance(index, Number):
                raise TypeError("Vector indices must be numbers")
            value = obj.get(int(index.value))
            return value if value is not None else NoneValue()
        else:
            raise TypeError(f"Cannot use bracket notation on {type(obj).__name__}")

    def visit_IndexAssignNode(self, node, context):
        """Handle bracket notation assignment like table["key"] = value or vector[0] = value."""
        obj = self.visit(node.object_node, context)
        index = self.visit(node.index_node, context)
        value = self.visit(node.value_node, context)

        if isinstance(obj, Table):
            if not isinstance(index, String):
                raise TypeError("Table keys must be strings")
            obj.set(index.value, value)
            return value
        elif isinstance(obj, Vector):
            if not isinstance(index, Number):
                raise TypeError("Vector indices must be numbers")
            obj.set(int(index.value), value)
            return value
        else:
            raise TypeError(f"Cannot use bracket notation assignment on {type(obj).__name__}")
        return value

    def visit_ImportNode(self, node, context):
        """Handle import statement: import "module" as alias"""
        module_name = node.module_name_token.value
        alias = node.alias_token.value if node.alias_token else None

        try:
            # Get the module system
            module_system = get_module_system()

            # Import the module
            exports = module_system.import_module(
                module_name=module_name,
                current_file=self.file_path,
                interpreter=self
            )

            # Determine what name to use in the symbol table
            import_name = alias if alias else module_name

            # For now, we'll import all exports directly into the namespace
            # In a full implementation, we might create a module object
            if alias:
                # If there's an alias, create a module namespace object
                module_obj = ModuleValue(module_name, exports)
                context.set(alias, module_obj)
            else:
                # Import all exports directly
                for name, value in exports.items():
                    context.set(name, value)

            return NoneValue()

        except ModuleNotFoundError as e:
            raise EngageRuntimeError(
                message=f"Module '{module_name}' not found: {str(e)}",
                line=node.module_name_token.line,
                column=node.module_name_token.column,
                file_path=self.file_path,
                stack_trace=self.stack_trace,
                error_type="Import Error"
            )
        except CircularDependencyError as e:
            raise EngageRuntimeError(
                message=f"Circular dependency detected: {str(e)}",
                line=node.module_name_token.line,
                column=node.module_name_token.column,
                file_path=self.file_path,
                stack_trace=self.stack_trace,
                error_type="Import Error"
            )
        except Exception as e:
            raise EngageRuntimeError(
                message=f"Error importing module '{module_name}': {str(e)}",
                line=node.module_name_token.line,
                column=node.module_name_token.column,
                file_path=self.file_path,
                stack_trace=self.stack_trace,
                error_type="Import Error"
            )

    def visit_FromImportNode(self, node, context):
        """Handle from import statement: from "module" import function1, function2"""
        module_name = node.module_name_token.value

        try:
            # Get the module system
            module_system = get_module_system()

            # Import the module
            exports = module_system.import_module(
                module_name=module_name,
                current_file=self.file_path,
                interpreter=self
            )

            # Import specific names
            for name_token, alias_token in node.import_names:
                import_name = name_token.value
                local_name = alias_token.value if alias_token else import_name

                if import_name not in exports:
                    available_names = list(exports.keys())
                    raise EngageRuntimeError(
                        message=f"Module '{module_name}' has no export '{import_name}'. Available exports: {', '.join(available_names)}",
                        line=name_token.line,
                        column=name_token.column,
                        file_path=self.file_path,
                        stack_trace=self.stack_trace,
                        error_type="Import Error"
                    )

                # Import the specific symbol
                context.set(local_name, exports[import_name])

            return NoneValue()

        except ModuleNotFoundError as e:
            raise EngageRuntimeError(
                message=f"Module '{module_name}' not found: {str(e)}",
                line=node.module_name_token.line,
                column=node.module_name_token.column,
                file_path=self.file_path,
                stack_trace=self.stack_trace,
                error_type="Import Error"
            )
        except CircularDependencyError as e:
            raise EngageRuntimeError(
                message=f"Circular dependency detected: {str(e)}",
                line=node.module_name_token.line,
                column=node.module_name_token.column,
                file_path=self.file_path,
                stack_trace=self.stack_trace,
                error_type="Import Error"
            )
        except EngageRuntimeError:
            # Re-raise EngageRuntimeError as-is
            raise
        except Exception as e:
            raise EngageRuntimeError(
                message=f"Error importing from module '{module_name}': {str(e)}",
                line=node.module_name_token.line,
                column=node.module_name_token.column,
                file_path=self.file_path,
                stack_trace=self.stack_trace,
                error_type="Import Error"
            )

    def visit_ExportVarNode(self, node, context):
        """Handle export variable statement: export let variable be value"""
        var_name = node.name_token.value
        value = self.visit(node.value_node, context)

        # Set the variable in the current context
        context.set(var_name, value)

        # Register this as an export in the module system
        self.register_export(var_name, value)

        return value

    def visit_ExportFuncNode(self, node, context):
        """Handle export function statement: to export function_name with params:"""
        func_name = node.name_token.value
        func_value = Function(func_name, node.body_nodes, [p.value for p in node.param_tokens])

        # Set the function in the current context
        context.set(func_name, func_value)

        # Register this as an export in the module system
        self.register_export(func_name, func_value)

        return func_value

    def register_export(self, name, value):
        """Register a symbol as an export for the current module."""
        # Store exports in the interpreter for the module system to access
        if not hasattr(self, 'current_exports'):
            self.current_exports = {}
        self.current_exports[name] = value

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
    except (ValueError, TypeError) as e:
        return ResultValue('Error', String(f"Cannot convert '{args[0].value}' to number"))

# Table built-in methods
def builtin_table_keys(args):
    if len(args) != 1:
        return ResultValue('Error', String("keys() expects one argument (the table)."))
    if not isinstance(args[0], Table):
        return ResultValue('Error', String("keys() can only be called on a Table."))

    keys = args[0].keys()
    # Return as a simple list representation for now
    return String(str(keys))

def builtin_table_values(args):
    if len(args) != 1:
        return ResultValue('Error', String("values() expects one argument (the table)."))
    if not isinstance(args[0], Table):
        return ResultValue('Error', String("values() can only be called on a Table."))

    values = args[0].values()
    # Convert values to their string representations
    value_strs = [str(v.value) if hasattr(v, 'value') else str(v) for v in values]
    return String(str(value_strs))

def builtin_table_has_key(args):
    if len(args) != 2:
        return ResultValue('Error', String("has_key() expects two arguments (table, key)."))
    if not isinstance(args[0], Table):
        return ResultValue('Error', String("has_key() can only be called on a Table."))
    if not isinstance(args[1], String):
        return ResultValue('Error', String("Table keys must be strings."))

    has_key = args[0].has_key(args[1].value)
    return Number(1) if has_key else Number(0)

def builtin_table_size(args):
    if len(args) != 1:
        return ResultValue('Error', String("size() expects one argument (the table)."))
    if not isinstance(args[0], Table):
        return ResultValue('Error', String("size() can only be called on a Table."))

    return Number(args[0].size())

# Vector built-in methods
def builtin_vector_push(args):
    if len(args) != 2:
        return ResultValue('Error', String("push() expects two arguments (vector, value)."))
    if not isinstance(args[0], Vector):
        return ResultValue('Error', String("push() can only be called on a Vector."))

    vector = args[0]
    value = args[1]
    new_length = vector.push(value)
    return Number(new_length)

def builtin_vector_pop(args):
    if len(args) != 1:
        return ResultValue('Error', String("pop() expects one argument (the vector)."))
    if not isinstance(args[0], Vector):
        return ResultValue('Error', String("pop() can only be called on a Vector."))

    vector = args[0]
    value = vector.pop()
    return value if value is not None else NoneValue()

def builtin_vector_length(args):
    if len(args) != 1:
        return ResultValue('Error', String("length() expects one argument (the vector)."))
    if not isinstance(args[0], Vector):
        return ResultValue('Error', String("length() can only be called on a Vector."))

    return Number(args[0].length())

def builtin_vector_insert(args):
    if len(args) != 3:
        return ResultValue('Error', String("insert() expects three arguments (vector, index, value)."))
    if not isinstance(args[0], Vector):
        return ResultValue('Error', String("insert() can only be called on a Vector."))
    if not isinstance(args[1], Number):
        return ResultValue('Error', String("Vector indices must be numbers."))

    vector = args[0]
    index = int(args[1].value)
    value = args[2]

    try:
        vector.insert(index, value)
        return Number(vector.length())
    except (TypeError, IndexError) as e:
        return ResultValue('Error', String(str(e)))

def builtin_vector_remove(args):
    if len(args) != 2:
        return ResultValue('Error', String("remove() expects two arguments (vector, index)."))
    if not isinstance(args[0], Vector):
        return ResultValue('Error', String("remove() can only be called on a Vector."))
    if not isinstance(args[1], Number):
        return ResultValue('Error', String("Vector indices must be numbers."))

    vector = args[0]
    index = int(args[1].value)

    try:
        value = vector.remove(index)
        return value if value is not None else NoneValue()
    except (TypeError, IndexError) as e:
        return ResultValue('Error', String(str(e)))

# --- Global Environment Setup ---
global_symbol_table = SymbolTable()

def setup_global_environment(symbol_table):
    """Set up the given symbol table with all integrated features."""

    # Initialize the modular standard library system
    stdlib = get_standard_library()

    # Register core built-in functions that are always available
    stdlib.register_builtin_function("print", builtin_print)
    stdlib.register_builtin_function("input", builtin_input)
    stdlib.register_builtin_function("number", builtin_number)

    # Register data structure built-in functions
    stdlib.register_builtin_function("keys", builtin_table_keys)
    stdlib.register_builtin_function("values", builtin_table_values)
    stdlib.register_builtin_function("has_key", builtin_table_has_key)
    stdlib.register_builtin_function("size", builtin_table_size)
    stdlib.register_builtin_function("push", builtin_vector_push)
    stdlib.register_builtin_function("pop", builtin_vector_pop)
    stdlib.register_builtin_function("length", builtin_vector_length)
    stdlib.register_builtin_function("insert", builtin_vector_insert)
    stdlib.register_builtin_function("remove", builtin_vector_remove)

    # Register standard library modules
    try:
        stdlib.register_module("strings", StringsModule)
        stdlib.register_module("math", MathModule)
        stdlib.register_module("files", FilesModule)
        stdlib.register_module("types", TypesModule)
        stdlib.register_module("collections", CollectionsModule)
    except Exception as e:
        print(f"Warning: Failed to register standard library modules: {e}")

    # Load built-in functions into the provided symbol table
    stdlib.load_builtin_functions(symbol_table, BuiltInFunction)

    # Load UI component built-in functions
    if UI_AVAILABLE:
        try:
            for func_name, func_obj in UI_BUILTIN_FUNCTIONS.items():
                symbol_table.set(func_name, func_obj)
        except Exception as e:
            print(f"Warning: Error loading UI functions: {e}")

    # Load Game object built-in functions
    if GAME_AVAILABLE:
        try:
            for func_name, func_obj in GAME_BUILTIN_FUNCTIONS.items():
                symbol_table.set(func_name, func_obj)
        except Exception as e:
            print(f"Warning: Error loading game functions: {e}")

    # Auto-load standard library modules
    modules_to_load = ["strings", "math", "files", "types", "collections"]
    for module_name in modules_to_load:
        try:
            stdlib.load_module_functions(module_name, symbol_table, BuiltInFunction)
        except Exception as e:
            print(f"Warning: Failed to load {module_name} module: {e}")

# Initialize the global environment
setup_global_environment(global_symbol_table)

def load_stdlib_module(module_name: str, symbol_table=None):
    """
    Load a standard library module into the given symbol table.

    Args:
        module_name: Name of the module to load
        symbol_table: Symbol table to load into (defaults to global)

    Returns:
        True if successful, False otherwise
    """
    if symbol_table is None:
        symbol_table = global_symbol_table

    try:
        stdlib.load_module_functions(module_name, symbol_table, BuiltInFunction)
        return True
    except Exception as e:
        print(f"Error loading module '{module_name}': {e}")
        return False

def list_available_modules():
    """
    Get a list of all available standard library modules.

    Returns:
        List of module names
    """
    return stdlib.list_modules()

def list_module_functions(module_name: str):
    """
    Get a list of functions in a specific module.

    Args:
        module_name: Name of the module

    Returns:
        List of function names, or empty list if module not found
    """
    try:
        return stdlib.list_module_functions(module_name)
    except Exception:
        return []


# --- Main Execution Function ---
def run(code, symbol_table, file_path=None):
    from engage_lexer import Lexer
    from engage_parser import Parser

    # Enhanced error reporting integration
    lexer = Lexer(code, file_path)

    # Check for lexical errors
    if lexer.has_errors():
        print("Lexical Errors:")
        print(lexer.get_error_report())
        return None

    tokens = lexer.tokenize()
    parser = Parser(tokens, file_path, code)

    # Parse with error recovery
    ast = parser.parse()

    # Check for parsing errors (but continue if we have a partial AST)
    if parser.has_errors():
        print("Parsing Errors:")
        print(parser.get_error_report())
        if not ast or not ast.statements:
            print("Too many parsing errors - cannot continue execution.")
            return None
        print("Continuing execution with partial AST...\n")

    if not ast:
        return None

    interpreter = Interpreter(file_path)

    try:
        # Push main program frame onto stack
        main_frame = interpreter.stack_trace.push_frame(
            function_name="<main>",
            file_path=file_path,
            context=symbol_table
        )

        result = interpreter.visit(ast, symbol_table)

        # Pop main frame
        interpreter.stack_trace.pop_frame()

        return result
    except EngageRuntimeError as e:
        # Display enhanced error with stack trace
        print("\n" + "="*50)
        print(e.format_error(show_locals=False))
        print("="*50)
        return None
    except Exception as e:
        # Handle unexpected errors
        print(f"\nUnexpected error: {e}")
        if interpreter.stack_trace.frames:
            print("\nStack trace:")
            print(interpreter.stack_trace.format_stack_trace())
        return None

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
        print("--- No file provided. Running built-in example for Records. ---")
        engage_code = """
        // records_demo.engage
        // Demonstrates defining records with properties and methods.

        define a record named Vector2:
            let x be 0.
            let y be 0.

            to add with other:
                let new_x be self.x plus other.x.
                let new_y be self.y plus other.y.
                return new Vector2 with x: new_x, y: new_y.
            end

            to scale with factor:
                set self.x to self.x times factor.
                set self.y to self.y times factor.
            end

            to magnitude:
                let x_squared be self.x times self.x.
                let y_squared be self.y times self.y.
                return x_squared plus y_squared.
            end
        end

        print with "Creating vectors...".
        let v1 be new Vector2 with x: 3, y: 4.
        let v2 be new Vector2 with x: 1, y: 2.

        print with "Adding v1 and v2...".
        let v3 be v1.add with v2.
        print with "Result (v3) x:".
        print with v3.x.
        print with "Result (v3) y:".
        print with v3.y.

        print with "Scaling v1 by 10...".
        v1.scale with 10.
        print with "New v1.x:".
        print with v1.x.

        print with "Calculating magnitude of the new v1...".
        let mag_sq be v1.magnitude.
        print with "Squared magnitude of v1:".
        print with mag_sq.
        """

    print(f"\nCODE:\n{engage_code}\n")
    print("--- OUTPUT ---")

    try:
        file_path = filepath if len(sys.argv) > 1 else None
        run(engage_code, global_symbol_table, file_path)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\nAn error occurred: {e}")
