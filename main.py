"""Entry point for ALI."""

from __future__ import annotations

import asyncio
import logging
import os

from ali.core.orchestrator import Orchestrator
from ali.models.gemma import ensure_gemma_model_cached


async def main() -> None:
    """Boot the orchestrator and start perception loops."""
    orchestrator = Orchestrator()
    logging.getLogger("ali").info("Starting ALI orchestrator")
    await orchestrator.start()


def _auto_install_model() -> None:
    if os.getenv("ALI_AUTO_INSTALL_MODEL", "true").lower() in {"1", "true", "yes"}:
        ensure_gemma_model_cached()


if __name__ == "__main__":
    try:
        _auto_install_model()
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
