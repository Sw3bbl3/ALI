"""Entry point for ALI."""

from __future__ import annotations

import asyncio

from ali.core.orchestrator import Orchestrator


async def main() -> None:
    """Boot the orchestrator and start perception loops."""
    orchestrator = Orchestrator()
    await orchestrator.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
