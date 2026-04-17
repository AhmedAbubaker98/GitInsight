from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class ProviderConfig:
    model_name: str
    temperature: float = 0.6
    max_output_tokens: Optional[int] = None
    request_timeout_seconds: int = 120


class SummaryProvider(Protocol):
    async def generate(self, prompt: str) -> str:
        """Generate an HTML summary for the provided prompt."""
