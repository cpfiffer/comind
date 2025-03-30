import pytest
import json
import os
from unittest.mock import patch, MagicMock
import sys
from typing import List, Dict, Any

# Add the parent directory to the path so we can import our module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our module
from src import structured_gen

# Test data
MOCK_MESSAGES = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Tell me about AI."}
]

MOCK_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "points": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["summary", "points"]
}

MOCK_CHOICES = ["Yes", "No", "Maybe"]
MOCK_REGEX = r"^\d{3}-\d{3}-\d{4}$"  # US phone number format
MOCK_CONTENT = "What is artificial intelligence?"

# Mock response class to simulate OpenAI API responses
class MockResponse:
    def __init__(self, content, model="mock-model"):
        self.model = model
        self.choices = [MagicMock(message=MagicMock(content=content))]
        self.data = [MagicMock(embedding=[0.1, 0.2, 0.3, 0.4, 0.5])]
        
# Apply mocks for all tests in this file
@pytest.fixture(autouse=True)
def setup_environment_variables():
    with patch.dict(os.environ, {
        "LLM_SERVER_URL": "http://mock-llm-server",
        "EMBEDDING_SERVER_URL": "http://mock-embedding-server"
    }):
        yield

@pytest.fixture
def mock_openai_client():
    with patch("src.structured_gen.CLIENT") as mock_client, \
         patch("src.structured_gen.CLIENT_EMBEDDING") as mock_embedding_client:
        
        # Mock the basic completion response
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content='{"summary": "AI is a field of computer science.", "points": ["Machine learning", "Neural networks"]}'))]
        mock_client.chat.completions.create.return_value = mock_completion
        
        # Mock the parse response
        mock_parse_response = MagicMock()
        mock_client.beta.chat.completions.parse.return_value = mock_parse_response
        
        # Mock embedding response
        mock_embedding_response = MagicMock()
        mock_embedding_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3, 0.4, 0.5])]
        mock_embedding_client.embeddings.create.return_value = mock_embedding_response
        
        yield mock_client, mock_embedding_client

# Test helper message function
def test_messages():
    # Test with both system and user messages
    result = structured_gen.messages("Test message", "System prompt")
    assert len(result) == 2
    assert result[0]["role"] == "system"
    assert result[0]["content"] == "System prompt"
    assert result[1]["role"] == "user"
    assert result[1]["content"] == "Test message"
    
    # Test with only user message
    result = structured_gen.messages("Test message", "")
    assert len(result) == 1
    assert result[0]["role"] == "user"
    assert result[0]["content"] == "Test message"

# Test generate function
def test_generate(mock_openai_client):
    mock_client, _ = mock_openai_client
    response_format = {"type": "json_object"}
    
    result = structured_gen.generate(MOCK_MESSAGES, response_format)
    
    # Verify the API was called correctly
    mock_client.beta.chat.completions.parse.assert_called_once()
    call_args = mock_client.beta.chat.completions.parse.call_args[1]
    assert call_args["model"] == structured_gen.DEFAULT_MODEL
    assert call_args["messages"] == MOCK_MESSAGES
    assert call_args["response_format"] == response_format
    assert call_args["extra_body"]["max_tokens"] == structured_gen.MAX_OUTPUT_TOKENS

# Test generate_by_schema function
def test_generate_by_schema(mock_openai_client):
    mock_client, _ = mock_openai_client
    schema_str = json.dumps(MOCK_SCHEMA)
    
    result = structured_gen.generate_by_schema(MOCK_MESSAGES, schema_str)
    
    # Check if API was called correctly
    mock_client.chat.completions.create.assert_called_once()
    call_args = mock_client.chat.completions.create.call_args[1]
    assert call_args["model"] == structured_gen.DEFAULT_MODEL
    assert call_args["messages"] == MOCK_MESSAGES
    assert call_args["extra_body"]["guided_json"] == schema_str
    assert call_args["extra_body"]["max_tokens"] == structured_gen.MAX_OUTPUT_TOKENS
    
    # Verify we can parse the result
    content = result.choices[0].message.content
    data = json.loads(content)
    assert "summary" in data
    assert "points" in data
    assert isinstance(data["points"], list)

# Test choose function
def test_choose(mock_openai_client):
    mock_client, _ = mock_openai_client
    
    result = structured_gen.choose(MOCK_MESSAGES, MOCK_CHOICES)
    
    # Check if API was called correctly
    mock_client.chat.completions.create.assert_called_once()
    call_args = mock_client.chat.completions.create.call_args[1]
    assert call_args["model"] == structured_gen.DEFAULT_MODEL
    assert call_args["messages"] == MOCK_MESSAGES
    assert call_args["extra_body"]["guided_choice"] == MOCK_CHOICES
    assert call_args["extra_body"]["max_tokens"] == structured_gen.MAX_OUTPUT_TOKENS

# Test regex function
def test_regex(mock_openai_client):
    mock_client, _ = mock_openai_client
    
    result = structured_gen.regex(MOCK_MESSAGES, MOCK_REGEX)
    
    # Check if API was called correctly
    mock_client.chat.completions.create.assert_called_once()
    call_args = mock_client.chat.completions.create.call_args[1]
    assert call_args["model"] == structured_gen.DEFAULT_MODEL
    assert call_args["messages"] == MOCK_MESSAGES
    assert call_args["extra_body"]["guided_regex"] == MOCK_REGEX
    assert call_args["extra_body"]["max_tokens"] == structured_gen.MAX_OUTPUT_TOKENS

# Test embed function
def test_embed(mock_openai_client):
    _, mock_embedding_client = mock_openai_client
    
    result = structured_gen.embed(MOCK_CONTENT)
    
    # Verify the embedding API was called correctly
    mock_embedding_client.embeddings.create.assert_called_once()
    call_args = mock_embedding_client.embeddings.create.call_args[1]
    assert call_args["model"] == structured_gen.DEFAULT_EMBEDDING_MODEL
    assert call_args["input"] == structured_gen.EMBEDDING_PREAMBLE + MOCK_CONTENT
    
    # Check the result is a list of floats
    assert isinstance(result, list)
    assert len(result) > 0
    assert isinstance(result[0], float)

# Test error handling
def test_error_handling(mock_openai_client):
    mock_client, _ = mock_openai_client
    mock_client.chat.completions.create.side_effect = Exception("API Error")
    
    # Test that an error is propagated
    with pytest.raises(Exception) as exc_info:
        structured_gen.generate_by_schema(MOCK_MESSAGES, json.dumps(MOCK_SCHEMA))
    
    assert "API Error" in str(exc_info.value)

# Run the tests
if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 