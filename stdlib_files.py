# stdlib_files.py
"""
Engage Standard Library - Files Module

Provides file system operations for the Engage programming language.
"""

import os
from typing import Dict, Callable
from engage_stdlib import BaseModule


class FilesModule(BaseModule):
    """
    Files module providing file system operations.
    """
    
    def get_functions(self) -> Dict[str, Callable]:
        """Return all file system functions."""
        return {
            'read_file': self._read_file,
            'write_file': self._write_file,
            'file_exists': self._file_exists,
            'create_directory': self._create_directory,
        }
    
    def _read_file(self, args):
        """Read the contents of a file."""
        from engage_interpreter import String, ResultValue
        
        if len(args) != 1:
            return ResultValue('Error', String("read_file() expects exactly one argument (file_path)."))
        
        if not hasattr(args[0], 'value'):
            return ResultValue('Error', String("read_file() argument must have a value."))
        
        if not isinstance(args[0].value, str):
            return ResultValue('Error', String("read_file() expects a string argument (file path)."))
        
        file_path = args[0].value
        
        # Validate file path is not empty
        if not file_path.strip():
            return ResultValue('Error', String("read_file() file path cannot be empty."))
        
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                return ResultValue('Error', String(f"read_file() file not found: {file_path}"))
            
            # Check if it's actually a file (not a directory)
            if not os.path.isfile(file_path):
                return ResultValue('Error', String(f"read_file() path is not a file: {file_path}"))
            
            # Read the file
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            return String(content)
            
        except PermissionError:
            return ResultValue('Error', String(f"read_file() permission denied: {file_path}"))
        except UnicodeDecodeError:
            return ResultValue('Error', String(f"read_file() unable to decode file as UTF-8: {file_path}"))
        except Exception as e:
            return ResultValue('Error', String(f"read_file() failed: {str(e)}"))
    
    def _write_file(self, args):
        """Write content to a file."""
        from engage_interpreter import String, ResultValue, NoneValue
        
        if len(args) != 2:
            return ResultValue('Error', String("write_file() expects exactly two arguments (file_path, content)."))
        
        # Validate file path argument
        if not hasattr(args[0], 'value'):
            return ResultValue('Error', String("write_file() file path argument must have a value."))
        
        if not isinstance(args[0].value, str):
            return ResultValue('Error', String("write_file() file path must be a string."))
        
        # Validate content argument
        if not hasattr(args[1], 'value'):
            return ResultValue('Error', String("write_file() content argument must have a value."))
        
        file_path = args[0].value
        content = str(args[1].value)  # Convert to string if not already
        
        # Validate file path is not empty
        if not file_path.strip():
            return ResultValue('Error', String("write_file() file path cannot be empty."))
        
        try:
            # Create directory if it doesn't exist
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
            
            # Write the file
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(content)
            
            return NoneValue()
            
        except PermissionError:
            return ResultValue('Error', String(f"write_file() permission denied: {file_path}"))
        except OSError as e:
            return ResultValue('Error', String(f"write_file() OS error: {str(e)}"))
        except Exception as e:
            return ResultValue('Error', String(f"write_file() failed: {str(e)}"))
    
    def _file_exists(self, args):
        """Check if a file exists."""
        from engage_interpreter import String, Number, ResultValue
        
        if len(args) != 1:
            return ResultValue('Error', String("file_exists() expects exactly one argument (file_path)."))
        
        if not hasattr(args[0], 'value'):
            return ResultValue('Error', String("file_exists() argument must have a value."))
        
        if not isinstance(args[0].value, str):
            return ResultValue('Error', String("file_exists() expects a string argument (file path)."))
        
        file_path = args[0].value
        
        # Validate file path is not empty
        if not file_path.strip():
            return ResultValue('Error', String("file_exists() file path cannot be empty."))
        
        try:
            # Check if file exists and is actually a file
            exists = os.path.exists(file_path) and os.path.isfile(file_path)
            return Number(1 if exists else 0)  # Return 1 for true, 0 for false
            
        except Exception as e:
            return ResultValue('Error', String(f"file_exists() failed: {str(e)}"))
    
    def _create_directory(self, args):
        """Create a directory (and parent directories if needed)."""
        from engage_interpreter import String, ResultValue, NoneValue
        
        if len(args) != 1:
            return ResultValue('Error', String("create_directory() expects exactly one argument (directory_path)."))
        
        if not hasattr(args[0], 'value'):
            return ResultValue('Error', String("create_directory() argument must have a value."))
        
        if not isinstance(args[0].value, str):
            return ResultValue('Error', String("create_directory() expects a string argument (directory path)."))
        
        directory_path = args[0].value
        
        # Validate directory path is not empty
        if not directory_path.strip():
            return ResultValue('Error', String("create_directory() directory path cannot be empty."))
        
        try:
            # Create directory and any necessary parent directories
            os.makedirs(directory_path, exist_ok=True)
            return NoneValue()
            
        except PermissionError:
            return ResultValue('Error', String(f"create_directory() permission denied: {directory_path}"))
        except OSError as e:
            return ResultValue('Error', String(f"create_directory() OS error: {str(e)}"))
        except Exception as e:
            return ResultValue('Error', String(f"create_directory() failed: {str(e)}"))