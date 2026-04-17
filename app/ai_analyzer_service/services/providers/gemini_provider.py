import logging

import google.generativeai as genai

from ai_analyzer_service.services.providers.base import ProviderConfig

logger = logging.getLogger(__name__)


class GeminiSummaryProvider:
    def __init__(self, api_key: str, config: ProviderConfig):
        self._config = config
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(config.model_name)

    async def generate(self, prompt: str) -> str:
        try:
            token_count_response = await self._model.count_tokens_async(prompt)
            logger.info("AI Analyzer (Gemini): Prompt token count: %s", token_count_response.total_tokens)
        except Exception as exc:
            logger.warning("AI Analyzer (Gemini): Token counting failed: %s", exc, exc_info=True)

        generation_config = genai.types.GenerationConfig(
            temperature=self._config.temperature,
            max_output_tokens=self._config.max_output_tokens,
        )

        response = await self._model.generate_content_async(
            prompt,
            generation_config=generation_config,
        )

        if response.prompt_feedback and response.prompt_feedback.block_reason:
            raise RuntimeError(
                f"Content generation blocked by safety filters: {response.prompt_feedback.block_reason}"
            )

        if not response.candidates or not response.candidates[0].content.parts:
            finish_reason = "UNKNOWN"
            if response.candidates and hasattr(response.candidates[0], "finish_reason"):
                finish_reason = response.candidates[0].finish_reason
            raise RuntimeError(f"No summary content received from Gemini. Finish reason: {finish_reason}")

        finish_reason = "UNKNOWN"
        if response.candidates and hasattr(response.candidates[0], "finish_reason"):
            finish_reason = response.candidates[0].finish_reason

        output = (response.text or "").strip()
        logger.info(
            "AI Analyzer (Gemini): Response metadata finish_reason=%s, output_chars=%d.",
            finish_reason,
            len(output),
        )

        return output
