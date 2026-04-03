import httpx
import json
import logging
from typing import Optional, List
from backend.config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self):
        self.base_url = settings.ollama_host
        self.model = settings.ollama_model
        self.timeout = 120.0
        self._resolved_model: Optional[str] = None  # cached after first resolve

    async def is_running(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                r.raise_for_status()
                data = r.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []

    async def _resolve_model(self) -> Optional[str]:
        """
        Return the model to use for generation.
        Uses the configured model if it's available; otherwise falls back to the
        first model that Ollama has pulled, and caches the result.
        """
        if self._resolved_model:
            return self._resolved_model

        models = await self.list_models()
        if not models:
            logger.warning(
                "Ollama is running but has no models pulled. "
                f"Run: ollama pull {self.model}"
            )
            return None

        configured_base = self.model.split(":")[0].lower()
        for m in models:
            if m.lower() == self.model.lower() or m.lower().startswith(configured_base + ":"):
                self._resolved_model = m
                logger.info(f"Using Ollama model: {m}")
                return m

        # Configured model not found — use whatever is available
        fallback = models[0]
        logger.warning(
            f"Configured Ollama model '{self.model}' not found. "
            f"Available models: {models}. Using '{fallback}'. "
            f"To use your preferred model run: ollama pull {self.model}"
        )
        self._resolved_model = fallback
        return fallback

    async def generate(self, prompt: str, model: Optional[str] = None, temperature: float = 0.7) -> str:
        target_model = model
        if target_model is None:
            target_model = await self._resolve_model()
            if not target_model:
                logger.warning("No Ollama model available — skipping LLM generation")
                return ""

        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": 600,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.post(f"{self.base_url}/api/generate", json=payload)
                if r.status_code == 404:
                    # Model was resolved but then removed — clear cache and warn
                    self._resolved_model = None
                    logger.warning(f"Ollama model '{target_model}' not found (404). "
                                   f"Run: ollama pull {target_model}")
                    return ""
                r.raise_for_status()
                return r.json().get("response", "").strip()
        except Exception as e:
            logger.warning(f"Ollama generate failed: {e}")
            return ""

    async def pull_model(self, model_name: str):
        """Pull a model, yielding progress lines."""
        payload = {"name": model_name, "stream": True}
        async with httpx.AsyncClient(timeout=600.0) as client:
            async with client.stream("POST", f"{self.base_url}/api/pull", json=payload) as r:
                async for line in r.aiter_lines():
                    if line:
                        yield json.loads(line)


ollama = OllamaClient()
