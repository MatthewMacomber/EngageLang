# engage_ui_components.py
# UI Component System Foundation for Engage Programming Language

from engage_values import Value, Function, BuiltInFunction, SymbolTable
from engage_errors import EngageRuntimeError
import uuid
from typing import Dict, List, Optional, Callable, Any

# --- Base UI Component System ---

class UIEvent:
    """Represents a UI event that can be triggered on components."""
    
    def __init__(self, event_type: str, source_component=None, data=None):
        self.event_type = event_type  # 'click', 'hover', 'input_change', etc.
        self.source_component = source_component
        self.data = data or {}
        self.timestamp = None  # Could be set by the rendering system
        self.handled = False
    
    def mark_handled(self):
        """Mark this event as handled to prevent further propagation."""
        self.handled = True
    
    def __repr__(self):
        return f"UIEvent(type='{self.event_type}', source={self.source_component}, data={self.data})"

class UIComponent(Value):
    """Base class for all UI components in Engage."""
    
    def __init__(self, component_type: str, component_id: str = None):
        super().__init__()
        self.component_type = component_type
        self.component_id = component_id or str(uuid.uuid4())
        
        # Common properties for all UI components
        self.x = 0
        self.y = 0
        self.width = 100
        self.height = 30
        self.visible = True
        self.enabled = True
        
        # Hierarchy management
        self.parent = None
        self.children = []
        
        # Event handling
        self.event_handlers = {}  # event_type -> list of callback functions
        
        # Rendering state
        self.needs_render = True
        self.render_data = {}
    
    def __repr__(self):
        return f"<{self.component_type} id='{self.component_id}' at ({self.x}, {self.y})>"
    
    @property
    def value(self):
        """Return a string representation for use with print and other functions."""
        return f"{self.component_type}('{self.component_id}')"
    
    def is_true(self):
        """UI components are considered 'true' if they are visible and enabled."""
        return self.visible and self.enabled
    
    # --- Property Management ---
    
    def set_position(self, x: int, y: int):
        """Set the position of the component."""
        if self.x != x or self.y != y:
            self.x = x
            self.y = y
            self.mark_needs_render()
    
    def set_size(self, width: int, height: int):
        """Set the size of the component."""
        if self.width != width or self.height != height:
            self.width = width
            self.height = height
            self.mark_needs_render()
    
    def set_visible(self, visible: bool):
        """Set the visibility of the component."""
        if self.visible != visible:
            self.visible = visible
            self.mark_needs_render()
    
    def set_enabled(self, enabled: bool):
        """Set whether the component is enabled for interaction."""
        if self.enabled != enabled:
            self.enabled = enabled
            self.mark_needs_render()
    
    def get_bounds(self):
        """Get the bounding rectangle of the component."""
        return {
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height,
            'right': self.x + self.width,
            'bottom': self.y + self.height
        }
    
    def contains_point(self, x: int, y: int) -> bool:
        """Check if a point is within the component's bounds."""
        bounds = self.get_bounds()
        return (bounds['x'] <= x <= bounds['right'] and 
                bounds['y'] <= y <= bounds['bottom'])
    
    # --- Hierarchy Management ---
    
    def add_child(self, child_component):
        """Add a child component to this component."""
        if not isinstance(child_component, UIComponent):
            raise TypeError("Child must be a UIComponent")
        
        if child_component.parent:
            child_component.parent.remove_child(child_component)
        
        child_component.parent = self
        self.children.append(child_component)
        self.mark_needs_render()
    
    def remove_child(self, child_component):
        """Remove a child component from this component."""
        if child_component in self.children:
            child_component.parent = None
            self.children.remove(child_component)
            self.mark_needs_render()
    
    def get_children(self) -> List['UIComponent']:
        """Get all child components."""
        return self.children.copy()
    
    def get_parent(self) -> Optional['UIComponent']:
        """Get the parent component."""
        return self.parent
    
    def get_root(self) -> 'UIComponent':
        """Get the root component in the hierarchy."""
        current = self
        while current.parent:
            current = current.parent
        return current
    
    def find_child_by_id(self, component_id: str) -> Optional['UIComponent']:
        """Find a child component by its ID (recursive search)."""
        for child in self.children:
            if child.component_id == component_id:
                return child
            found = child.find_child_by_id(component_id)
            if found:
                return found
        return None
    
    # --- Event Handling System ---
    
    def add_event_handler(self, event_type: str, handler):
        """Add an event handler for a specific event type."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        
        # Handler can be either a Python callable or an Engage Function
        if not (callable(handler) or isinstance(handler, (Function, BuiltInFunction))):
            raise TypeError("Event handler must be callable or an Engage Function")
        
        self.event_handlers[event_type].append(handler)
    
    def remove_event_handler(self, event_type: str, handler):
        """Remove a specific event handler."""
        if event_type in self.event_handlers:
            try:
                self.event_handlers[event_type].remove(handler)
                if not self.event_handlers[event_type]:
                    del self.event_handlers[event_type]
            except ValueError:
                pass  # Handler not found, ignore
    
    def clear_event_handlers(self, event_type: str = None):
        """Clear event handlers for a specific type or all types."""
        if event_type:
            self.event_handlers.pop(event_type, None)
        else:
            self.event_handlers.clear()
    
    def trigger_event(self, event: UIEvent, context=None):
        """Trigger an event on this component."""
        if not self.enabled:
            return False  # Disabled components don't handle events
        
        event.source_component = self
        handled = False
        
        # Execute handlers for this event type
        handlers = self.event_handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                if isinstance(handler, (Function, BuiltInFunction)):
                    # Execute Engage function handler
                    if context:
                        self._execute_engage_handler(handler, event, context)
                else:
                    # Execute Python callable handler
                    handler(event)
                
                handled = True
                if event.handled:
                    break  # Stop processing if event was marked as handled
                    
            except Exception as e:
                # Log error but continue processing other handlers
                print(f"Error in event handler for {event.event_type}: {e}")
        
        return handled
    
    def _execute_engage_handler(self, handler, event, context):
        """Execute an Engage function as an event handler."""
        # This would need to be integrated with the interpreter
        # For now, we'll create a basic interface
        if isinstance(handler, Function):
            # Create event data that can be passed to Engage functions
            from engage_interpreter import String, Number, Table
            
            event_table = Table()
            event_table.set("type", String(event.event_type))
            event_table.set("component_id", String(self.component_id))
            
            # Add event-specific data
            for key, value in event.data.items():
                if isinstance(value, str):
                    event_table.set(key, String(value))
                elif isinstance(value, (int, float)):
                    event_table.set(key, Number(value))
            
            # Execute the handler function with the event data
            # This would need proper integration with the interpreter's execute_user_function
            pass
    
    # --- Rendering Interface ---
    
    def mark_needs_render(self):
        """Mark this component as needing to be re-rendered."""
        self.needs_render = True
        # Propagate to parent if needed
        if self.parent:
            self.parent.mark_needs_render()
    
    def clear_render_flag(self):
        """Clear the needs_render flag after rendering."""
        self.needs_render = False
    
    def prepare_render_data(self) -> Dict[str, Any]:
        """Prepare data needed for rendering this component."""
        self.render_data = {
            'component_type': self.component_type,
            'component_id': self.component_id,
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height,
            'visible': self.visible,
            'enabled': self.enabled,
            'children': [child.prepare_render_data() for child in self.children if child.visible]
        }
        return self.render_data
    
    def render(self, renderer=None):
        """Render this component using the provided renderer."""
        if not self.visible:
            return
        
        # Prepare render data
        render_data = self.prepare_render_data()
        
        # Call the actual rendering implementation
        if renderer:
            renderer.render_component(self, render_data)
        else:
            # Default console-based rendering for testing
            self._console_render(render_data)
        
        # Render children
        for child in self.children:
            if child.visible:
                child.render(renderer)
        
        self.clear_render_flag()
    
    def _console_render(self, render_data):
        """Basic console rendering for testing purposes."""
        indent = "  " * self._get_hierarchy_depth()
        print(f"{indent}{self.component_type} '{self.component_id}' at ({self.x}, {self.y}) size ({self.width}x{self.height})")
    
    def _get_hierarchy_depth(self) -> int:
        """Get the depth of this component in the hierarchy."""
        depth = 0
        current = self.parent
        while current:
            depth += 1
            current = current.parent
        return depth

# --- UI Component Manager ---

class UIComponentManager:
    """Manages the lifecycle and interactions of UI components."""
    
    def __init__(self):
        self.components = {}  # component_id -> component
        self.root_components = []  # Components without parents
        self.event_queue = []
        self.renderer = None
    
    def register_component(self, component: UIComponent):
        """Register a component with the manager."""
        self.components[component.component_id] = component
        if not component.parent:
            self.root_components.append(component)
    
    def unregister_component(self, component: UIComponent):
        """Unregister a component from the manager."""
        if component.component_id in self.components:
            del self.components[component.component_id]
        
        if component in self.root_components:
            self.root_components.remove(component)
        
        # Remove from parent if it has one
        if component.parent:
            component.parent.remove_child(component)
    
    def get_component(self, component_id: str) -> Optional[UIComponent]:
        """Get a component by its ID."""
        return self.components.get(component_id)
    
    def find_component_at_position(self, x: int, y: int) -> Optional[UIComponent]:
        """Find the topmost component at the given position."""
        # Search from root components down
        for root in reversed(self.root_components):  # Reverse for top-to-bottom search
            found = self._find_component_at_position_recursive(root, x, y)
            if found:
                return found
        return None
    
    def _find_component_at_position_recursive(self, component: UIComponent, x: int, y: int) -> Optional[UIComponent]:
        """Recursively search for component at position."""
        if not component.visible or not component.contains_point(x, y):
            return None
        
        # Check children first (they're on top)
        for child in reversed(component.children):
            found = self._find_component_at_position_recursive(child, x, y)
            if found:
                return found
        
        # If no child contains the point, this component does
        return component
    
    def queue_event(self, event: UIEvent):
        """Queue an event for processing."""
        self.event_queue.append(event)
    
    def process_events(self, context=None):
        """Process all queued events."""
        while self.event_queue:
            event = self.event_queue.pop(0)
            
            if event.source_component:
                event.source_component.trigger_event(event, context)
            else:
                # Broadcast event to all components
                for component in self.components.values():
                    component.trigger_event(event, context)
                    if event.handled:
                        break
    
    def render_all(self):
        """Render all root components."""
        for root in self.root_components:
            if root.needs_render or any(self._needs_render_recursive(root)):
                root.render(self.renderer)
    
    def _needs_render_recursive(self, component: UIComponent) -> bool:
        """Check if component or any of its children need rendering."""
        if component.needs_render:
            return True
        return any(self._needs_render_recursive(child) for child in component.children)
    
    def set_renderer(self, renderer):
        """Set the renderer for all components."""
        self.renderer = renderer

# --- Global UI Manager Instance ---
ui_manager = UIComponentManager()

# --- Built-in Functions for Engage Integration ---

def create_ui_component_builtin(component_type: str):
    """Create a built-in function factory for UI component creation."""
    
    def create_component(args):
        from engage_interpreter import String, Number, Table
        
        # Create the component
        component = UIComponent(component_type)
        
        # Register with the manager
        ui_manager.register_component(component)
        
        return component
    
    return BuiltInFunction(f"create_{component_type.lower()}", create_component)

def ui_set_property_builtin(args):
    """Built-in function to set UI component properties."""
    from engage_interpreter import String, Number
    
    if len(args) != 3:
        raise TypeError("ui_set_property requires 3 arguments: component, property_name, value")
    
    component, prop_name, value = args
    

    
    if not isinstance(component, UIComponent):
        raise TypeError("First argument must be a UIComponent")
    
    if not (hasattr(prop_name, 'value') and type(prop_name).__name__ == 'String'):
        raise TypeError("Property name must be a string")
    
    prop = prop_name.value
    
    # Handle different property types
    if prop in ('x', 'y', 'width', 'height'):
        if not (hasattr(value, 'value') and type(value).__name__ == 'Number'):
            raise TypeError(f"Property '{prop}' must be a number")
        setattr(component, prop, int(value.value))
        component.mark_needs_render()
    elif prop in ('visible', 'enabled'):
        bool_value = value.is_true() if hasattr(value, 'is_true') else bool(value.value)
        setattr(component, prop, bool_value)
        component.mark_needs_render()
    else:
        raise ValueError(f"Unknown property: {prop}")
    
    return component

def ui_add_event_handler_builtin(args):
    """Built-in function to add event handlers to UI components."""
    from engage_interpreter import String
    
    if len(args) != 3:
        raise TypeError("ui_add_event_handler requires 3 arguments: component, event_type, handler")
    
    component, event_type, handler = args
    
    if not isinstance(component, UIComponent):
        raise TypeError("First argument must be a UIComponent")
    
    if not isinstance(event_type, String):
        raise TypeError("Event type must be a string")
    
    component.add_event_handler(event_type.value, handler)
    return component

# --- Export built-in functions for interpreter integration ---
UI_BUILTIN_FUNCTIONS = {
    'create_ui_component': create_ui_component_builtin('UIComponent'),
    'ui_set_property': BuiltInFunction('ui_set_property', ui_set_property_builtin),
    'ui_add_event_handler': BuiltInFunction('ui_add_event_handler', ui_add_event_handler_builtin),
}

# --- Specific UI Component Types ---

class Button(UIComponent):
    """Button component with click event handling."""
    
    def __init__(self, text: str = "", component_id: str = None):
        super().__init__("Button", component_id)
        self.text = text
        self.width = max(100, len(text) * 8 + 20)  # Auto-size based on text
        self.height = 30
    
    def set_text(self, text: str):
        """Set the button text."""
        if self.text != text:
            self.text = text
            self.width = max(100, len(text) * 8 + 20)  # Auto-resize
            self.mark_needs_render()
    
    def get_text(self) -> str:
        """Get the button text."""
        return self.text
    
    def click(self, context=None):
        """Programmatically trigger a click event."""
        event = UIEvent("click", self, {"button": "left"})
        self.trigger_event(event, context)
    
    def prepare_render_data(self) -> Dict[str, Any]:
        """Prepare render data including button-specific properties."""
        data = super().prepare_render_data()
        data['text'] = self.text
        return data
    
    def _console_render(self, render_data):
        """Console rendering for button."""
        indent = "  " * self._get_hierarchy_depth()
        status = "enabled" if self.enabled else "disabled"
        print(f"{indent}Button '{self.component_id}': \"{self.text}\" at ({self.x}, {self.y}) [{status}]")

class Label(UIComponent):
    """Label component for text display."""
    
    def __init__(self, text: str = "", component_id: str = None):
        super().__init__("Label", component_id)
        self.text = text
        self.width = max(50, len(text) * 8)  # Auto-size based on text
        self.height = 20
        self.text_color = "black"
        self.font_size = 12
    
    def set_text(self, text: str):
        """Set the label text."""
        if self.text != text:
            self.text = text
            self.width = max(50, len(text) * 8)  # Auto-resize
            self.mark_needs_render()
    
    def get_text(self) -> str:
        """Get the label text."""
        return self.text
    
    def set_text_color(self, color: str):
        """Set the text color."""
        if self.text_color != color:
            self.text_color = color
            self.mark_needs_render()
    
    def set_font_size(self, size: int):
        """Set the font size."""
        if self.font_size != size:
            self.font_size = size
            self.mark_needs_render()
    
    def prepare_render_data(self) -> Dict[str, Any]:
        """Prepare render data including label-specific properties."""
        data = super().prepare_render_data()
        data.update({
            'text': self.text,
            'text_color': self.text_color,
            'font_size': self.font_size
        })
        return data
    
    def _console_render(self, render_data):
        """Console rendering for label."""
        indent = "  " * self._get_hierarchy_depth()
        print(f"{indent}Label '{self.component_id}': \"{self.text}\" at ({self.x}, {self.y})")

class TextInput(UIComponent):
    """Text input component with input validation."""
    
    def __init__(self, placeholder: str = "", component_id: str = None):
        super().__init__("TextInput", component_id)
        self.text = ""
        self.placeholder = placeholder
        self.width = 200
        self.height = 25
        self.max_length = None
        self.is_password = False
        self.is_focused = False
        self.validation_pattern = None
    
    def set_text(self, text: str):
        """Set the input text with validation."""
        if self.max_length and len(text) > self.max_length:
            text = text[:self.max_length]
        
        if self.validation_pattern:
            import re
            if not re.match(self.validation_pattern, text):
                # Trigger validation error event
                event = UIEvent("validation_error", self, {"text": text, "pattern": self.validation_pattern})
                self.trigger_event(event)
                return False
        
        if self.text != text:
            old_text = self.text
            self.text = text
            self.mark_needs_render()
            
            # Trigger input change event
            event = UIEvent("input_change", self, {"old_text": old_text, "new_text": text})
            self.trigger_event(event)
        
        return True
    
    def get_text(self) -> str:
        """Get the input text."""
        return self.text
    
    def set_placeholder(self, placeholder: str):
        """Set the placeholder text."""
        if self.placeholder != placeholder:
            self.placeholder = placeholder
            self.mark_needs_render()
    
    def set_max_length(self, max_length: int):
        """Set the maximum text length."""
        self.max_length = max_length
        if self.max_length and len(self.text) > self.max_length:
            self.set_text(self.text[:self.max_length])
    
    def set_password_mode(self, is_password: bool):
        """Set whether this is a password input."""
        if self.is_password != is_password:
            self.is_password = is_password
            self.mark_needs_render()
    
    def set_validation_pattern(self, pattern: str):
        """Set a regex pattern for input validation."""
        self.validation_pattern = pattern
    
    def focus(self):
        """Give focus to this input."""
        if not self.is_focused:
            self.is_focused = True
            self.mark_needs_render()
            event = UIEvent("focus", self)
            self.trigger_event(event)
    
    def blur(self):
        """Remove focus from this input."""
        if self.is_focused:
            self.is_focused = False
            self.mark_needs_render()
            event = UIEvent("blur", self)
            self.trigger_event(event)
    
    def clear(self):
        """Clear the input text."""
        self.set_text("")
    
    def prepare_render_data(self) -> Dict[str, Any]:
        """Prepare render data including input-specific properties."""
        data = super().prepare_render_data()
        data.update({
            'text': self.text,
            'placeholder': self.placeholder,
            'is_password': self.is_password,
            'is_focused': self.is_focused,
            'max_length': self.max_length
        })
        return data
    
    def _console_render(self, render_data):
        """Console rendering for text input."""
        indent = "  " * self._get_hierarchy_depth()
        display_text = "*" * len(self.text) if self.is_password else self.text
        focus_indicator = " [FOCUSED]" if self.is_focused else ""
        placeholder_text = f" (placeholder: \"{self.placeholder}\")" if self.placeholder and not self.text else ""
        print(f"{indent}TextInput '{self.component_id}': \"{display_text}\"{placeholder_text} at ({self.x}, {self.y}){focus_indicator}")

class Panel(UIComponent):
    """Panel component for layout management and grouping."""
    
    def __init__(self, component_id: str = None):
        super().__init__("Panel", component_id)
        self.width = 300
        self.height = 200
        self.background_color = "white"
        self.border_width = 1
        self.border_color = "gray"
        self.padding = 5
        self.layout_type = "none"  # "none", "vertical", "horizontal", "grid"
        self.spacing = 5
    
    def set_background_color(self, color: str):
        """Set the background color."""
        if self.background_color != color:
            self.background_color = color
            self.mark_needs_render()
    
    def set_border(self, width: int, color: str):
        """Set the border width and color."""
        if self.border_width != width or self.border_color != color:
            self.border_width = width
            self.border_color = color
            self.mark_needs_render()
    
    def set_padding(self, padding: int):
        """Set the internal padding."""
        if self.padding != padding:
            self.padding = padding
            self.mark_needs_render()
            self._update_child_layout()
    
    def set_layout_type(self, layout_type: str):
        """Set the layout type for child components."""
        if layout_type not in ("none", "vertical", "horizontal", "grid"):
            raise ValueError("Layout type must be 'none', 'vertical', 'horizontal', or 'grid'")
        
        if self.layout_type != layout_type:
            self.layout_type = layout_type
            self._update_child_layout()
    
    def set_spacing(self, spacing: int):
        """Set the spacing between child components."""
        if self.spacing != spacing:
            self.spacing = spacing
            self._update_child_layout()
    
    def add_child(self, child_component):
        """Add a child and update layout."""
        super().add_child(child_component)
        self._update_child_layout()
    
    def remove_child(self, child_component):
        """Remove a child and update layout."""
        super().remove_child(child_component)
        self._update_child_layout()
    
    def _update_child_layout(self):
        """Update the layout of child components based on layout type."""
        if not self.children or self.layout_type == "none":
            return
        
        content_x = self.x + self.padding
        content_y = self.y + self.padding
        content_width = self.width - (2 * self.padding)
        content_height = self.height - (2 * self.padding)
        
        if self.layout_type == "vertical":
            current_y = content_y
            for child in self.children:
                child.set_position(content_x, current_y)
                current_y += child.height + self.spacing
        
        elif self.layout_type == "horizontal":
            current_x = content_x
            for child in self.children:
                child.set_position(current_x, content_y)
                current_x += child.width + self.spacing
        
        elif self.layout_type == "grid":
            # Simple grid layout - calculate columns based on panel width
            cols = max(1, content_width // (150 + self.spacing))  # Assume 150px per column
            current_x = content_x
            current_y = content_y
            col = 0
            
            for child in self.children:
                child.set_position(current_x, current_y)
                col += 1
                
                if col >= cols:
                    col = 0
                    current_x = content_x
                    current_y += child.height + self.spacing
                else:
                    current_x += child.width + self.spacing
    
    def get_content_bounds(self):
        """Get the bounds of the content area (excluding padding)."""
        return {
            'x': self.x + self.padding,
            'y': self.y + self.padding,
            'width': self.width - (2 * self.padding),
            'height': self.height - (2 * self.padding)
        }
    
    def prepare_render_data(self) -> Dict[str, Any]:
        """Prepare render data including panel-specific properties."""
        data = super().prepare_render_data()
        data.update({
            'background_color': self.background_color,
            'border_width': self.border_width,
            'border_color': self.border_color,
            'padding': self.padding,
            'layout_type': self.layout_type,
            'spacing': self.spacing
        })
        return data
    
    def _console_render(self, render_data):
        """Console rendering for panel."""
        indent = "  " * self._get_hierarchy_depth()
        print(f"{indent}Panel '{self.component_id}' at ({self.x}, {self.y}) size ({self.width}x{self.height}) layout={self.layout_type}")

# --- Enhanced Built-in Functions for Specific Components ---

def create_button_builtin(args):
    """Create a Button component."""
    from engage_interpreter import String
    
    text = ""
    if args and isinstance(args[0], String):
        text = args[0].value
    
    button = Button(text)
    ui_manager.register_component(button)
    return button

def create_label_builtin(args):
    """Create a Label component."""
    from engage_interpreter import String
    
    text = ""
    if args and isinstance(args[0], String):
        text = args[0].value
    
    label = Label(text)
    ui_manager.register_component(label)
    return label

def create_text_input_builtin(args):
    """Create a TextInput component."""
    from engage_interpreter import String
    
    placeholder = ""
    if args and isinstance(args[0], String):
        placeholder = args[0].value
    
    text_input = TextInput(placeholder)
    ui_manager.register_component(text_input)
    return text_input

def create_panel_builtin(args):
    """Create a Panel component."""
    panel = Panel()
    ui_manager.register_component(panel)
    return panel

def ui_add_child_builtin(args):
    """Add a child component to a parent component."""
    if len(args) != 2:
        raise TypeError("ui_add_child requires 2 arguments: parent, child")
    
    parent, child = args
    
    if not isinstance(parent, UIComponent):
        raise TypeError("Parent must be a UIComponent")
    
    if not isinstance(child, UIComponent):
        raise TypeError("Child must be a UIComponent")
    
    parent.add_child(child)
    return parent

def ui_trigger_event_builtin(args):
    """Trigger an event on a component."""
    from engage_interpreter import String, Table
    
    if len(args) < 2:
        raise TypeError("ui_trigger_event requires at least 2 arguments: component, event_type")
    
    component, event_type = args[:2]
    event_data = args[2] if len(args) > 2 else None
    
    if not isinstance(component, UIComponent):
        raise TypeError("First argument must be a UIComponent")
    
    if not (hasattr(event_type, 'value') and type(event_type).__name__ == 'String'):
        raise TypeError("Event type must be a string")
    
    # Convert event data if provided
    data = {}
    if event_data and hasattr(event_data, 'data') and hasattr(event_data, 'keys'):
        for key in event_data.keys():
            value = event_data.get(key)
            if hasattr(value, 'value'):
                data[key] = value.value
            else:
                data[key] = str(value)
    
    event = UIEvent(event_type.value, component, data)
    component.trigger_event(event)
    return component

# --- Update the built-in functions dictionary ---
UI_BUILTIN_FUNCTIONS.update({
    'create_button': BuiltInFunction('create_button', create_button_builtin),
    'create_label': BuiltInFunction('create_label', create_label_builtin),
    'create_text_input': BuiltInFunction('create_text_input', create_text_input_builtin),
    'create_panel': BuiltInFunction('create_panel', create_panel_builtin),
    'ui_add_child': BuiltInFunction('ui_add_child', ui_add_child_builtin),
    'ui_trigger_event': BuiltInFunction('ui_trigger_event', ui_trigger_event_builtin),
})