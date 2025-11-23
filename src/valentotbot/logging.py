from __future__ import annotations

import logging
import sys
from typing import Optional

from valentotbot.config import LogLevel


def setup_logging(level: Optional[LogLevel]) -> None:
    """Configure root logger to stdout with the given level."""
    numeric_level = getattr(logging, (level or "INFO").upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
