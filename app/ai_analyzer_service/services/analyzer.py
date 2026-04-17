import logging
import hashlib
from typing import Optional

from ai_analyzer_service.core.config import settings
from ai_analyzer_service.services.providers.base import SummaryProvider
from ai_analyzer_service.services.providers.factory import create_summary_provider

logger = logging.getLogger(__name__)

class AISummaryError(RuntimeError): pass
class AIInitializationError(AISummaryError): pass
class AITokenizationError(AISummaryError): pass
class AIGenerationError(AISummaryError): pass

_summary_provider: Optional[SummaryProvider] = None


def _get_summary_provider() -> SummaryProvider:
    global _summary_provider
    if _summary_provider is None:
        try:
            _summary_provider = create_summary_provider()
            logger.info(
                "AI Analyzer: Initialized provider '%s' with model '%s'.",
                settings.AI_PROVIDER,
                settings.AI_MODEL_NAME,
            )
        except Exception as exc:
            logger.error("AI Analyzer: Provider initialization failed: %s", exc, exc_info=True)
            raise AIInitializationError(str(exc)) from exc
    return _summary_provider


def _normalize_technicality(technicality: str) -> str:
    normalized = (technicality or "technical").strip().lower()
    aliases = {
        "beginner": "non-technical",
        "intermediate": "technical",
    }
    return aliases.get(normalized, normalized)


def _build_prompt(text: str, lang: str, size: str, technicality: str) -> str:
    length_guidance = {
        "small": "concise (around 2-3 paragraphs)",
        "medium": "detailed (several paragraphs, covering key aspects)",
        "large": "very detailed and comprehensive (multiple sections, extensive coverage)",
    }.get((size or "medium").lower(), "detailed (several paragraphs)")

    technical_guidance = {
        "non-technical": "for a non-technical team member or client (simple language, focus on purpose and value).",
        "technical": "for a software developer (mention key technologies, structure, and how to get started).",
        "expert": "for an expert in the domain (deep dive into architecture, advanced concepts, and potential challenges).",
    }.get(_normalize_technicality(technicality), "for a software developer.")

    return f"""Analyze the following GitHub repository content and generate a structured HTML summary.
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

Do NOT include markdown fences around your HTML output.
Provide only the HTML content for the summary itself.

Repository Content:
---
{text}
---
End of Repository Content. Generate the HTML summary now.
"""


def _clean_model_output(output: str) -> str:
    cleaned = (output or "").strip()
    if cleaned.startswith("```html"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    return cleaned.strip()

async def generate_summary(
    text: str,
    lang: str = 'en',
    size: str = "medium",
    technicality: str = "technical",
    analysis_id: Optional[int] = None,
) -> str:
    """
    Generates a summary using the configured provider.
    Returns the summary string or raises an AIGenerationError.
    """
    if not text:
        logger.warning("AI Analyzer: No text content provided for summarization.")
        raise ValueError("No text content received by analyzer.")

    prompt = _build_prompt(text=text, lang=lang, size=size, technicality=technicality)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
    logger.info(
        "AI Analyzer: Prompt prepared for analysis_id=%s (input_chars=%d, prompt_chars=%d, prompt_hash=%s).",
        analysis_id,
        len(text),
        len(prompt),
        prompt_hash,
    )

    try:
        logger.info("AI Analyzer: Sending request to provider '%s' for analysis_id=%s.", settings.AI_PROVIDER, analysis_id)
        provider = _get_summary_provider()
        final_summary = _clean_model_output(await provider.generate(prompt))
        logger.info("AI Analyzer: Summary generated for analysis_id=%s. Length=%d chars.", analysis_id, len(final_summary))

        return final_summary

    except AIInitializationError:
        raise
    except Exception as exc:
        if isinstance(exc, AIGenerationError):
            raise
        logger.error("AI Analyzer: Error during provider call: %s", exc, exc_info=True)
        raise AIGenerationError(
            f"Failed to generate summary due to an API error: {type(exc).__name__}"
        ) from exc