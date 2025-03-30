# Testing Comind

This directory contains tests for the Comind project.

## Setup

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

## Running Tests

You can run all tests using:

```bash
python tests/run_tests.py
```

Or run pytest directly:

```bash
pytest -xvs tests/
```

To run a specific test file:

```bash
pytest -xvs tests/test_structured_gen.py
```

## Writing Tests

- Each module should have a corresponding test file named `test_<module_name>.py`
- Use pytest fixtures for common setup
- Mock external dependencies (like API calls)
- Aim for high test coverage

## Coverage Report

Generate a coverage report with:

```bash
pytest --cov=src tests/
```

For a detailed HTML report:

```bash
pytest --cov=src --cov-report=html tests/
```

The HTML report will be available in the `htmlcov` directory. 