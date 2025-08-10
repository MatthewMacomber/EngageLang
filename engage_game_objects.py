# engage_game_objects.py
# Game Object System Foundation for Engage Programming Language

from engage_interpreter import Value, Function, BuiltInFunction, SymbolTable, EngageRuntimeError
import uuid
import math
from typing import Dict, List, Optional, Callable, Any, Tuple

# --- Game Event System ---

class GameEvent:
    """Represents a game event that can be triggered on game objects."""
    
    def __init__(self, event_type: str, source_object=None, data=None):
        self.event_type = event_type  # 'collision', 'update', 'render', 'destroy', etc.
        self.source_object = source_object
        self.data = data or {}
        self.timestamp = None  # Could be set by the game loop
        self.handled = False
    
    def mark_handled(self):
        """Mark this event as handled to prevent further propagation."""
        self.handled = True
    
    def __repr__(self):
        return f"GameEvent(type='{self.event_type}', source={self.source_object}, data={self.data})"

# --- Transform System ---

class Transform:
    """Represents position, rotation, and scale of a game object."""
    
    def __init__(self, x: float = 0.0, y: float = 0.0, rotation: float = 0.0, scale_x: float = 1.0, scale_y: float = 1.0):
        self.x = x
        self.y = y
        self.rotation = rotation  # In degrees
        self.scale_x = scale_x
        self.scale_y = scale_y
        
        # Cached values for performance
        self._dirty = True
        self._world_matrix = None
    
    def set_position(self, x: float, y: float):
        """Set the position of the transform."""
        if self.x != x or self.y != y:
            self.x = x
            self.y = y
            self._mark_dirty()
    
    def set_rotation(self, rotation: float):
        """Set the rotation in degrees."""
        # Normalize rotation to 0-360 range
        rotation = rotation % 360
        if self.rotation != rotation:
            self.rotation = rotation
            self._mark_dirty()
    
    def set_scale(self, scale_x: float, scale_y: float = None):
        """Set the scale. If scale_y is None, uses scale_x for both axes."""
        if scale_y is None:
            scale_y = scale_x
        
        if self.scale_x != scale_x or self.scale_y != scale_y:
            self.scale_x = scale_x
            self.scale_y = scale_y
            self._mark_dirty()
    
    def translate(self, dx: float, dy: float):
        """Move the transform by the given offset."""
        self.set_position(self.x + dx, self.y + dy)
    
    def rotate(self, degrees: float):
        """Rotate the transform by the given degrees."""
        self.set_rotation(self.rotation + degrees)
    
    def scale(self, factor_x: float, factor_y: float = None):
        """Scale the transform by the given factors."""
        if factor_y is None:
            factor_y = factor_x
        self.set_scale(self.scale_x * factor_x, self.scale_y * factor_y)
    
    def get_forward_vector(self) -> Tuple[float, float]:
        """Get the forward direction vector based on rotation."""
        rad = math.radians(self.rotation)
        return (math.cos(rad), math.sin(rad))
    
    def get_right_vector(self) -> Tuple[float, float]:
        """Get the right direction vector based on rotation."""
        rad = math.radians(self.rotation + 90)
        return (math.cos(rad), math.sin(rad))
    
    def distance_to(self, other: 'Transform') -> float:
        """Calculate distance to another transform."""
        dx = self.x - other.x
        dy = self.y - other.y
        return math.sqrt(dx * dx + dy * dy)
    
    def angle_to(self, other: 'Transform') -> float:
        """Calculate angle to another transform in degrees."""
        dx = other.x - self.x
        dy = other.y - self.y
        return math.degrees(math.atan2(dy, dx))
    
    def _mark_dirty(self):
        """Mark the transform as dirty for matrix recalculation."""
        self._dirty = True
    
    def get_world_matrix(self):
        """Get the world transformation matrix (for advanced rendering)."""
        if self._dirty or self._world_matrix is None:
            # Simple 2D transformation matrix calculation
            cos_r = math.cos(math.radians(self.rotation))
            sin_r = math.sin(math.radians(self.rotation))
            
            # 3x3 transformation matrix for 2D
            self._world_matrix = [
                [self.scale_x * cos_r, -self.scale_x * sin_r, self.x],
                [self.scale_y * sin_r,  self.scale_y * cos_r, self.y],
                [0, 0, 1]
            ]
            self._dirty = False
        
        return self._world_matrix
    
    def copy(self) -> 'Transform':
        """Create a copy of this transform."""
        return Transform(self.x, self.y, self.rotation, self.scale_x, self.scale_y)
    
    def __repr__(self):
        return f"Transform(pos=({self.x:.2f}, {self.y:.2f}), rot={self.rotation:.2f}°, scale=({self.scale_x:.2f}, {self.scale_y:.2f}))"

# --- Collision System ---

class BoundingBox:
    """Represents an axis-aligned bounding box for collision detection."""
    
    def __init__(self, x: float, y: float, width: float, height: float):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
    
    @property
    def left(self) -> float:
        return self.x
    
    @property
    def right(self) -> float:
        return self.x + self.width
    
    @property
    def top(self) -> float:
        return self.y
    
    @property
    def bottom(self) -> float:
        return self.y + self.height
    
    @property
    def center_x(self) -> float:
        return self.x + self.width / 2
    
    @property
    def center_y(self) -> float:
        return self.y + self.height / 2
    
    def contains_point(self, x: float, y: float) -> bool:
        """Check if a point is inside this bounding box."""
        return (self.left <= x <= self.right and 
                self.top <= y <= self.bottom)
    
    def intersects(self, other: 'BoundingBox') -> bool:
        """Check if this bounding box intersects with another."""
        return not (self.right < other.left or 
                   self.left > other.right or 
                   self.bottom < other.top or 
                   self.top > other.bottom)
    
    def get_intersection(self, other: 'BoundingBox') -> Optional['BoundingBox']:
        """Get the intersection rectangle with another bounding box."""
        if not self.intersects(other):
            return None
        
        left = max(self.left, other.left)
        top = max(self.top, other.top)
        right = min(self.right, other.right)
        bottom = min(self.bottom, other.bottom)
        
        return BoundingBox(left, top, right - left, bottom - top)
    
    def get_overlap_area(self, other: 'BoundingBox') -> float:
        """Get the area of overlap with another bounding box."""
        intersection = self.get_intersection(other)
        return intersection.width * intersection.height if intersection else 0.0
    
    def expand(self, amount: float) -> 'BoundingBox':
        """Create a new bounding box expanded by the given amount."""
        return BoundingBox(
            self.x - amount,
            self.y - amount,
            self.width + 2 * amount,
            self.height + 2 * amount
        )
    
    def __repr__(self):
        return f"BoundingBox(x={self.x:.2f}, y={self.y:.2f}, w={self.width:.2f}, h={self.height:.2f})"

class CollisionInfo:
    """Contains information about a collision between two game objects."""
    
    def __init__(self, object_a, object_b, overlap_area: float = 0.0, collision_point: Tuple[float, float] = None):
        self.object_a = object_a
        self.object_b = object_b
        self.overlap_area = overlap_area
        self.collision_point = collision_point or (0.0, 0.0)
        self.collision_normal = (0.0, 0.0)  # Direction of collision
        self.penetration_depth = 0.0
    
    def calculate_collision_details(self):
        """Calculate detailed collision information."""
        bbox_a = self.object_a.get_bounding_box()
        bbox_b = self.object_b.get_bounding_box()
        
        if bbox_a and bbox_b:
            intersection = bbox_a.get_intersection(bbox_b)
            if intersection:
                self.overlap_area = intersection.width * intersection.height
                self.collision_point = (intersection.center_x, intersection.center_y)
                
                # Calculate collision normal (direction from A to B)
                dx = bbox_b.center_x - bbox_a.center_x
                dy = bbox_b.center_y - bbox_a.center_y
                length = math.sqrt(dx * dx + dy * dy)
                
                if length > 0:
                    self.collision_normal = (dx / length, dy / length)
                    self.penetration_depth = min(intersection.width, intersection.height)
    
    def __repr__(self):
        return f"CollisionInfo({self.object_a} <-> {self.object_b}, area={self.overlap_area:.2f})"

# --- Sprite System ---

class Sprite:
    """Represents a sprite for rendering game objects."""
    
    def __init__(self, sprite_path: str = "", width: float = 32.0, height: float = 32.0):
        self.sprite_path = sprite_path
        self.width = width
        self.height = height
        self.offset_x = 0.0  # Offset from transform position
        self.offset_y = 0.0
        self.tint_color = (255, 255, 255, 255)  # RGBA
        self.flip_horizontal = False
        self.flip_vertical = False
        self.visible = True
        
        # Animation support
        self.frame_count = 1
        self.current_frame = 0
        self.animation_speed = 0.0  # Frames per second
        self.animation_time = 0.0
        self.loop_animation = True
    
    def set_sprite(self, sprite_path: str, width: float = None, height: float = None):
        """Set the sprite image and optionally its dimensions."""
        self.sprite_path = sprite_path
        if width is not None:
            self.width = width
        if height is not None:
            self.height = height
    
    def set_size(self, width: float, height: float):
        """Set the sprite dimensions."""
        self.width = width
        self.height = height
    
    def set_offset(self, offset_x: float, offset_y: float):
        """Set the offset from the transform position."""
        self.offset_x = offset_x
        self.offset_y = offset_y
    
    def set_tint(self, r: int, g: int, b: int, a: int = 255):
        """Set the tint color (RGBA values 0-255)."""
        self.tint_color = (r, g, b, a)
    
    def set_flip(self, horizontal: bool, vertical: bool = False):
        """Set sprite flipping."""
        self.flip_horizontal = horizontal
        self.flip_vertical = vertical
    
    def set_animation(self, frame_count: int, animation_speed: float, loop: bool = True):
        """Set up sprite animation."""
        self.frame_count = max(1, frame_count)
        self.animation_speed = animation_speed
        self.loop_animation = loop
        self.current_frame = 0
        self.animation_time = 0.0
    
    def update_animation(self, delta_time: float):
        """Update sprite animation."""
        if self.frame_count <= 1 or self.animation_speed <= 0:
            return
        
        self.animation_time += delta_time
        frame_duration = 1.0 / self.animation_speed
        
        while self.animation_time >= frame_duration:
            self.animation_time -= frame_duration
            self.current_frame += 1
            
            if self.current_frame >= self.frame_count:
                if self.loop_animation:
                    self.current_frame = 0
                else:
                    self.current_frame = self.frame_count - 1
                    break  # Stop updating if not looping
    
    def get_render_bounds(self, transform: Transform) -> BoundingBox:
        """Get the bounds where this sprite should be rendered."""
        x = transform.x + self.offset_x - (self.width * transform.scale_x) / 2
        y = transform.y + self.offset_y - (self.height * transform.scale_y) / 2
        width = self.width * transform.scale_x
        height = self.height * transform.scale_y
        
        return BoundingBox(x, y, width, height)
    
    def copy(self) -> 'Sprite':
        """Create a copy of this sprite."""
        sprite = Sprite(self.sprite_path, self.width, self.height)
        sprite.offset_x = self.offset_x
        sprite.offset_y = self.offset_y
        sprite.tint_color = self.tint_color
        sprite.flip_horizontal = self.flip_horizontal
        sprite.flip_vertical = self.flip_vertical
        sprite.visible = self.visible
        sprite.frame_count = self.frame_count
        sprite.current_frame = self.current_frame
        sprite.animation_speed = self.animation_speed
        sprite.animation_time = self.animation_time
        sprite.loop_animation = self.loop_animation
        return sprite
    
    def __repr__(self):
        return f"Sprite(path='{self.sprite_path}', size=({self.width:.1f}x{self.height:.1f}), frame={self.current_frame}/{self.frame_count})"

# --- Base Game Object ---

class GameObject(Value):
    """Base class for all game objects in Engage."""
    
    def __init__(self, object_type: str = "GameObject", object_id: str = None):
        super().__init__()
        self.object_type = object_type
        self.object_id = object_id or str(uuid.uuid4())
        
        # Core components
        self.transform = Transform()
        self.sprite = Sprite()
        
        # Collision properties
        self.collision_enabled = True
        self.collision_width = 32.0
        self.collision_height = 32.0
        self.collision_offset_x = 0.0
        self.collision_offset_y = 0.0
        self.is_trigger = False  # If true, collision events fire but no physics response
        
        # Hierarchy management
        self.parent = None
        self.children = []
        
        # Game state
        self.active = True
        self.visible = True
        self.destroy_on_next_frame = False
        
        # Event handling
        self.event_handlers = {}  # event_type -> list of callback functions
        
        # Game loop hooks
        self.update_enabled = True
        self.render_enabled = True
        
        # Tags for categorization and searching
        self.tags = set()
    
    def __repr__(self):
        return f"<{self.object_type} id='{self.object_id}' at ({self.transform.x:.1f}, {self.transform.y:.1f})>"
    
    @property
    def value(self):
        """Return a string representation for use with print and other functions."""
        return f"{self.object_type}('{self.object_id}')"
    
    def is_true(self):
        """Game objects are considered 'true' if they are active."""
        return self.active
    
    # --- Transform Properties ---
    
    def set_position(self, x: float, y: float):
        """Set the position of the game object."""
        self.transform.set_position(x, y)
    
    def get_position(self) -> Tuple[float, float]:
        """Get the position of the game object."""
        return (self.transform.x, self.transform.y)
    
    def set_rotation(self, rotation: float):
        """Set the rotation of the game object in degrees."""
        self.transform.set_rotation(rotation)
    
    def get_rotation(self) -> float:
        """Get the rotation of the game object in degrees."""
        return self.transform.rotation
    
    def set_scale(self, scale_x: float, scale_y: float = None):
        """Set the scale of the game object."""
        self.transform.set_scale(scale_x, scale_y)
    
    def get_scale(self) -> Tuple[float, float]:
        """Get the scale of the game object."""
        return (self.transform.scale_x, self.transform.scale_y)
    
    def translate(self, dx: float, dy: float):
        """Move the game object by the given offset."""
        self.transform.translate(dx, dy)
    
    def rotate(self, degrees: float):
        """Rotate the game object by the given degrees."""
        self.transform.rotate(degrees)
    
    def scale(self, factor_x: float, factor_y: float = None):
        """Scale the game object by the given factors."""
        self.transform.scale(factor_x, factor_y)
    
    # --- Sprite Properties ---
    
    def set_sprite(self, sprite_path: str, width: float = None, height: float = None):
        """Set the sprite for this game object."""
        self.sprite.set_sprite(sprite_path, width, height)
        
        # Auto-adjust collision box to sprite size if not manually set
        if width and height and (self.collision_width == 32.0 and self.collision_height == 32.0):
            self.set_collision_box(width, height)
    
    def get_sprite_path(self) -> str:
        """Get the current sprite path."""
        return self.sprite.sprite_path
    
    def set_sprite_size(self, width: float, height: float):
        """Set the sprite size."""
        self.sprite.set_size(width, height)
    
    def set_sprite_offset(self, offset_x: float, offset_y: float):
        """Set the sprite offset from the transform position."""
        self.sprite.set_offset(offset_x, offset_y)
    
    def set_sprite_tint(self, r: int, g: int, b: int, a: int = 255):
        """Set the sprite tint color."""
        self.sprite.set_tint(r, g, b, a)
    
    def set_sprite_flip(self, horizontal: bool, vertical: bool = False):
        """Set sprite flipping."""
        self.sprite.set_flip(horizontal, vertical)
    
    def set_sprite_animation(self, frame_count: int, animation_speed: float, loop: bool = True):
        """Set up sprite animation."""
        self.sprite.set_animation(frame_count, animation_speed, loop)
    
    # --- Collision System ---
    
    def set_collision_box(self, width: float, height: float, offset_x: float = 0.0, offset_y: float = 0.0):
        """Set the collision box dimensions and offset."""
        self.collision_width = width
        self.collision_height = height
        self.collision_offset_x = offset_x
        self.collision_offset_y = offset_y
    
    def get_bounding_box(self) -> BoundingBox:
        """Get the current bounding box for collision detection."""
        if not self.collision_enabled:
            return None
        
        x = self.transform.x + self.collision_offset_x - (self.collision_width * self.transform.scale_x) / 2
        y = self.transform.y + self.collision_offset_y - (self.collision_height * self.transform.scale_y) / 2
        width = self.collision_width * self.transform.scale_x
        height = self.collision_height * self.transform.scale_y
        
        return BoundingBox(x, y, width, height)
    
    def collides_with(self, other: 'GameObject') -> bool:
        """Check if this game object collides with another."""
        if not self.collision_enabled or not other.collision_enabled:
            return False
        
        if not self.active or not other.active:
            return False
        
        bbox_self = self.get_bounding_box()
        bbox_other = other.get_bounding_box()
        
        if not bbox_self or not bbox_other:
            return False
        
        return bbox_self.intersects(bbox_other)
    
    def get_collision_info(self, other: 'GameObject') -> Optional[CollisionInfo]:
        """Get detailed collision information with another game object."""
        if not self.collides_with(other):
            return None
        
        collision_info = CollisionInfo(self, other)
        collision_info.calculate_collision_details()
        return collision_info
    
    def distance_to(self, other: 'GameObject') -> float:
        """Calculate distance to another game object."""
        return self.transform.distance_to(other.transform)
    
    def angle_to(self, other: 'GameObject') -> float:
        """Calculate angle to another game object in degrees."""
        return self.transform.angle_to(other.transform)
    
    # --- Hierarchy Management ---
    
    def add_child(self, child_object: 'GameObject'):
        """Add a child game object."""
        if not isinstance(child_object, GameObject):
            raise TypeError("Child must be a GameObject")
        
        if child_object.parent:
            child_object.parent.remove_child(child_object)
        
        child_object.parent = self
        self.children.append(child_object)
    
    def remove_child(self, child_object: 'GameObject'):
        """Remove a child game object."""
        if child_object in self.children:
            child_object.parent = None
            self.children.remove(child_object)
    
    def get_children(self) -> List['GameObject']:
        """Get all child game objects."""
        return self.children.copy()
    
    def get_parent(self) -> Optional['GameObject']:
        """Get the parent game object."""
        return self.parent
    
    def get_root(self) -> 'GameObject':
        """Get the root game object in the hierarchy."""
        current = self
        while current.parent:
            current = current.parent
        return current
    
    def find_child_by_id(self, object_id: str) -> Optional['GameObject']:
        """Find a child game object by its ID (recursive search)."""
        for child in self.children:
            if child.object_id == object_id:
                return child
            found = child.find_child_by_id(object_id)
            if found:
                return found
        return None
    
    def find_children_by_tag(self, tag: str) -> List['GameObject']:
        """Find all child game objects with a specific tag (recursive search)."""
        results = []
        for child in self.children:
            if tag in child.tags:
                results.append(child)
            results.extend(child.find_children_by_tag(tag))
        return results
    
    # --- Tag System ---
    
    def add_tag(self, tag: str):
        """Add a tag to this game object."""
        self.tags.add(tag)
    
    def remove_tag(self, tag: str):
        """Remove a tag from this game object."""
        self.tags.discard(tag)
    
    def has_tag(self, tag: str) -> bool:
        """Check if this game object has a specific tag."""
        return tag in self.tags
    
    def get_tags(self) -> set:
        """Get all tags for this game object."""
        return self.tags.copy()
    
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
    
    def trigger_event(self, event: GameEvent, context=None):
        """Trigger an event on this game object."""
        if not self.active:
            return False  # Inactive objects don't handle events
        
        event.source_object = self
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
            event_table.set("object_id", String(self.object_id))
            
            # Add event-specific data
            for key, value in event.data.items():
                if isinstance(value, str):
                    event_table.set(key, String(value))
                elif isinstance(value, (int, float)):
                    event_table.set(key, Number(value))
            
            # Execute the handler function with the event data
            # This would need proper integration with the interpreter's execute_user_function
            pass
    
    # --- Game Loop Integration ---
    
    def update(self, delta_time: float):
        """Update the game object. Called every frame by the game loop."""
        if not self.active or not self.update_enabled:
            return
        
        # Update sprite animation
        self.sprite.update_animation(delta_time)
        
        # Trigger update event
        event = GameEvent("update", self, {"delta_time": delta_time})
        self.trigger_event(event)
        
        # Update children
        for child in self.children:
            if child.active:
                child.update(delta_time)
    
    def render(self, renderer=None):
        """Render the game object. Called every frame by the game loop."""
        if not self.active or not self.visible or not self.render_enabled:
            return
        
        # Trigger render event
        event = GameEvent("render", self, {"renderer": renderer})
        self.trigger_event(event)
        
        # Render sprite if visible
        if self.sprite.visible and renderer:
            render_data = self.prepare_render_data()
            renderer.render_game_object(self, render_data)
        else:
            # Default console-based rendering for testing
            self._console_render()
        
        # Render children
        for child in self.children:
            if child.active and child.visible:
                child.render(renderer)
    
    def prepare_render_data(self) -> Dict[str, Any]:
        """Prepare data needed for rendering this game object."""
        return {
            'object_type': self.object_type,
            'object_id': self.object_id,
            'transform': {
                'x': self.transform.x,
                'y': self.transform.y,
                'rotation': self.transform.rotation,
                'scale_x': self.transform.scale_x,
                'scale_y': self.transform.scale_y
            },
            'sprite': {
                'path': self.sprite.sprite_path,
                'width': self.sprite.width,
                'height': self.sprite.height,
                'offset_x': self.sprite.offset_x,
                'offset_y': self.sprite.offset_y,
                'tint_color': self.sprite.tint_color,
                'flip_horizontal': self.sprite.flip_horizontal,
                'flip_vertical': self.sprite.flip_vertical,
                'current_frame': self.sprite.current_frame,
                'frame_count': self.sprite.frame_count
            },
            'collision': {
                'enabled': self.collision_enabled,
                'width': self.collision_width,
                'height': self.collision_height,
                'offset_x': self.collision_offset_x,
                'offset_y': self.collision_offset_y,
                'is_trigger': self.is_trigger
            },
            'visible': self.visible,
            'active': self.active,
            'tags': list(self.tags)
        }
    
    def _console_render(self):
        """Basic console rendering for testing purposes."""
        indent = "  " * self._get_hierarchy_depth()
        sprite_info = f" sprite='{self.sprite.sprite_path}'" if self.sprite.sprite_path else ""
        collision_info = f" collision=({self.collision_width:.0f}x{self.collision_height:.0f})" if self.collision_enabled else ""
        tags_info = f" tags={list(self.tags)}" if self.tags else ""
        
        print(f"{indent}{self.object_type} '{self.object_id}' at ({self.transform.x:.1f}, {self.transform.y:.1f}) "
              f"rot={self.transform.rotation:.1f}° scale=({self.transform.scale_x:.1f}, {self.transform.scale_y:.1f})"
              f"{sprite_info}{collision_info}{tags_info}")
    
    def _get_hierarchy_depth(self) -> int:
        """Get the depth of this game object in the hierarchy."""
        depth = 0
        current = self.parent
        while current:
            depth += 1
            current = current.parent
        return depth
    
    # --- Lifecycle Management ---
    
    def destroy(self):
        """Mark this game object for destruction."""
        self.destroy_on_next_frame = True
        
        # Trigger destroy event
        event = GameEvent("destroy", self)
        self.trigger_event(event)
        
        # Remove from parent
        if self.parent:
            self.parent.remove_child(self)
        
        # Destroy children
        for child in self.children.copy():
            child.destroy()
    
    def is_destroyed(self) -> bool:
        """Check if this game object is marked for destruction."""
        return self.destroy_on_next_frame
    
    def clone(self) -> 'GameObject':
        """Create a copy of this game object."""
        clone = GameObject(self.object_type)
        
        # Copy transform
        clone.transform = self.transform.copy()
        
        # Copy sprite
        clone.sprite = self.sprite.copy()
        
        # Copy collision properties
        clone.collision_enabled = self.collision_enabled
        clone.collision_width = self.collision_width
        clone.collision_height = self.collision_height
        clone.collision_offset_x = self.collision_offset_x
        clone.collision_offset_y = self.collision_offset_y
        clone.is_trigger = self.is_trigger
        
        # Copy state
        clone.active = self.active
        clone.visible = self.visible
        clone.update_enabled = self.update_enabled
        clone.render_enabled = self.render_enabled
        
        # Copy tags
        clone.tags = self.tags.copy()
        
        # Note: Event handlers and children are not copied to avoid complex reference issues
        
        return clone
# --- Game Object Manager ---

class GameObjectManager:
    """Manages the lifecycle and interactions of game objects."""
    
    def __init__(self):
        self.objects = {}  # object_id -> game_object
        self.objects_by_tag = {}  # tag -> set of game_objects
        self.root_objects = []  # Objects without parents
        self.collision_pairs = []  # Pairs of objects that can collide
        self.event_queue = []
        self.renderer = None
        
        # Performance optimization
        self.spatial_grid = {}  # Simple spatial partitioning for collision detection
        self.grid_size = 100  # Size of each grid cell
        
        # Game loop timing
        self.last_update_time = 0.0
        self.target_fps = 60.0
        self.frame_count = 0
    
    def register_object(self, game_object: GameObject):
        """Register a game object with the manager."""
        self.objects[game_object.object_id] = game_object
        
        if not game_object.parent:
            self.root_objects.append(game_object)
        
        # Add to tag index
        for tag in game_object.tags:
            if tag not in self.objects_by_tag:
                self.objects_by_tag[tag] = set()
            self.objects_by_tag[tag].add(game_object)
        
        # Update spatial grid
        self._update_spatial_grid(game_object)
    
    def unregister_object(self, game_object: GameObject):
        """Unregister a game object from the manager."""
        if game_object.object_id in self.objects:
            del self.objects[game_object.object_id]
        
        if game_object in self.root_objects:
            self.root_objects.remove(game_object)
        
        # Remove from tag index
        for tag in game_object.tags:
            if tag in self.objects_by_tag:
                self.objects_by_tag[tag].discard(game_object)
                if not self.objects_by_tag[tag]:
                    del self.objects_by_tag[tag]
        
        # Remove from parent if it has one
        if game_object.parent:
            game_object.parent.remove_child(game_object)
        
        # Remove from spatial grid
        self._remove_from_spatial_grid(game_object)
    
    def get_object(self, object_id: str) -> Optional[GameObject]:
        """Get a game object by its ID."""
        return self.objects.get(object_id)
    
    def get_objects_by_tag(self, tag: str) -> List[GameObject]:
        """Get all game objects with a specific tag."""
        return list(self.objects_by_tag.get(tag, set()))
    
    def get_objects_by_type(self, object_type: str) -> List[GameObject]:
        """Get all game objects of a specific type."""
        return [obj for obj in self.objects.values() if obj.object_type == object_type]
    
    def find_objects_in_area(self, x: float, y: float, width: float, height: float) -> List[GameObject]:
        """Find all game objects within a rectangular area."""
        area_bbox = BoundingBox(x, y, width, height)
        results = []
        
        for game_object in self.objects.values():
            if not game_object.active or not game_object.collision_enabled:
                continue
            
            obj_bbox = game_object.get_bounding_box()
            if obj_bbox and area_bbox.intersects(obj_bbox):
                results.append(game_object)
        
        return results
    
    def find_objects_in_radius(self, center_x: float, center_y: float, radius: float) -> List[GameObject]:
        """Find all game objects within a circular area."""
        results = []
        radius_squared = radius * radius
        
        for game_object in self.objects.values():
            if not game_object.active:
                continue
            
            dx = game_object.transform.x - center_x
            dy = game_object.transform.y - center_y
            distance_squared = dx * dx + dy * dy
            
            if distance_squared <= radius_squared:
                results.append(game_object)
        
        return results
    
    def find_nearest_object(self, x: float, y: float, max_distance: float = float('inf'), 
                           exclude_object: GameObject = None, tag_filter: str = None) -> Optional[GameObject]:
        """Find the nearest game object to a point."""
        nearest = None
        nearest_distance = max_distance
        
        for game_object in self.objects.values():
            if not game_object.active or game_object == exclude_object:
                continue
            
            if tag_filter and tag_filter not in game_object.tags:
                continue
            
            dx = game_object.transform.x - x
            dy = game_object.transform.y - y
            distance = math.sqrt(dx * dx + dy * dy)
            
            if distance < nearest_distance:
                nearest = game_object
                nearest_distance = distance
        
        return nearest
    
    def _update_spatial_grid(self, game_object: GameObject):
        """Update the spatial grid for collision optimization."""
        if not game_object.collision_enabled:
            return
        
        bbox = game_object.get_bounding_box()
        if not bbox:
            return
        
        # Calculate grid cells this object occupies
        min_grid_x = int(bbox.left // self.grid_size)
        max_grid_x = int(bbox.right // self.grid_size)
        min_grid_y = int(bbox.top // self.grid_size)
        max_grid_y = int(bbox.bottom // self.grid_size)
        
        # Add to grid cells
        for grid_x in range(min_grid_x, max_grid_x + 1):
            for grid_y in range(min_grid_y, max_grid_y + 1):
                grid_key = (grid_x, grid_y)
                if grid_key not in self.spatial_grid:
                    self.spatial_grid[grid_key] = set()
                self.spatial_grid[grid_key].add(game_object)
    
    def _remove_from_spatial_grid(self, game_object: GameObject):
        """Remove a game object from the spatial grid."""
        # Remove from all grid cells (inefficient but simple)
        for grid_cell in self.spatial_grid.values():
            grid_cell.discard(game_object)
    
    def _get_potential_collision_pairs(self) -> List[Tuple[GameObject, GameObject]]:
        """Get pairs of objects that might collide using spatial partitioning."""
        pairs = set()
        
        for grid_cell in self.spatial_grid.values():
            objects_in_cell = list(grid_cell)
            for i in range(len(objects_in_cell)):
                for j in range(i + 1, len(objects_in_cell)):
                    obj_a, obj_b = objects_in_cell[i], objects_in_cell[j]
                    if obj_a.active and obj_b.active and obj_a.collision_enabled and obj_b.collision_enabled:
                        pairs.add((obj_a, obj_b))
        
        return list(pairs)
    
    def check_collisions(self, context=None):
        """Check for collisions between all game objects."""
        collision_pairs = self._get_potential_collision_pairs()
        
        for obj_a, obj_b in collision_pairs:
            if obj_a.collides_with(obj_b):
                collision_info = obj_a.get_collision_info(obj_b)
                
                # Trigger collision events
                event_a = GameEvent("collision", obj_a, {
                    "other_object": obj_b,
                    "collision_info": collision_info
                })
                event_b = GameEvent("collision", obj_b, {
                    "other_object": obj_a,
                    "collision_info": collision_info
                })
                
                obj_a.trigger_event(event_a, context)
                obj_b.trigger_event(event_b, context)
    
    def queue_event(self, event: GameEvent):
        """Queue an event for processing."""
        self.event_queue.append(event)
    
    def process_events(self, context=None):
        """Process all queued events."""
        while self.event_queue:
            event = self.event_queue.pop(0)
            
            if event.source_object:
                event.source_object.trigger_event(event, context)
            else:
                # Broadcast event to all objects
                for game_object in self.objects.values():
                    if game_object.active:
                        game_object.trigger_event(event, context)
                        if event.handled:
                            break
    
    def update_all(self, delta_time: float, context=None):
        """Update all game objects."""
        # Update root objects (which will update their children)
        for root_object in self.root_objects:
            if root_object.active:
                root_object.update(delta_time)
        
        # Update spatial grid for moved objects
        for game_object in self.objects.values():
            if game_object.active:
                self._update_spatial_grid(game_object)
        
        # Check collisions
        self.check_collisions(context)
        
        # Process events
        self.process_events(context)
        
        # Clean up destroyed objects
        self._cleanup_destroyed_objects()
        
        self.frame_count += 1
    
    def render_all(self):
        """Render all game objects."""
        # Sort root objects by render order (could be based on z-order, layer, etc.)
        sorted_roots = sorted(self.root_objects, key=lambda obj: getattr(obj, 'render_order', 0))
        
        for root_object in sorted_roots:
            if root_object.active and root_object.visible:
                root_object.render(self.renderer)
    
    def _cleanup_destroyed_objects(self):
        """Remove objects marked for destruction."""
        destroyed_objects = [obj for obj in self.objects.values() if obj.is_destroyed()]
        
        for obj in destroyed_objects:
            self.unregister_object(obj)
    
    def set_renderer(self, renderer):
        """Set the renderer for all game objects."""
        self.renderer = renderer
    
    def get_frame_count(self) -> int:
        """Get the current frame count."""
        return self.frame_count
    
    def get_object_count(self) -> int:
        """Get the total number of active game objects."""
        return len(self.objects)
    
    def clear_all(self):
        """Clear all game objects."""
        for obj in list(self.objects.values()):
            self.unregister_object(obj)
        
        self.objects.clear()
        self.objects_by_tag.clear()
        self.root_objects.clear()
        self.spatial_grid.clear()
        self.event_queue.clear()
        self.frame_count = 0

# --- Game Loop Integration ---

class GameLoop:
    """Basic game loop implementation for Engage games."""
    
    def __init__(self, game_manager: GameObjectManager):
        self.game_manager = game_manager
        self.running = False
        self.paused = False
        self.target_fps = 60.0
        self.delta_time = 0.0
        self.last_frame_time = 0.0
        self.frame_count = 0
        
        # Performance tracking
        self.fps_counter = 0
        self.fps_timer = 0.0
        self.current_fps = 0.0
        
        # Game loop hooks
        self.pre_update_hooks = []
        self.post_update_hooks = []
        self.pre_render_hooks = []
        self.post_render_hooks = []
    
    def add_pre_update_hook(self, hook_function):
        """Add a function to be called before each update."""
        self.pre_update_hooks.append(hook_function)
    
    def add_post_update_hook(self, hook_function):
        """Add a function to be called after each update."""
        self.post_update_hooks.append(hook_function)
    
    def add_pre_render_hook(self, hook_function):
        """Add a function to be called before each render."""
        self.pre_render_hooks.append(hook_function)
    
    def add_post_render_hook(self, hook_function):
        """Add a function to be called after each render."""
        self.post_render_hooks.append(hook_function)
    
    def start(self):
        """Start the game loop."""
        self.running = True
        self.last_frame_time = self._get_time()
        
        while self.running:
            current_time = self._get_time()
            self.delta_time = current_time - self.last_frame_time
            self.last_frame_time = current_time
            
            # Cap delta time to prevent large jumps
            self.delta_time = min(self.delta_time, 1.0 / 30.0)  # Max 30 FPS minimum
            
            if not self.paused:
                self.update()
                self.render()
            
            self.frame_count += 1
            self._update_fps_counter()
            self._limit_frame_rate()
    
    def stop(self):
        """Stop the game loop."""
        self.running = False
    
    def pause(self):
        """Pause the game loop."""
        self.paused = True
    
    def resume(self):
        """Resume the game loop."""
        self.paused = False
    
    def update(self):
        """Update game state."""
        # Execute pre-update hooks
        for hook in self.pre_update_hooks:
            try:
                hook(self.delta_time)
            except Exception as e:
                print(f"Error in pre-update hook: {e}")
        
        # Update game objects
        self.game_manager.update_all(self.delta_time)
        
        # Execute post-update hooks
        for hook in self.post_update_hooks:
            try:
                hook(self.delta_time)
            except Exception as e:
                print(f"Error in post-update hook: {e}")
    
    def render(self):
        """Render game state."""
        # Execute pre-render hooks
        for hook in self.pre_render_hooks:
            try:
                hook()
            except Exception as e:
                print(f"Error in pre-render hook: {e}")
        
        # Render game objects
        self.game_manager.render_all()
        
        # Execute post-render hooks
        for hook in self.post_render_hooks:
            try:
                hook()
            except Exception as e:
                print(f"Error in post-render hook: {e}")
    
    def _get_time(self) -> float:
        """Get current time in seconds."""
        import time
        return time.time()
    
    def _update_fps_counter(self):
        """Update FPS counter."""
        self.fps_counter += 1
        self.fps_timer += self.delta_time
        
        if self.fps_timer >= 1.0:
            self.current_fps = self.fps_counter / self.fps_timer
            self.fps_counter = 0
            self.fps_timer = 0.0
    
    def _limit_frame_rate(self):
        """Limit frame rate to target FPS."""
        if self.target_fps <= 0:
            return
        
        target_frame_time = 1.0 / self.target_fps
        current_frame_time = self._get_time() - self.last_frame_time
        
        if current_frame_time < target_frame_time:
            import time
            time.sleep(target_frame_time - current_frame_time)
    
    def get_fps(self) -> float:
        """Get current FPS."""
        return self.current_fps
    
    def set_target_fps(self, fps: float):
        """Set target FPS."""
        self.target_fps = max(0, fps)

# --- Global Game Manager Instance ---
game_manager = GameObjectManager()

# --- Built-in Functions for Engage Integration ---

def create_game_object_builtin(args):
    """Built-in function to create a game object."""
    from engage_interpreter import String
    
    object_type = "GameObject"
    if len(args) > 0:
        # Handle both real String objects and mock objects for testing
        if hasattr(args[0], 'value'):
            object_type = args[0].value
        elif isinstance(args[0], str):
            object_type = args[0]
    
    game_object = GameObject(object_type)
    game_manager.register_object(game_object)
    
    return game_object

def game_set_position_builtin(args):
    """Built-in function to set game object position."""
    from engage_interpreter import Number
    
    if len(args) != 3:
        raise TypeError("game_set_position requires 3 arguments: object, x, y")
    
    game_object, x, y = args
    
    if not isinstance(game_object, GameObject):
        raise TypeError("First argument must be a GameObject")
    
    # Handle both real Number objects and mock objects for testing
    if not (hasattr(x, 'value') and hasattr(y, 'value')):
        raise TypeError("Position coordinates must be numbers")
    
    game_object.set_position(x.value, y.value)
    return game_object

def game_set_sprite_builtin(args):
    """Built-in function to set game object sprite."""
    from engage_interpreter import String, Number
    
    if len(args) < 2:
        raise TypeError("game_set_sprite requires at least 2 arguments: object, sprite_path")
    
    game_object = args[0]
    sprite_path = args[1]
    
    if not isinstance(game_object, GameObject):
        raise TypeError("First argument must be a GameObject")
    
    # Handle both real String objects and mock objects for testing
    if not hasattr(sprite_path, 'value'):
        raise TypeError("Sprite path must be a string")
    
    width = args[2].value if len(args) > 2 and hasattr(args[2], 'value') else None
    height = args[3].value if len(args) > 3 and hasattr(args[3], 'value') else None
    
    game_object.set_sprite(sprite_path.value, width, height)
    return game_object

def game_check_collision_builtin(args):
    """Built-in function to check collision between two game objects."""
    from engage_interpreter import Number
    
    if len(args) != 2:
        raise TypeError("game_check_collision requires 2 arguments: object1, object2")
    
    obj1, obj2 = args
    
    if not isinstance(obj1, GameObject) or not isinstance(obj2, GameObject):
        raise TypeError("Both arguments must be GameObjects")
    
    return Number(1) if obj1.collides_with(obj2) else Number(0)

def game_add_tag_builtin(args):
    """Built-in function to add a tag to a game object."""
    from engage_interpreter import String
    
    if len(args) != 2:
        raise TypeError("game_add_tag requires 2 arguments: object, tag")
    
    game_object, tag = args
    
    if not isinstance(game_object, GameObject):
        raise TypeError("First argument must be a GameObject")
    
    # Handle both real String objects and mock objects for testing
    if not hasattr(tag, 'value'):
        raise TypeError("Tag must be a string")
    
    game_object.add_tag(tag.value)
    return game_object

def game_find_objects_by_tag_builtin(args):
    """Built-in function to find objects by tag."""
    from engage_interpreter import String, Vector
    
    if len(args) != 1:
        raise TypeError("game_find_objects_by_tag requires 1 argument: tag")
    
    tag = args[0]
    
    if not hasattr(tag, 'value'):
        raise TypeError("Tag must be a string")
    
    objects = game_manager.get_objects_by_tag(tag.value)
    
    # Return as Vector
    result = Vector()
    for obj in objects:
        result.push(obj)
    
    return result

# --- Export built-in functions for interpreter integration ---
GAME_BUILTIN_FUNCTIONS = {
    'create_game_object': BuiltInFunction('create_game_object', create_game_object_builtin),
    'game_set_position': BuiltInFunction('game_set_position', game_set_position_builtin),
    'game_set_sprite': BuiltInFunction('game_set_sprite', game_set_sprite_builtin),
    'game_check_collision': BuiltInFunction('game_check_collision', game_check_collision_builtin),
    'game_add_tag': BuiltInFunction('game_add_tag', game_add_tag_builtin),
    'game_find_objects_by_tag': BuiltInFunction('game_find_objects_by_tag', game_find_objects_by_tag_builtin),
}