from ai_analyzer_service.core.config import settings
from ai_analyzer_service.services.providers.base import ProviderConfig, SummaryProvider
from ai_analyzer_service.services.providers.gemini_provider import GeminiSummaryProvider
from ai_analyzer_service.services.providers.lmstudio_provider import LMStudioSummaryProvider


def create_summary_provider() -> SummaryProvider:
    config = ProviderConfig(
        model_name=settings.AI_MODEL_NAME,
        temperature=settings.AI_TEMPERATURE,
        max_output_tokens=settings.AI_MAX_OUTPUT_TOKENS,
        request_timeout_seconds=settings.AI_REQUEST_TIMEOUT_SECONDS,
    )

    if settings.AI_PROVIDER == "gemini":
        return GeminiSummaryProvider(
            api_key=settings.AI_ANALYZER_MY_GOOGLE_API_KEY or "",
            config=config,
        )

    if settings.AI_PROVIDER == "lmstudio":
        return LMStudioSummaryProvider(
            base_url=settings.AI_LMSTUDIO_BASE_URL or "",
            chat_endpoint=settings.AI_LMSTUDIO_CHAT_ENDPOINT,
            api_key=settings.AI_LMSTUDIO_API_KEY,
            config=config,
        )

    raise ValueError(f"Unsupported AI provider: {settings.AI_PROVIDER}")
