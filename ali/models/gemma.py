"""Local Gemma model loader for ALI."""

from __future__ import annotations

import getpass
import importlib.util
import logging
import os
import webbrowser
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

        if importlib.util.find_spec("torch") is None or importlib.util.find_spec(
            "transformers"
        ) is None:
            raise RuntimeError(
                "Missing dependencies for Gemma. Install requirements.txt before loading the model."
            )

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

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


def ensure_gemma_model_cached(
    *,
    model_id: Optional[str] = None,
    cache_dir: Optional[Path] = None,
    force: bool = False,
) -> bool:
    """Download the Gemma model snapshot if it is not cached yet."""
    if importlib.util.find_spec("huggingface_hub") is None:
        logger.warning(
            "huggingface_hub is not installed; skipping Gemma model download."
        )
        return False

    from huggingface_hub import HfFolder, HfApi, login, snapshot_download
    from huggingface_hub.utils import HfHubHTTPError

    config = GemmaLocalModel._config_from_env()
    resolved_model_id = model_id or config.model_id
    resolved_cache_dir = cache_dir or config.cache_dir
    resolved_cache_dir.mkdir(parents=True, exist_ok=True)
    local_dir = resolved_cache_dir / resolved_model_id.replace("/", "__")

    if not _ensure_huggingface_login(
        resolved_model_id, hf_folder=HfFolder, hf_api=HfApi, login_func=login
    ):
        return False

    try:
        snapshot_download(
            repo_id=resolved_model_id,
            cache_dir=str(resolved_cache_dir),
            local_dir=str(local_dir),
            local_dir_use_symlinks=False,
            resume_download=not force,
        )
    except HfHubHTTPError as exc:
        if getattr(exc.response, "status_code", None) in {401, 403}:
            logger.warning(
                "Hugging Face authentication required to access %s.",
                resolved_model_id,
            )
            if _ensure_huggingface_login(
                resolved_model_id, hf_folder=HfFolder, hf_api=HfApi, login_func=login
            ):
                return ensure_gemma_model_cached(
                    model_id=resolved_model_id, cache_dir=resolved_cache_dir, force=force
                )
        logger.warning("Unable to download Gemma model %s: %s", resolved_model_id, exc)
        return False
    except Exception as exc:
        logger.warning("Unable to download Gemma model %s: %s", resolved_model_id, exc)
        return False
    return True


def _ensure_huggingface_login(
    model_id: str,
    *,
    hf_folder: type,
    hf_api: type,
    login_func: type,
) -> bool:
    token = hf_folder.get_token()
    if token:
        return True

    logger.warning(
        "No Hugging Face token found. Please sign in to access %s.", model_id
    )
    _open_huggingface_login(model_id)
    token = getpass.getpass("Enter your Hugging Face token (leave blank to skip): ")
    if not token.strip():
        logger.warning("Skipping Hugging Face login; model download will be skipped.")
        return False

    login_func(token=token.strip(), add_to_git_credential=True)
    try:
        hf_api().whoami(token=token.strip())
    except Exception:
        logger.warning("Hugging Face login failed; please verify your token.")
        return False
    return True


def _open_huggingface_login(model_id: str) -> None:
    login_url = "https://huggingface.co/login"
    model_url = f"https://huggingface.co/{model_id}"
    webbrowser.open(login_url)
    webbrowser.open(model_url)
