"""The only module that talks to Gemini. It spaces calls out for the free-tier rate limits, applies
a timeout, backs off after a 429, and can cache responses on disk so eval reruns cost nothing.
FakeLLM stands in for it in tests."""

import asyncio
import hashlib
import time
from collections.abc import Callable

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from . import config


class LLMError(Exception):
    pass


class GeminiLLM:
    def __init__(self, cache: bool = False):
        self.cache = cache
        # For the eval report: all requests, cache hits, network calls, and the network time of
        # each (excluding the wait for a rate-limit slot).
        self.requests = 0
        self.cache_hits = 0
        self.api_calls = 0
        self.latencies_ms: list[int] = []
        self._client: genai.Client | None = None  # created on first use so a missing key isn't fatal
        self._lock = asyncio.Lock()
        self._next_call_at = 0.0  # monotonic time before which no call may start

    async def generate_json(self, prompt: str, schema: type[BaseModel], timeout_s: float) -> str:
        """Return the model's raw JSON text for `schema`. Raises LLMError on API problems."""
        self.requests += 1
        settings = f"{config.GEMINI_MODEL}|{config.GEMINI_THINKING_LEVEL}|{schema.__name__}"
        key = hashlib.sha256(f"{settings}|{prompt}".encode()).hexdigest()
        cache_file = config.CACHE_DIR / f"{key}.json"
        if self.cache and cache_file.exists():
            self.cache_hits += 1
            return cache_file.read_text(encoding="utf-8")
        if not config.GEMINI_API_KEY:
            raise LLMError("GEMINI_API_KEY is not set")
        if self._client is None:
            # attempts=1: retries are ours to decide (backoff below), not the SDK's.
            options = types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1))
            self._client = genai.Client(api_key=config.GEMINI_API_KEY, http_options=options)

        await self._wait_for_slot()
        thinking = None
        if config.GEMINI_THINKING_LEVEL != "none":
            thinking = types.ThinkingConfig(thinking_level=config.GEMINI_THINKING_LEVEL)
        request = self._client.aio.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=schema.model_json_schema(),
                thinking_config=thinking,
            ),
        )
        self.api_calls += 1
        started = time.monotonic()
        try:
            response = await asyncio.wait_for(request, timeout_s)
        except TimeoutError as exc:
            raise LLMError(f"no response within {timeout_s:.0f}s") from exc
        except errors.APIError as exc:
            if exc.code == 429:
                self._next_call_at = max(self._next_call_at, time.monotonic() + config.LLM_BACKOFF_SECONDS)
                # Google's message names the quota that ran out (per minute or per day), which
                # decides whether waiting helps; keep it for the decision log.
                detail = " ".join(str(exc.message or "").split())[:300]
                raise LLMError(f"rate limited (429); pausing LLM calls for {config.LLM_BACKOFF_SECONDS:.0f}s. {detail}") from exc
            raise LLMError(f"Gemini error {exc.code}: {exc.message}") from exc

        self.latencies_ms.append(int((time.monotonic() - started) * 1000))
        text = response.text or ""
        # Cache only valid output, so the analyzer's retry of a bad response really asks again.
        if self.cache and _is_valid(text, schema):
            config.CACHE_DIR.mkdir(exist_ok=True)
            cache_file.write_text(text, encoding="utf-8")
        return text

    async def _wait_for_slot(self) -> None:
        """Start calls at least MIN_SECONDS_BETWEEN_LLM_CALLS apart across all rooms (the quota is
        per API key). The lock makes concurrent callers queue up in order."""
        async with self._lock:
            # A loop, not one sleep: a 429 while we slept pushes the next slot later.
            while (delay := self._next_call_at - time.monotonic()) > 0:
                await asyncio.sleep(delay)
            self._next_call_at = time.monotonic() + config.MIN_SECONDS_BETWEEN_LLM_CALLS


def _is_valid(text: str, schema: type[BaseModel]) -> bool:
    try:
        schema.model_validate_json(text)
        return True
    except ValidationError:
        return False


class FakeLLM:
    """Test double. `respond(prompt, schema)` returns a pydantic instance or a JSON string, or
    raises to simulate an API failure. Every prompt is kept for assertions."""

    def __init__(self, respond: Callable[[str, type[BaseModel]], BaseModel | str]):
        self.respond = respond
        self.prompts: list[str] = []

    async def generate_json(self, prompt: str, schema: type[BaseModel], timeout_s: float) -> str:
        self.prompts.append(prompt)
        result = self.respond(prompt, schema)
        return result if isinstance(result, str) else result.model_dump_json()


LLM = GeminiLLM | FakeLLM
