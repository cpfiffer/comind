"""
Format utilities for the Comind project.
Provides a more robust alternative to Python's string.format method.
"""

import re
import logging
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)

def format(template: str, context: Dict[str, Any], 
           safe: bool = True, default: str = "", 
           recursive: bool = True, max_depth: int = 5) -> str:
    """
    Format a template string using values from a context dictionary.
    
    This is a more robust alternative to Python's string.format() method,
    with features like:
    - Safe formatting (won't raise KeyError)
    - Default values for missing keys
    - Recursive formatting (format placeholders within formatted values)
    - Maximum recursion depth to prevent infinite loops
    - Detailed logging of formatting errors
    
    Args:
        template: The template string with {placeholders}
        context: Dictionary with values to insert into the template
        safe: If True, missing keys won't raise an exception
        default: Default value to use for missing keys when safe=True
        recursive: If True, perform recursive formatting
        max_depth: Maximum recursion depth for recursive formatting
        
    Returns:
        The formatted string
    """
    if not template:
        return template
        
    if not isinstance(template, str):
        logger.warning(f"Non-string template passed to format: {type(template)}")
        return str(template)
    
    # Find all placeholders in the string
    placeholders = re.findall(r'\{([^{}]*)\}', template)
    
    # Process each placeholder
    result = template
    for placeholder in placeholders:
        try:
            # Handle format specifiers (e.g., {key:10s})
            key = placeholder.split(':', 1)[0]
            
            if key in context:
                value = context[key]
                
                # Convert value to string if it's not already
                value_str = str(value) if not isinstance(value, str) else value
                
                # Handle recursive formatting if needed
                if recursive and max_depth > 0 and '{' in value_str and '}' in value_str:
                    value_str = format(
                        value_str, 
                        context, 
                        safe=safe, 
                        default=default, 
                        recursive=recursive, 
                        max_depth=max_depth-1
                    )
                
                # Replace the placeholder with the value
                result = result.replace(f"{{{placeholder}}}", value_str)
            elif safe:
                # Replace with default value if the key is missing
                result = result.replace(f"{{{placeholder}}}", default)
            else:
                # Raise an error for missing keys if not in safe mode
                raise KeyError(f"Missing key '{key}' in context dictionary")
                
        except Exception as e:
            if safe:
                logger.warning(f"Error formatting placeholder '{placeholder}': {str(e)}")
                result = result.replace(f"{{{placeholder}}}", default)
            else:
                raise
    
    return result

def format_dict(templates: Dict[str, str], context: Dict[str, Any], **kwargs) -> Dict[str, str]:
    """
    Format all string values in a dictionary using the same context.
    
    Args:
        templates: Dictionary of template strings to format
        context: Context dictionary to use for formatting
        **kwargs: Additional arguments to pass to format()
        
    Returns:
        Dictionary with all string values formatted
    """
    result = {}
    for key, template in templates.items():
        if isinstance(template, str):
            result[key] = format(template, context, **kwargs)
        else:
            result[key] = template
    return result 