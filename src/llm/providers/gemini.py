from dataclasses import dataclass

from google import genai
from google.genai import types


@dataclass
class LLMResult:
    """Model output plus token accounting from the provider's usage metadata."""
    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class GeminiProvider:
    # `gemini-3.1-pro` (the spec's nominal default) resolves to this preview alias
    # on the live Gemini API; override with AGENT_LLM_MODEL.
    DEFAULT_MODEL = "gemini-3.1-pro-preview"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    @property
    def model(self) -> str:
        return self._model

    def _generate(self, prompt: str, system: str | None, response_json: bool):
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json" if response_json else None,
        )
        return self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        return self._generate(prompt, system, response_json=False).text

    def call_model_with_usage(
        self, prompt: str, *, system: str | None = None, response_json: bool = False
    ) -> LLMResult:
        response = self._generate(prompt, system, response_json)
        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = getattr(usage, "prompt_token_count", None) if usage else None
        completion_tokens = getattr(usage, "candidates_token_count", None) if usage else None
        return LLMResult(
            text=response.text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
