#!/usr/bin/env python3
"""
Script to apply non-timestamp logging configuration to all major modules.
Run this script from the project root directory.
"""

import importlib
import logging
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our logging configuration
from src.comind.logging_config import configure_root_logger_without_timestamp

# Configure the root logger without timestamps
configure_root_logger_without_timestamp()

# Reset and reconfigure all existing loggers to remove timestamps
for name in logging.root.manager.loggerDict:
    logger = logging.getLogger(name)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Force the logger to use handlers from the root logger
    logger.propagate = True

    print(f"Reconfigured logger: {name}")

# Force reload modules that might have already configured logging
modules_to_reload = [
    'src.jetstream_consumer',
    'src.record_manager',
    'src.session_reuse',
    'src.structured_gen',
    'src.comind.comind',
    'src.bsky_utils',
    'src.sphere_manager',
]

for module_name in modules_to_reload:
    try:
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
            print(f"Reloaded module: {module_name}")
    except (ImportError, KeyError) as e:
        print(f"Could not reload module {module_name}: {e}")

print("\nLogging has been reconfigured to remove timestamps.")
print("All new log messages should now appear without timestamps.")
print("Note: You may need to restart any existing processes for changes to take effect.") 