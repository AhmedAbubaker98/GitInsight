import logging

import httpx

from ai_analyzer_service.services.providers.base import ProviderConfig

logger = logging.getLogger(__name__)


class LMStudioSummaryProvider:
    def __init__(
        self,
        base_url: str,
        chat_endpoint: str,
        api_key: str | None,
        config: ProviderConfig,
    ):
        self._base_url = base_url.rstrip("/")
        self._chat_endpoint = chat_endpoint
        self._api_key = api_key
        self._config = config

    async def generate(self, prompt: str) -> str:
        endpoint = f"{self._base_url}/{self._chat_endpoint.lstrip('/')}"

        payload = {
            "model": self._config.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self._config.temperature,
        }
        if self._config.max_output_tokens is not None:
            payload["max_tokens"] = self._config.max_output_tokens

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        async with httpx.AsyncClient(timeout=self._config.request_timeout_seconds) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()

        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("LM Studio response contained no choices.")

        first_choice = choices[0]
        message = first_choice.get("message") or {}
        finish_reason = first_choice.get("finish_reason")
        content = message.get("content")
        if isinstance(content, list):
            # Some backends can return structured content segments.
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        if isinstance(content, str):
            content = content.strip()

        # gpt-oss style responses may return reasoning with empty content.
        reasoning = message.get("reasoning")
        if isinstance(reasoning, str):
            reasoning = reasoning.strip()

        logger.info(
            "AI Analyzer (LM Studio): Response metadata finish_reason=%s, content_chars=%d, reasoning_chars=%d.",
            finish_reason,
            len(content or ""),
            len(reasoning or ""),
        )

        if not content:
            if reasoning:
                content = reasoning

        if not content:
            raise RuntimeError("LM Studio response did not include usable content or reasoning.")

        logger.info("AI Analyzer (LM Studio): Summary generated. Length: %s chars.", len(content))
        return content.strip()
