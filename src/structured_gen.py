# See vllm docs for structured outputs stuff
# https://docs.vllm.ai/en/latest/features/structured_outputs.html

import json
from openai import OpenAI
from pydantic import BaseModel
from typing import List, Dict, Union
import logging
from rich import print

import os
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger("structured_gen")

# Silence httpx logs (only show warnings and errors)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

LLM_SERVER_URL = os.getenv("COMIND_LLM_SERVER_URL")
EMBEDDING_SERVER_URL = os.getenv("COMIND_EMBEDDING_SERVER_URL")
LLM_SERVER_API_KEY = os.getenv("COMIND_LLM_SERVER_API_KEY", "no key required")
EMBEDDING_SERVER_API_KEY = os.getenv("COMIND_EMBEDDING_SERVER_API_KEY", "no key required")

if LLM_SERVER_URL is None:
    logger.error("LLM_SERVER_URL is not set. Please set this environment variable.")
    raise ValueError("LLM_SERVER_URL environment variable is required")

if EMBEDDING_SERVER_URL is None:
    logger.error("EMBEDDING_SERVER_URL is not set. Please set this environment variable.")
    raise ValueError("EMBEDDING_SERVER_URL environment variable is required")

logger.info(f"Connecting to LLM server at {LLM_SERVER_URL}")
logger.info(f"Connecting to embedding server at {EMBEDDING_SERVER_URL}")

CLIENT = OpenAI(
    base_url=LLM_SERVER_URL,
    api_key=LLM_SERVER_API_KEY,
)
CLIENT_EMBEDDING = OpenAI(
    base_url=EMBEDDING_SERVER_URL,
    api_key=EMBEDDING_SERVER_API_KEY,
)

# Check to see if we have a DEFAULT_MODEL environment variable.
DEFAULT_MODEL = os.getenv("COMIND_DEFAULT_MODEL")
if DEFAULT_MODEL is None:
    logger.info("No COMIND_DEFAULT_MODEL environment variable set. Fetching models from the server.")
    try:
        MODELS = CLIENT.models.list()
        DEFAULT_MODEL = MODELS.data[0].id
        logger.info(f"Using default LLM model: {DEFAULT_MODEL}. Available models are: {[m.id for m in MODELS.data]}")
    except Exception as e:
        logger.error(f"Failed to fetch LLM models: {e}")
        DEFAULT_MODEL = "claude-3-haiku-20240307"
        logger.warning(f"Falling back to default model: {DEFAULT_MODEL}")

try:
    EMBEDDING_MODELS = CLIENT_EMBEDDING.models.list()
    DEFAULT_EMBEDDING_MODEL = EMBEDDING_MODELS.data[0].id
    logger.info(f"Using default embedding model: {DEFAULT_EMBEDDING_MODEL}")
except Exception as e:
    logger.error(f"Failed to fetch embedding models: {e}")
    DEFAULT_EMBEDDING_MODEL = "text-embedding-ada-002"
    logger.warning(f"Falling back to default embedding model: {DEFAULT_EMBEDDING_MODEL}")

EMBEDDING_PREAMBLE = "Represent this sentence for searching relevant passages: "

# Maximum number of tokens that can be output by the LLM.
MAX_OUTPUT_TOKENS = 12000

def messages(user: str, system: str = "You are a helpful assistant."):
    """Create a messages list for the chat API."""
    ms = [{"role": "user", "content": user}]
    if system:
        ms.insert(0, {"role": "system", "content": system})
    return ms

def generate(
    messages: List[Dict[str, str]],
    response_format: BaseModel,
):
    """Generate a response using a structured response format."""
    logger.info(f"Generating structured response with model {DEFAULT_MODEL}")
    try:
        response = CLIENT.beta.chat.completions.parse(
            model=DEFAULT_MODEL,
            messages=messages,
            response_format=response_format,
            extra_body={
                "max_tokens": MAX_OUTPUT_TOKENS,
            }
        )
        logger.info("Successfully generated structured response")
        return response
    except Exception as e:
        logger.error(f"Error generating structured response: {e}")
        raise

def generate_by_schema(
    messages: List[Dict[str, str]],
    schema: Union[str, dict],
) -> BaseModel:
    """Generate a response conforming to a JSON schema."""
    logger.info(f"Generating schema-guided response with model {DEFAULT_MODEL}")

    if isinstance(schema, dict):
        schema = json.dumps(schema)
    elif isinstance(schema, str):
        schema = schema
    else:
        raise ValueError(f"Schema must be a string or a dictionary. Received: {type(schema)}")
    
    try:
        response = CLIENT.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            extra_body={
                "guided_json": schema,
                "max_tokens": MAX_OUTPUT_TOKENS,
            }
        )
        logger.debug("Successfully generated schema-guided response")
        return response
    except Exception as e:
        logger.error(f"Error generating schema-guided response: {e}")
        raise

def choose(
    messages: List[Dict[str, str]],
    choices: List[str],
) -> BaseModel:
    """Generate a response that must be one of the given choices."""
    logger.info(f"Generating choice response with {len(choices)} options")
    
    try:
        completion = CLIENT.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            extra_body={"guided_choice": choices, "max_tokens": MAX_OUTPUT_TOKENS},
        )
        logger.info("Successfully generated choice response")
        return completion
    except Exception as e:
        logger.error(f"Error generating choice response: {e}")
        raise

def regex(
    messages: List[Dict[str, str]],
    regex: str,
) -> BaseModel:
    """Generate a response that matches the given regex pattern."""
    logger.info(f"Generating regex-guided response with pattern: {regex[:30]}...")
    
    try:
        completion = CLIENT.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            extra_body={"guided_regex": regex, "max_tokens": MAX_OUTPUT_TOKENS},
        )
        logger.info("Successfully generated regex-guided response")
        return completion
    except Exception as e:
        logger.error(f"Error generating regex-guided response: {e}")
        raise

def embed(content: str) -> List[float]:
    """Generate embeddings for the given content."""
    logger.debug(f"Generating embeddings for content: {content[:50]}...")
    try:
        response = CLIENT_EMBEDDING.embeddings.create(
            model=DEFAULT_EMBEDDING_MODEL,
            input=EMBEDDING_PREAMBLE + content,
        )
        logger.debug(f"Successfully generated embeddings with dimension {len(response.data[0].embedding)}")
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise
