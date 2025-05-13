import logging
from typing import AsyncGenerator
import google.generativeai as genai
from vertexai.preview import tokenization

from core.config import settings # Import centralized settings

logger = logging.getLogger(__name__)

# --- Custom Exceptions ---
class AISummaryError(RuntimeError):
    """Base exception for AI summary generation errors."""
    pass

class AIInitializationError(AISummaryError):
    """Exception raised when AI model/tokenizer fails to initialize."""
    pass

class AITokenizationError(AISummaryError):
    """Exception raised during tokenization for AI model."""
    pass

class AIGenerationError(AISummaryError):
    """Exception raised during AI content generation, including blocked content."""
    pass

# --- Configuration ---
MODEL_NAME = 'gemini-2.0-flash' # Updated to a common valid model
TOKENIZER_MODEL = "gemini-1.5-pro-002" # Match model for tokenizer

if not settings.MY_GOOGLE_API_KEY:
    msg = "MY_GOOGLE_API_KEY environment variable not set. AI summarization will not work."
    logger.critical(msg)
    raise AIInitializationError(msg)

# Configure the GenAI client
try:
    genai.configure(api_key=settings.MY_GOOGLE_API_KEY)
    model = genai.GenerativeModel(MODEL_NAME)
    # This uses the public preview tokenizer, adjust if using Vertex AI directly
    tokenizer = tokenization.get_tokenizer_for_model(TOKENIZER_MODEL)
    logger.info(f"Initialized Gemini model '{MODEL_NAME}' and tokenizer '{TOKENIZER_MODEL}'")
except Exception as e:
    msg = f"Failed to initialize Google AI components: {e}"
    logger.critical(msg, exc_info=True)
    raise AIInitializationError(msg) from e


# --- Generation Function ---
async def generate_summary_stream(text: str, lang: str = 'en', size: str = "medium", technicality: str = "technical") -> AsyncGenerator[str | dict, None]:
    """
    Generates a summary using the Gemini model and yields progress/results.
    Yields:
        - dict: Progress updates or error messages.
        - str: The final generated summary text (HTML).
    """
    if not text:
        logger.warning("Analyzer: No text content provided for summarization.")
        yield {"error": "No text content received by analyzer."}
        return

    length_guidance = {
        "small": "concise (around 2-3 paragraphs)",
        "medium": "detailed (several paragraphs, covering key aspects)",
        "large": "very detailed and comprehensive (multiple sections, extensive coverage)"
    }.get(size.lower(), "detailed (several paragraphs, covering key aspects)")

    prompt = f"""
    
    ```
    {text}
    ```
    """
    
    yield {"status": "Calculating prompt size...", "component": "analyzer"}
    try:
        prompt_token_count_response = tokenizer.count_tokens(prompt)
        total_tokens = prompt_token_count_response.total_tokens
        logger.info(f"Analyzer: Prompt token count for current request: {total_tokens}")
        yield {"status": f"Prompt token count: {total_tokens}", "component": "analyzer"}
    except Exception as e:
        logger.error(f"Analyzer: Error during tokenization: {e}", exc_info=True)
        # Yield error to client and stop this generation attempt
        yield {"error": f"Could not calculate prompt size: {type(e).__name__}"}
        # Optionally raise AITokenizationError(e) if this function was not a generator
        return

    logger.info("Analyzer: Sending request to Gemini API...")
    yield {"status": "Generating summary via Gemini API...", "component": "analyzer"}

    try:
        generation_config = genai.types.GenerationConfig(
            temperature=0.7,
        )
        response = await model.generate_content_async(
            prompt,
            generation_config=generation_config,
        )

        if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
            block_reason_str = str(response.prompt_feedback.block_reason)
            logger.warning(f"Analyzer: Content generation blocked by safety filters. Reason: {block_reason_str}")
            yield {"error": f"Content generation blocked by safety filters: {block_reason_str}"}
            return # Stop generation

        if not response.candidates or not response.candidates[0].content.parts:
            finish_reason_str = "UNKNOWN"
            if response.candidates and response.candidates[0].finish_reason:
                 finish_reason_str = str(response.candidates[0].finish_reason)
            logger.warning(f"Analyzer: No valid candidate content received from Gemini. Finish reason: {finish_reason_str}")
            yield {"error": f"No summary content received from Gemini. Finish reason: {finish_reason_str}"}
            return

        final_summary = response.text
        # Basic cleanup for common markdown fences if AI includes them despite prompt
        if "" in final_summary:
            final_summary = final_summary.replace("", "").replace("```", "").strip()
        
        logger.info(f"Analyzer: Summary generated successfully. Length: {len(final_summary)} chars.")
        yield final_summary

    except Exception as e:
        logger.error(f"Analyzer: Error during Gemini API call: {e}", exc_info=True)
        yield {"error": f"Failed to generate summary due to an API error: {type(e).__name__}"}
        # Optionally raise AIGenerationError(e) if this function was not a generator
