# engage_stdlib.py
"""
Engage Standard Library Foundation

This module provides the foundation for Engage's modular standard library system.
It includes:
- Module loading system with lazy initialization
- Base module interface for consistent function registration
- Module namespace isolation
- Error handling for module loading failures
"""

import os
import importlib.util
from typing import Dict, Any, Optional, Callable, List
from abc import ABC, abstractmethod


class EngageStdLibError(Exception):
    """Base exception for standard library errors."""
    pass


class ModuleLoadError(EngageStdLibError):
    """Raised when a module fails to load."""
    pass


class ModuleNotFoundError(EngageStdLibError):
    """Raised when a requested module is not found."""
    pass


class BaseModule(ABC):
    """
    Base class for all Engage standard library modules.
    
    Each module must implement the get_functions() method to return
    a dictionary of function names to their implementations.
    """
    
    def __init__(self, name: str):
        self.name = name
        self._initialized = False
        self._functions = {}
    
    @abstractmethod
    def get_functions(self) -> Dict[str, Callable]:
        """
        Return a dictionary of function names to their implementations.
        
        Returns:
            Dict[str, Callable]: Mapping of function names to callables
        """
        pass
    
    def initialize(self) -> None:
        """
        Initialize the module by loading its functions.
        This is called lazily when the module is first accessed.
        """
        if not self._initialized:
            try:
                self._functions = self.get_functions()
                self._initialized = True
            except Exception as e:
                raise ModuleLoadError(f"Failed to initialize module '{self.name}': {e}")
    
    def get_function(self, name: str) -> Optional[Callable]:
        """
        Get a specific function from this module.
        
        Args:
            name: The name of the function to retrieve
            
        Returns:
            The function callable, or None if not found
        """
        if not self._initialized:
            self.initialize()
        return self._functions.get(name)
    
    def list_functions(self) -> List[str]:
        """
        Get a list of all function names provided by this module.
        
        Returns:
            List of function names
        """
        if not self._initialized:
            self.initialize()
        return list(self._functions.keys())


class ModuleRegistry:
    """
    Registry for managing standard library modules.
    
    Provides lazy loading, namespace isolation, and error handling
    for standard library modules.
    """
    
    def __init__(self):
        self._modules: Dict[str, BaseModule] = {}
        self._module_paths: Dict[str, str] = {}
        self._loaded_modules: Dict[str, bool] = {}
    
    def register_module(self, name: str, module_class: type, module_path: Optional[str] = None) -> None:
        """
        Register a module class for lazy loading.
        
        Args:
            name: The name of the module
            module_class: The class that implements the module
            module_path: Optional path to the module file (for file-based modules)
        """
        if not issubclass(module_class, BaseModule):
            raise ValueError(f"Module class must inherit from BaseModule")
        
        self._modules[name] = module_class(name)
        if module_path:
            self._module_paths[name] = module_path
        self._loaded_modules[name] = False
    
    def get_module(self, name: str) -> Optional[BaseModule]:
        """
        Get a module by name, loading it lazily if necessary.
        
        Args:
            name: The name of the module to retrieve
            
        Returns:
            The module instance, or None if not found
            
        Raises:
            ModuleNotFoundError: If the module is not registered
            ModuleLoadError: If the module fails to load
        """
        if name not in self._modules:
            raise ModuleNotFoundError(f"Module '{name}' is not registered")
        
        module = self._modules[name]
        
        # Lazy initialization
        if not self._loaded_modules[name]:
            try:
                module.initialize()
                self._loaded_modules[name] = True
            except Exception as e:
                raise ModuleLoadError(f"Failed to load module '{name}': {e}")
        
        return module
    
    def get_function(self, module_name: str, function_name: str) -> Optional[Callable]:
        """
        Get a specific function from a module.
        
        Args:
            module_name: The name of the module
            function_name: The name of the function
            
        Returns:
            The function callable, or None if not found
        """
        try:
            module = self.get_module(module_name)
            return module.get_function(function_name) if module else None
        except (ModuleNotFoundError, ModuleLoadError):
            return None
    
    def list_modules(self) -> List[str]:
        """
        Get a list of all registered module names.
        
        Returns:
            List of module names
        """
        return list(self._modules.keys())
    
    def list_module_functions(self, module_name: str) -> List[str]:
        """
        Get a list of all functions in a specific module.
        
        Args:
            module_name: The name of the module
            
        Returns:
            List of function names
            
        Raises:
            ModuleNotFoundError: If the module is not registered
        """
        module = self.get_module(module_name)
        return module.list_functions() if module else []
    
    def is_module_loaded(self, name: str) -> bool:
        """
        Check if a module has been loaded.
        
        Args:
            name: The name of the module
            
        Returns:
            True if the module is loaded, False otherwise
        """
        return self._loaded_modules.get(name, False)


class StandardLibrary:
    """
    Main interface for the Engage standard library system.
    
    This class provides the primary interface for registering modules,
    loading functions, and managing the standard library namespace.
    """
    
    def __init__(self):
        self.registry = ModuleRegistry()
        self._builtin_functions: Dict[str, Callable] = {}
    
    def register_module(self, name: str, module_class: type, module_path: Optional[str] = None) -> None:
        """
        Register a standard library module.
        
        Args:
            name: The name of the module
            module_class: The class that implements the module
            module_path: Optional path to the module file
        """
        self.registry.register_module(name, module_class, module_path)
    
    def load_module_functions(self, module_name: str, symbol_table, builtin_function_class) -> None:
        """
        Load all functions from a module into the given symbol table.
        
        Args:
            module_name: The name of the module to load
            symbol_table: The symbol table to load functions into
            builtin_function_class: The BuiltInFunction class to use for wrapping
            
        Raises:
            ModuleNotFoundError: If the module is not found
            ModuleLoadError: If the module fails to load
        """
        module = self.registry.get_module(module_name)
        if not module:
            raise ModuleNotFoundError(f"Module '{module_name}' not found")
        
        for func_name in module.list_functions():
            func = module.get_function(func_name)
            if func:
                # Wrap the function in a BuiltInFunction for the interpreter
                builtin_func = builtin_function_class(f"{module_name}.{func_name}", func)
                symbol_table.set(func_name, builtin_func)
    
    def get_function(self, module_name: str, function_name: str) -> Optional[Callable]:
        """
        Get a specific function from a module.
        
        Args:
            module_name: The name of the module
            function_name: The name of the function
            
        Returns:
            The function callable, or None if not found
        """
        return self.registry.get_function(module_name, function_name)
    
    def list_modules(self) -> List[str]:
        """Get a list of all available modules."""
        return self.registry.list_modules()
    
    def list_module_functions(self, module_name: str) -> List[str]:
        """Get a list of all functions in a specific module."""
        return self.registry.list_module_functions(module_name)
    
    def register_builtin_function(self, name: str, func: Callable) -> None:
        """
        Register a built-in function that's always available.
        
        Args:
            name: The name of the function
            func: The function implementation
        """
        self._builtin_functions[name] = func
    
    def load_builtin_functions(self, symbol_table, builtin_function_class) -> None:
        """
        Load all built-in functions into the given symbol table.
        
        Args:
            symbol_table: The symbol table to load functions into
            builtin_function_class: The BuiltInFunction class to use for wrapping
        """
        for func_name, func in self._builtin_functions.items():
            builtin_func = builtin_function_class(func_name, func)
            symbol_table.set(func_name, builtin_func)


# Global standard library instance
stdlib = StandardLibrary()


def get_standard_library() -> StandardLibrary:
    """
    Get the global standard library instance.
    
    Returns:
        The global StandardLibrary instance
    """
    return stdlib


# --- Register UI Component Built-in Functions ---

def _register_ui_builtin_functions():
    """Register UI component built-in functions with the standard library."""
    try:
        from engage_ui_components import UI_BUILTIN_FUNCTIONS
        
        # Register each UI function as a built-in
        for func_name, func_obj in UI_BUILTIN_FUNCTIONS.items():
            stdlib.register_builtin_function(func_name, func_obj.func_ptr)
            
    except ImportError as e:
        print(f"Warning: Failed to load UI component functions: {e}")
    except Exception as e:
        print(f"Warning: Error registering UI functions: {e}")

# Register UI functions when module is imported
_register_ui_builtin_functions()