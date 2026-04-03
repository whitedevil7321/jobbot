import httpx
import json
import logging
from typing import Optional
from backend.config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self):
        self.base_url = settings.ollama_host
        self.model = settings.ollama_model
        self.timeout = 120.0

    async def is_running(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                r.raise_for_status()
                data = r.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []

    async def generate(self, prompt: str, model: Optional[str] = None, temperature: float = 0.7) -> str:
        target_model = model or self.model
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
                r.raise_for_status()
                return r.json().get("response", "").strip()
        except Exception as e:
            logger.error(f"Ollama generate failed: {e}")
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
