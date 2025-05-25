# This is a copy/adaptation of the original services/analyzer.py
import logging
import asyncio
from typing import AsyncGenerator, Union # Union for Python < 3.10, use | for >= 3.10

import google.generativeai as genai
# from vertexai.preview import tokenization # Using genai's count_tokens for simplicity now
# If vertexai tokenizer is strictly needed, ensure google-cloud-aiplatform is installed

from ai_analyzer_service.core.config import settings

logger = logging.getLogger(__name__)

class AISummaryError(RuntimeError): pass
class AIInitializationError(AISummaryError): pass
class AITokenizationError(AISummaryError): pass
class AIGenerationError(AISummaryError): pass

# Configure GenAI client (done once when module is loaded)
try:
    if not settings.AI_ANALYZER_MY_GOOGLE_API_KEY:
        raise AIInitializationError("AI_ANALYZER_MY_GOOGLE_API_KEY not set in AI Analyzer service.")
    genai.configure(api_key=settings.AI_ANALYZER_MY_GOOGLE_API_KEY)
    model = genai.GenerativeModel(settings.AI_MODEL_NAME)
    # Tokenizer can be implicitly handled by model.count_tokens or explicitly:
    # tokenizer = tokenization.get_tokenizer_for_model(settings.AI_TOKENIZER_MODEL) # If using Vertex
    logger.info(f"AI Analyzer: Initialized Gemini model '{settings.AI_MODEL_NAME}'")
except Exception as e:
    logger.critical(f"AI Analyzer: Failed to initialize Google AI components: {e}", exc_info=True)
    # This will cause tasks to fail if model is not initialized.
    # Consider a health check or explicit failure if model is None.
    model = None # Ensure model is None if init fails

async def generate_summary(text: str, lang: str = 'en', size: str = "medium", technicality: str = "technical") -> str:
    """
    Generates a summary using the Gemini model. This is now a direct call, not a stream.
    Returns the summary string or raises an AIGenerationError.
    """
    if not model:
        raise AIInitializationError("AI Model not initialized. Cannot generate summary.")
    if not text:
        logger.warning("AI Analyzer: No text content provided for summarization.")
        raise ValueError("No text content received by analyzer.")

    length_guidance = {
        "small": "concise (around 2-3 paragraphs)",
        "medium": "detailed (several paragraphs, covering key aspects)",
        "large": "very detailed and comprehensive (multiple sections, extensive coverage)"
    }.get(size.lower(), "detailed (several paragraphs)")

    technical_guidance = {
        "non-technical": "for a non-technical team member or client (simple language, focus on purpose and value).",
        "technical": "for a software developer (mention key technologies, structure, and how to get started).",
        "expert": "for an expert in the domain (deep dive into architecture, advanced concepts, and potential challenges)."
    }.get(technicality.lower(), "for a software developer.")

    prompt = f"""Analyze the following GitHub repository content and generate a structured HTML summary.
The repository content is provided as a series of file excerpts.
Your summary should be in {lang}.
The desired length of the summary is: {length_guidance}.
The target audience is: {technical_guidance}.

The HTML output should be well-formed and include these sections if applicable, adapting to the content:
- **Overview:** A brief introduction to the project's purpose.
- **Key Features/Functionality:** Main capabilities.
- **Tech Stack/Architecture:** Core technologies and structure.
- **Setup & Usage:** How to get it running and use it.
- **File Structure Highlights:** Notable files or directories.
- **Potential Next Steps/Improvements:** (Optional, if evident)

Do NOT include the markdown "html" and "" fences around your HTML output.
Provide only the HTML content for the summary itself.

Repository Content:
---
{text}
---
End of Repository Content. Generate the HTML summary now.
"""
    try:
        # Token counting (optional here, but good for debugging/cost estimation)
        # token_count_response = await model.count_tokens_async(prompt) # If using genai's count_tokens
        # logger.info(f"AI Analyzer: Prompt token count: {token_count_response.total_tokens}")
        pass
    except Exception as e:
        logger.error(f"AI Analyzer: Error during token counting (optional step): {e}", exc_info=True)
        # Non-fatal for this step, proceed to generation

    logger.info("AI Analyzer: Sending request to Gemini API...")
    try:
        generation_config = genai.types.GenerationConfig(
            temperature=0.6, # Adjust as needed
            # max_output_tokens= (depends on 'size' parameter, e.g. 2048 for medium)
        )
        response = await model.generate_content_async(
            prompt,
            generation_config=generation_config,
            # safety_settings=... # configure safety settings if needed
        )

        if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
            reason = response.prompt_feedback.block_reason
            logger.warning(f"AI Analyzer: Content generation blocked. Reason: {reason}")
            raise AIGenerationError(f"Content generation blocked by safety filters: {reason}")

        if not response.candidates or not response.candidates[0].content.parts:
            finish_reason = "UNKNOWN"
            if response.candidates and hasattr(response.candidates[0], 'finish_reason'):
                 finish_reason = response.candidates[0].finish_reason
            logger.warning(f"AI Analyzer: No valid candidate content. Finish reason: {finish_reason}")
            raise AIGenerationError(f"No summary content received from Gemini. Finish reason: {finish_reason}")

        final_summary = response.text
        # Basic cleanup if AI still includes markdown fences
        if final_summary.startswith("html"): final_summary = final_summary[7:]
        if final_summary.endswith(""): final_summary = final_summary[:-3]
        final_summary = final_summary.strip()
        
        logger.info(f"AI Analyzer: Summary generated. Length: {len(final_summary)} chars.")
        return final_summary

    except Exception as e:
        if isinstance(e, AIGenerationError): raise # Re-raise if already our type
        logger.error(f"AI Analyzer: Error during Gemini API call: {e}", exc_info=True)
        raise AIGenerationError(f"Failed to generate summary due to an API error: {type(e).__name__}") from e