# tests/services/test_analyzer.py
import pytest
import os
from unittest.mock import patch, AsyncMock, MagicMock

# Mock genai and tokenizer before importing the service
# This is crucial if these are initialized at the module level in analyzer.py
mock_genai = MagicMock()
mock_generative_model = MagicMock()
mock_genai.GenerativeModel.return_value = mock_generative_model
mock_genai.configure = MagicMock()
mock_genai.types = MagicMock() # For GenerationConfig
mock_genai.types.GenerationConfig = MagicMock(return_value="mock_generation_config")

mock_tokenizer_instance = MagicMock()
mock_tokenizer_instance.count_tokens.return_value = MagicMock(total_tokens=100) # Mock the structure of CountTokensResponse

mock_tokenization_module = MagicMock()
mock_tokenization_module.get_tokenizer_for_model.return_value = mock_tokenizer_instance

# IMPORTANT: Patch before 'from services.analyzer import ...'
# if GOOGLE_API_KEY check is at module level
# Or ensure MY_GOOGLE_API_KEY is set in test environment (e.g., conftest.py monkeypatch)
with patch.dict(os.environ, {"MY_GOOGLE_API_KEY": "test_google_api_key_for_analyzer"}):
    with patch('google.generativeai', mock_genai):
        with patch('vertexai.preview.tokenization', mock_tokenization_module):
            from services.analyzer import generate_summary_stream

@pytest.mark.asyncio
async def test_generate_summary_stream_success():
    # Reset mocks for each test if they are stateful
    mock_generative_model.generate_content_async.reset_mock()
    mock_tokenizer_instance.count_tokens.reset_mock()

    mock_response = AsyncMock()
    mock_response.text = " Mocked HTML Summary "
    mock_response.candidates = [MagicMock(content=MagicMock(parts=[MagicMock()]), finish_reason="STOP")] # Mock structure
    mock_response.prompt_feedback = None # No blocking
    mock_generative_model.generate_content_async.return_value = mock_response
    mock_tokenizer_instance.count_tokens.return_value = MagicMock(total_tokens=150)

    input_text = "This is a test repository content."
    results = []
    async for item in generate_summary_stream(input_text, lang="en", size="small", technicality="non-technical"):
        results.append(item)

    # Expected sequence of yields:
    # 1. Token count status
    # 2. Token count result
    # 3. Generation start status
    # 4. Final summary string
    assert len(results) >= 3 # Status updates + final summary
    assert any(r == {"status": "Calculating prompt size...", "component": "analyzer"} for r in results)
    assert any(r == {"status": "Prompt token count: 150", "component": "analyzer"} for r in results)
    assert any(r == {"status": "Generating summary via Gemini API...", "component": "analyzer"} for r in results)
    assert " Mocked HTML Summary " in results

    mock_tokenizer_instance.count_tokens.assert_called_once()
    prompt_arg = mock_tokenizer_instance.count_tokens.call_args[0][0]
    assert "Output Language: en" in prompt_arg
    assert "concise (around 2-3 paragraphs)" in prompt_arg # for 'small' size
    assert "non-technical team member" in prompt_arg # for 'non-technical'
    mock_generative_model.generate_content_async.assert_called_once()
    # Further assertions on the prompt passed to generate_content_async can be added here

@pytest.mark.asyncio
async def test_generate_summary_stream_empty_text():
    results = []
    async for item in generate_summary_stream(""):
        results.append(item)
    assert len(results) == 1
    assert results[0] == {"error": "No text content received by analyzer."}

@pytest.mark.asyncio
async def test_generate_summary_stream_tokenization_error():
    mock_tokenizer_instance.count_tokens.side_effect = Exception("Tokenization failed")
    results = []
    async for item in generate_summary_stream("some text"):
        results.append(item)

    # Expected sequence:
    # 1. Calculating prompt size...
    # 2. Error from tokenization
    # It should not proceed to Gemini API call
    assert {"status": "Calculating prompt size...", "component": "analyzer"} in results
    assert {"error": "Could not calculate prompt size: Tokenization failed"} in results
    mock_generative_model.generate_content_async.assert_not_called()

    # Reset side effect for other tests
    mock_tokenizer_instance.count_tokens.side_effect = None
    mock_tokenizer_instance.count_tokens.return_value = MagicMock(total_tokens=100)

@pytest.mark.asyncio
async def test_generate_summary_stream_api_error():
    mock_generative_model.generate_content_async.side_effect = Exception("API Call Failed")
    mock_tokenizer_instance.count_tokens.return_value = MagicMock(total_tokens=100)

    results = []
    async for item in generate_summary_stream("some text"):
        results.append(item)

    assert any(r == {"status": "Generating summary via Gemini API...", "component": "analyzer"} for r in results)
    assert any(r == {"error": "Failed to generate summary: Exception"} for r in results) # Type of exception

    # Reset side effect
    mock_generative_model.generate_content_async.side_effect = None

@pytest.mark.asyncio
async def test_generate_summary_stream_blocked_content():
    mock_response_blocked = AsyncMock()
    mock_response_blocked.prompt_feedback = MagicMock(block_reason="SAFETY")
    mock_response_blocked.text = "" # No text when blocked
    mock_response_blocked.candidates = [] # Or candidates might exist but indicate blocking
    mock_generative_model.generate_content_async.return_value = mock_response_blocked
    mock_tokenizer_instance.count_tokens.return_value = MagicMock(total_tokens=100)

    results = []
    async for item in generate_summary_stream("potentially problematic text"):
        results.append(item)

    assert any(r == {"error": "Content generation blocked by safety filters: SAFETY"} for r in results)

@pytest.mark.asyncio
async def test_generate_summary_stream_no_candidates():
    mock_response_no_candidate = AsyncMock()
    mock_response_no_candidate.prompt_feedback = None
    mock_response_no_candidate.candidates = [] # No candidates
    # OR mock_response_no_candidate.candidates = [MagicMock(content=MagicMock(parts=[]))]
    mock_generative_model.generate_content_async.return_value = mock_response_no_candidate
    mock_tokenizer_instance.count_tokens.return_value = MagicMock(total_tokens=100)

    results = []
    async for item in generate_summary_stream("text leading to no candidates"):
        results.append(item)

    # The error message includes finish_reason which might be tricky to mock perfectly without knowing the exact structure
    # We'll check for the core part of the error.
    found_error = False
    for r in results:
        if isinstance(r, dict) and "error" in r and "No summary content received from Gemini" in r["error"]:
            found_error = True
            break
    assert found_error, f"Expected 'No summary content received' error, got {results}"

# Ensure mocks are reset if they were class-level or module-level for some reason
# This is generally handled by pytest fixtures or function-scoped mocks.