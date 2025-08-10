# engage_modules.py
# Module system foundation for the Engage programming language

import os
import sys
from pathlib import Path
from typing import Dict, Set, List, Optional, Any
from dataclasses import dataclass, field

from engage_lexer import Lexer
from engage_parser import Parser


@dataclass
class ModuleInfo:
    """Information about a loaded module."""
    name: str
    file_path: str
    symbol_table: Any = None  # Will be SymbolTable when created
    exports: Dict[str, Any] = field(default_factory=dict)  # Will be Dict[str, Value]
    is_loaded: bool = False
    is_loading: bool = False  # For circular dependency detection
    dependencies: Set[str] = field(default_factory=set)


class CircularDependencyError(Exception):
    """Raised when a circular dependency is detected."""
    def __init__(self, cycle_path: List[str]):
        self.cycle_path = cycle_path
        cycle_str = " -> ".join(cycle_path + [cycle_path[0]])
        super().__init__(f"Circular dependency detected: {cycle_str}")


class ModuleNotFoundError(Exception):
    """Raised when a module cannot be found."""
    def __init__(self, module_name: str, search_paths: List[str]):
        self.module_name = module_name
        self.search_paths = search_paths
        paths_str = ", ".join(search_paths) if search_paths else "no search paths"
        super().__init__(f"Module '{module_name}' not found. Searched in: {paths_str}")


class ModuleResolver:
    """Handles module path resolution and file discovery."""
    
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.search_paths = [
            self.base_path,  # Current directory
            self.base_path / "modules",  # modules subdirectory
            self.base_path / "lib",  # lib subdirectory
        ]
    
    def add_search_path(self, path: str):
        """Add a directory to the module search path."""
        search_path = Path(path)
        if search_path not in self.search_paths:
            self.search_paths.append(search_path)
    
    def resolve_module_path(self, module_name: str, current_file: str = None) -> str:
        """
        Resolve a module name to an absolute file path.
        
        Args:
            module_name: The module name (e.g., "math", "utils/helpers")
            current_file: Path of the file doing the import (for relative imports)
            
        Returns:
            Absolute path to the module file
            
        Raises:
            ModuleNotFoundError: If the module cannot be found
        """
        # Handle relative imports (starting with ./ or ../)
        if module_name.startswith('./') or module_name.startswith('../'):
            if not current_file:
                raise ModuleNotFoundError(module_name, [])
            
            current_dir = Path(current_file).parent
            relative_path = current_dir / module_name
            module_path = relative_path.resolve()
            
            # Try with .engage extension
            if module_path.suffix != '.engage':
                module_path = module_path.with_suffix('.engage')
            
            if module_path.exists():
                return str(module_path)
            else:
                raise ModuleNotFoundError(module_name, [str(current_dir)])
        
        # Handle absolute imports
        module_file = module_name
        if not module_file.endswith('.engage'):
            module_file += '.engage'
        
        # Search in all search paths
        for search_path in self.search_paths:
            candidate_path = search_path / module_file
            if candidate_path.exists():
                return str(candidate_path.resolve())
        
        # Also try treating module_name as a directory with an index.engage file
        for search_path in self.search_paths:
            index_path = search_path / module_name / "index.engage"
            if index_path.exists():
                return str(index_path.resolve())
        
        raise ModuleNotFoundError(module_name, [str(p) for p in self.search_paths])


class DependencyGraph:
    """Tracks module dependencies and detects circular dependencies."""
    
    def __init__(self):
        self.dependencies: Dict[str, Set[str]] = {}
        self.loading_stack: List[str] = []
    
    def add_dependency(self, from_module: str, to_module: str):
        """Add a dependency relationship."""
        if from_module not in self.dependencies:
            self.dependencies[from_module] = set()
        self.dependencies[from_module].add(to_module)
    
    def start_loading(self, module_path: str):
        """Mark a module as starting to load."""
        if module_path in self.loading_stack:
            # Circular dependency detected
            cycle_start = self.loading_stack.index(module_path)
            cycle = self.loading_stack[cycle_start:] + [module_path]
            raise CircularDependencyError(cycle)
        
        self.loading_stack.append(module_path)
    
    def finish_loading(self, module_path: str):
        """Mark a module as finished loading."""
        if self.loading_stack and self.loading_stack[-1] == module_path:
            self.loading_stack.pop()
    
    def get_dependencies(self, module_path: str) -> Set[str]:
        """Get all dependencies of a module."""
        return self.dependencies.get(module_path, set())
    
    def has_circular_dependency(self, from_module: str, to_module: str) -> bool:
        """Check if adding a dependency would create a cycle."""
        # Simple cycle detection using DFS
        visited = set()
        
        def dfs(current: str, target: str) -> bool:
            if current == target:
                return True
            if current in visited:
                return False
            
            visited.add(current)
            for dep in self.dependencies.get(current, set()):
                if dfs(dep, target):
                    return True
            return False
        
        return dfs(to_module, from_module)


class ModuleCache:
    """Caches loaded modules to prevent re-execution."""
    
    def __init__(self):
        self.modules: Dict[str, ModuleInfo] = {}
        self.file_timestamps: Dict[str, float] = {}
    
    def get_module(self, file_path: str) -> Optional[ModuleInfo]:
        """Get a cached module if it exists and is up to date."""
        if file_path not in self.modules:
            return None
        
        module_info = self.modules[file_path]
        
        # Check if file has been modified
        try:
            current_timestamp = os.path.getmtime(file_path)
            cached_timestamp = self.file_timestamps.get(file_path, 0)
            
            if current_timestamp > cached_timestamp:
                # File has been modified, invalidate cache
                self.invalidate_module(file_path)
                return None
        except OSError:
            # File doesn't exist anymore, invalidate cache
            self.invalidate_module(file_path)
            return None
        
        return module_info
    
    def cache_module(self, file_path: str, module_info: ModuleInfo):
        """Cache a loaded module."""
        self.modules[file_path] = module_info
        try:
            self.file_timestamps[file_path] = os.path.getmtime(file_path)
        except OSError:
            self.file_timestamps[file_path] = 0
    
    def invalidate_module(self, file_path: str):
        """Remove a module from the cache."""
        self.modules.pop(file_path, None)
        self.file_timestamps.pop(file_path, None)
    
    def clear_cache(self):
        """Clear all cached modules."""
        self.modules.clear()
        self.file_timestamps.clear()
    
    def get_cached_modules(self) -> List[str]:
        """Get list of all cached module paths."""
        return list(self.modules.keys())


class ModuleNamespace:
    """Manages namespace isolation for imported modules."""
    
    def __init__(self, parent: Any = None):  # parent will be SymbolTable
        # We'll create the symbol table when we have access to the class
        self.parent = parent
        self.symbol_table = None
        self.imported_symbols: Dict[str, Any] = {}  # Will be Dict[str, Value]
        self.module_aliases: Dict[str, str] = {}  # alias -> module_path
    
    def _ensure_symbol_table(self):
        """Ensure symbol table is created (lazy initialization)."""
        if self.symbol_table is None:
            # Import here to avoid circular dependency
            from engage_interpreter import SymbolTable
            self.symbol_table = SymbolTable(self.parent)
    
    def import_symbol(self, name: str, value: Any, alias: str = None):  # value will be Value
        """Import a symbol into this namespace."""
        self._ensure_symbol_table()
        symbol_name = alias if alias else name
        self.imported_symbols[symbol_name] = value
        self.symbol_table.set(symbol_name, value)
    
    def import_module_as(self, module_path: str, alias: str, exports: Dict[str, Any]):  # exports will be Dict[str, Value]
        """Import an entire module with an alias."""
        self._ensure_symbol_table()
        from engage_interpreter import SymbolTable
        
        self.module_aliases[alias] = module_path
        
        # Create a module object that contains all exports
        module_table = SymbolTable()
        for name, value in exports.items():
            module_table.set(name, value)
        
        # For now, we'll represent the module as a special value
        # In a full implementation, this might be a ModuleValue class
        self.symbol_table.set(alias, ModuleNamespaceValue(module_table))
    
    def get_symbol(self, name: str) -> Optional[Any]:  # returns Optional[Value]
        """Get a symbol from this namespace."""
        self._ensure_symbol_table()
        return self.symbol_table.get(name)
    
    def has_symbol(self, name: str) -> bool:
        """Check if a symbol exists in this namespace."""
        self._ensure_symbol_table()
        return self.symbol_table.get(name) is not None
    
    def get_imported_symbols(self) -> Dict[str, Any]:  # returns Dict[str, Value]
        """Get all imported symbols."""
        return self.imported_symbols.copy()


class ModuleNamespaceValue:
    """Represents a module namespace as a value."""
    
    def __init__(self, symbol_table: Any):  # symbol_table will be SymbolTable
        self.symbol_table = symbol_table
    
    def __repr__(self):
        return f"<module namespace with {len(self.symbol_table.symbols)} symbols>"
    
    def get_attribute(self, name: str) -> Optional[Any]:  # returns Optional[Value]
        """Get an attribute from the module namespace."""
        return self.symbol_table.get(name)


class ModuleSystem:
    """Main module system that coordinates all module operations."""
    
    def __init__(self, base_path: str = None):
        self.resolver = ModuleResolver(base_path)
        self.cache = ModuleCache()
        self.dependency_graph = DependencyGraph()
        self.current_loading_module: Optional[str] = None
    
    def load_module(self, module_name: str, current_file: str = None) -> ModuleInfo:
        """
        Load a module and return its ModuleInfo.
        
        Args:
            module_name: Name or path of the module to load
            current_file: Path of the file requesting the import
            
        Returns:
            ModuleInfo object containing the loaded module
            
        Raises:
            ModuleNotFoundError: If the module cannot be found
            CircularDependencyError: If a circular dependency is detected
        """
        # Resolve module path
        module_path = self.resolver.resolve_module_path(module_name, current_file)
        
        # Check cache first
        cached_module = self.cache.get_module(module_path)
        if cached_module and cached_module.is_loaded:
            return cached_module
        
        # Check for circular dependencies
        if current_file:
            current_module_path = os.path.abspath(current_file)
            if self.dependency_graph.has_circular_dependency(current_module_path, module_path):
                raise CircularDependencyError([current_module_path, module_path])
            
            # Add dependency
            self.dependency_graph.add_dependency(current_module_path, module_path)
        
        # Start loading
        self.dependency_graph.start_loading(module_path)
        
        try:
            # Import SymbolTable here to avoid circular dependency
            from engage_interpreter import SymbolTable
            
            # Create module info
            module_info = ModuleInfo(
                name=module_name,
                file_path=module_path,
                symbol_table=SymbolTable(),
                is_loading=True
            )
            
            # Cache the module info (even before loading to handle recursion)
            self.cache.cache_module(module_path, module_info)
            
            # Load and parse the module file
            with open(module_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            # Tokenize and parse
            lexer = Lexer(source_code, module_path)
            tokens = lexer.tokenize()
            
            if lexer.has_errors():
                raise Exception(f"Lexical errors in module {module_name}:\n{lexer.get_error_report()}")
            
            parser = Parser(tokens, module_path, source_code)
            ast = parser.parse()
            
            if parser.error_aggregator.has_errors():
                raise Exception(f"Parse errors in module {module_name}:\n{parser.error_aggregator.format_all_errors()}")
            
            # Store the AST for later execution
            module_info.ast = ast
            module_info.is_loading = False
            module_info.is_loaded = True
            
            return module_info
            
        finally:
            self.dependency_graph.finish_loading(module_path)
    
    def execute_module(self, module_info: ModuleInfo, interpreter) -> Dict[str, Any]:
        """
        Execute a module and return its exports.
        
        Args:
            module_info: The module to execute
            interpreter: The interpreter instance to use
            
        Returns:
            Dictionary of exported symbols
        """
        if not hasattr(module_info, 'ast'):
            raise Exception(f"Module {module_info.name} was not properly loaded")
        
        # Set up module execution context
        old_file_path = interpreter.file_path
        interpreter.file_path = module_info.file_path
        
        try:
            # Initialize exports tracking in the interpreter
            interpreter.current_exports = {}
            
            # Execute the module
            interpreter.visit(module_info.ast, module_info.symbol_table)
            
            # Use explicit exports if any were registered, otherwise export all symbols
            if hasattr(interpreter, 'current_exports') and interpreter.current_exports:
                exports = interpreter.current_exports.copy()
            else:
                # Fallback: export all symbols (for backward compatibility)
                exports = {}
                for name, value in module_info.symbol_table.symbols.items():
                    exports[name] = value
            
            module_info.exports = exports
            return exports
            
        finally:
            interpreter.file_path = old_file_path
    
    def import_module(self, module_name: str, current_file: str = None, interpreter=None) -> Dict[str, Any]:
        """
        Import a module and return its exports.
        
        Args:
            module_name: Name of the module to import
            current_file: Path of the file doing the import
            interpreter: Interpreter instance for execution
            
        Returns:
            Dictionary of exported symbols
        """
        module_info = self.load_module(module_name, current_file)
        
        if not module_info.exports:
            if not interpreter:
                raise Exception("Interpreter required to execute module")
            self.execute_module(module_info, interpreter)
        
        return module_info.exports
    
    def get_module_info(self, module_path: str) -> Optional[ModuleInfo]:
        """Get information about a loaded module."""
        return self.cache.get_module(module_path)
    
    def clear_cache(self):
        """Clear the module cache."""
        self.cache.clear_cache()
    
    def get_dependency_info(self, module_path: str) -> Dict[str, Any]:
        """Get dependency information for a module."""
        return {
            'dependencies': list(self.dependency_graph.get_dependencies(module_path)),
            'is_cached': module_path in self.cache.modules,
            'loading_stack': self.dependency_graph.loading_stack.copy()
        }


# Global module system instance
_module_system = None

def get_module_system(base_path: str = None) -> ModuleSystem:
    """Get the global module system instance."""
    global _module_system
    if _module_system is None:
        _module_system = ModuleSystem(base_path)
    return _module_system

def reset_module_system():
    """Reset the global module system (useful for testing)."""
    global _module_system
    _module_system = None