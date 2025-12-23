#!/usr/bin/env python3
"""Install ALI dependencies and download the default local model."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def install_deps(requirements: Path) -> None:
    if requirements.exists():
        _run([sys.executable, "-m", "pip", "install", "-r", str(requirements)])
    else:
        raise FileNotFoundError(f"Requirements file not found: {requirements}")


def download_model(model_id: str, cache_dir: Path, force: bool) -> None:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("huggingface_hub is not installed. Install dependencies first.") from exc

    cache_dir.mkdir(parents=True, exist_ok=True)
    local_dir = cache_dir / model_id.replace("/", "__")
    snapshot_download(
        repo_id=model_id,
        cache_dir=str(cache_dir),
        local_dir=str(local_dir),
        local_dir_use_symlinks=False,
        resume_download=not force,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install ALI and its local models.")
    parser.add_argument(
        "--skip-deps",
        action="store_true",
        help="Skip installing Python dependencies.",
    )
    parser.add_argument(
        "--model-id",
        default="google/gemma-3-270m",
        help="Hugging Face model ID to download.",
    )
    parser.add_argument(
        "--cache-dir",
        default="ali/models/cache",
        help="Directory for model downloads.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download of model artifacts.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    requirements = Path("requirements.txt")
    if not args.skip_deps:
        install_deps(requirements)
    download_model(args.model_id, Path(args.cache_dir), args.force)
    print("ALI installation complete. Model cached in:", args.cache_dir)


if __name__ == "__main__":
    main()
