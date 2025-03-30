#!/usr/bin/env python3
"""
Run all tests in the tests directory.
Usage: python tests/run_tests.py
"""

import os
import sys
import pytest

def main():
    """Run all tests in the tests directory."""
    # Get the directory of this script
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Add the parent directory to the path so we can import our modules
    parent_dir = os.path.dirname(tests_dir)
    sys.path.append(parent_dir)
    
    # Run all tests in the tests directory
    result = pytest.main(["-xvs", tests_dir])
    
    # Return the exit code from pytest
    return result

if __name__ == "__main__":
    sys.exit(main()) 