from __future__ import annotations

import logging
import logging.handlers
import sys
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ERROR_DIR = ROOT / "Error"
ERROR_DIR.mkdir(parents=True, exist_ok=True)


def _write_unhandled(exc_type, exc, tb):
    try:
        msg = "".join(traceback.format_exception(exc_type, exc, tb))
        (ERROR_DIR / "unhandled.log").write_text(msg, encoding="utf-8")
    except Exception:
        pass



root_logger = logging.getLogger()
if not root_logger.handlers:
    # rotating file to avoid unbounded growth
    fh = logging.handlers.RotatingFileHandler(ERROR_DIR / "app.log", encoding="utf-8", maxBytes=5 * 1024 * 1024, backupCount=3)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root_logger.addHandler(fh)
    # also keep console handler
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root_logger.addHandler(ch)

    # avoid very noisy debug logs by default
    root_logger.setLevel(logging.INFO)

# Capture unhandled exceptions
sys.excepthook = _write_unhandled


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name)
