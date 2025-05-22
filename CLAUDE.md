# Comind Development Guidelines

## Build & Test Commands
- Install dependencies: `pip install -r requirements.txt -r requirements-dev.txt`
- Run all tests: `python tests/run_tests.py` or `pytest -xvs tests/`
- Run single test: `pytest -xvs tests/test_structured_gen.py`
- Code coverage: `pytest --cov=src tests/` or with HTML report: `pytest --cov=src --cov-report=html tests/`
- Format code: `black src/ tests/`
- Lint code: `flake8 src/ tests/`
- Type check: `mypy src/ tests/`

## Code Style Guidelines
- Use Black formatter with default settings
- Keep line length to 88 characters (Black default)
- Use type annotations for all functions and classes
- Variable/function names: snake_case
- Class names: PascalCase
- Constants: UPPER_SNAKE_CASE
- Use Python 3.10+ features and typing
- Use Pydantic models for structured data
- Organize imports: standard library → third-party → local modules
- Proper error handling with try/except and logging
- Include docstrings for public functions/classes
- Code must pass mypy type checking and flake8 linting

## Core Principles
- Comind is lexicon first. Lexicons are the source of truth.

AI-generated contributions are welcome but must be high quality and well-reviewed.

## Documentation Guidelines
- Documentation is important. Changes in goals, objectives, motivations, and operation must be updated in the content/ folder. Be careful with it -- it is the most important thing for Comind.