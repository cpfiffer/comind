"""
Configure logging for the Comind application.
"""

import logging
import sys

def configure_root_logger_without_timestamp(level=logging.INFO):
    """
    Configure the root logger to output logs without timestamps.
    This affects all loggers in the application.
    """
    # Reset root logger configuration
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Create a new handler for stdout
    handler = logging.StreamHandler(sys.stdout)
    
    # Create a formatter without timestamps
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    # Add the handler to the root logger
    logging.root.addHandler(handler)
    logging.root.setLevel(level)
    
    # Also silence some noisy loggers by default
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    return logging.root

def configure_logger_without_timestamp(logger_name, level=logging.INFO):
    """
    Configure a specific logger to output logs without timestamps.
    """
    logger = logging.getLogger(logger_name)
    
    # Remove existing handlers to avoid duplicate messages
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create a new handler
    handler = logging.StreamHandler(sys.stdout)
    
    # Create a formatter without timestamps
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    logger.setLevel(level)
    
    # Prevent propagation to parent loggers (including root) to avoid duplicate logs
    logger.propagate = False
    
    return logger 