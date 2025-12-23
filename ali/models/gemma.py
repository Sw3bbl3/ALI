"""Local Gemma model loader for ALI."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger("ali.models.gemma")


@dataclass
class GemmaConfig:
    """Configuration for loading Gemma locally."""

    model_id: str = "google/gemma-3-270m"
    cache_dir: Path = Path("ali/models/cache")
    device: Optional[str] = None


class GemmaLocalModel:
    """Lazy-loading wrapper around a local Gemma model."""

    def __init__(self, config: Optional[GemmaConfig] = None) -> None:
        self._config = config or self._config_from_env()
        self._model = None
        self._tokenizer = None
        self._device = self._config.device

    def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int = 120,
        temperature: float = 0.7,
    ) -> str:
        """Generate a response from the model."""
        self._load()
        if not self._model or not self._tokenizer:
            raise RuntimeError("Gemma model failed to load.")

        import torch

        inputs = self._tokenizer(prompt, return_tensors="pt")
        inputs = {key: tensor.to(self._device) for key, tensor in inputs.items()}
        with torch.no_grad():
            output = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=temperature > 0,
                temperature=temperature,
                pad_token_id=self._tokenizer.eos_token_id,
            )
        decoded = self._tokenizer.decode(output[0], skip_special_tokens=True)
        if decoded.startswith(prompt):
            decoded = decoded[len(prompt) :]
        return decoded.strip()

    def _load(self) -> None:
        if self._model and self._tokenizer:
            return

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "Missing dependencies for Gemma. Install requirements.txt before loading the model."
            ) from exc

        cache_dir = self._config.cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._device = self._device or ("cuda" if torch.cuda.is_available() else "cpu")
        dtype = torch.float16 if self._device == "cuda" else torch.float32

        logger.info("Loading Gemma model %s on %s", self._config.model_id, self._device)
        self._tokenizer = AutoTokenizer.from_pretrained(
            self._config.model_id,
            cache_dir=str(cache_dir),
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            self._config.model_id,
            cache_dir=str(cache_dir),
            torch_dtype=dtype,
        )
        self._model.to(self._device)
        self._model.eval()

    @staticmethod
    def _config_from_env() -> GemmaConfig:
        model_id = os.getenv("ALI_GEMMA_MODEL_ID", "google/gemma-3-270m")
        cache_dir = Path(os.getenv("ALI_MODEL_CACHE", "ali/models/cache"))
        device = os.getenv("ALI_MODEL_DEVICE")
        return GemmaConfig(model_id=model_id, cache_dir=cache_dir, device=device)
