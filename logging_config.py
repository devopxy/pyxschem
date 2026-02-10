"""
Centralized logging configuration for PyXSchem.

This module configures:
- Rotating file logging capped to ~500 MB total disk usage
- Optional stderr logging for interactive debugging
- Unhandled exception logging for main and worker threads
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


LOG_FILE_NAME = "pyxschem.log"

# Keep total log disk usage around 500 MB: 10 files * 50 MB each.
LOG_MAX_BYTES = 50_000_000
LOG_BACKUP_COUNT = 9
LOG_TOTAL_BUDGET_BYTES = LOG_MAX_BYTES * (LOG_BACKUP_COUNT + 1)

DEFAULT_LOG_DIR = Path.home() / ".pyxschem" / "logs"
FALLBACK_LOG_DIR = Path("/tmp") / "pyxschem" / "logs"

_initialized = False
_log_file_path: Optional[Path] = None
_original_excepthook = sys.excepthook
_original_threading_excepthook = getattr(threading, "excepthook", None)


def _resolve_level(level: str | int | None) -> int:
    """Resolve a user-provided log level to a logging constant."""
    if isinstance(level, int):
        return level

    level_name = str(level or "INFO").upper()
    return getattr(logging, level_name, logging.INFO)


def _log_unhandled_exception(exc_type, exc_value, exc_traceback) -> None:
    """Log uncaught exceptions from the main thread."""
    if issubclass(exc_type, KeyboardInterrupt):
        _original_excepthook(exc_type, exc_value, exc_traceback)
        return

    logging.getLogger("pyxschem.crash").critical(
        "Unhandled exception",
        exc_info=(exc_type, exc_value, exc_traceback),
    )
    _original_excepthook(exc_type, exc_value, exc_traceback)


def _log_thread_exception(args: threading.ExceptHookArgs) -> None:
    """Log uncaught exceptions from worker threads."""
    logging.getLogger("pyxschem.crash").critical(
        "Unhandled thread exception in '%s'",
        args.thread.name if args.thread else "unknown",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )
    if _original_threading_excepthook is not None:
        _original_threading_excepthook(args)


def setup_logging(
    log_level: str | int | None = None,
    log_dir: str | Path | None = None,
    enable_stderr: bool | None = None,
) -> Path:
    """
    Configure process-wide logging.

    The rotating file handler stores logs in:
    - ``$PYXSCHEM_LOG_DIR`` if set, otherwise
    - ``~/.pyxschem/logs``

    Rotation policy:
    - Current file: 50 MB max
    - Backup files: 9
    - Total budget: ~500 MB
    """
    global _initialized
    global _log_file_path

    if _initialized and _log_file_path is not None:
        return _log_file_path

    level = _resolve_level(os.environ.get("PYXSCHEM_LOG_LEVEL", log_level))
    preferred_dir = Path(
        os.environ.get("PYXSCHEM_LOG_DIR", str(log_dir or DEFAULT_LOG_DIR))
    ).expanduser()
    fallback_dir = Path(os.environ.get("PYXSCHEM_FALLBACK_LOG_DIR", str(FALLBACK_LOG_DIR))).expanduser()

    resolved_dir = preferred_dir
    try:
        resolved_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        resolved_dir = fallback_dir
        resolved_dir.mkdir(parents=True, exist_ok=True)
        print(
            f"PyXSchem logging directory '{preferred_dir}' unavailable ({exc}); "
            f"falling back to '{resolved_dir}'.",
            file=sys.stderr,
        )

    _log_file_path = resolved_dir / LOG_FILE_NAME

    if enable_stderr is None:
        enable_stderr = os.environ.get("PYXSCHEM_LOG_TO_STDERR", "1") != "0"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()

    file_handler = RotatingFileHandler(
        _log_file_path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            fmt=(
                "%(asctime)s.%(msecs)03d | %(levelname)-8s | "
                "%(process)d | %(threadName)s | %(name)s:%(lineno)d | %(message)s"
            ),
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(file_handler)

    if enable_stderr:
        stderr_handler = logging.StreamHandler()
        stderr_handler.setLevel(level)
        stderr_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        root_logger.addHandler(stderr_handler)

    logging.captureWarnings(True)
    sys.excepthook = _log_unhandled_exception
    if hasattr(threading, "excepthook"):
        threading.excepthook = _log_thread_exception

    _initialized = True

    logging.getLogger(__name__).info(
        "Logging initialized at '%s' (rotation=%d bytes, backups=%d, total_budget=%d bytes)",
        _log_file_path,
        LOG_MAX_BYTES,
        LOG_BACKUP_COUNT,
        LOG_TOTAL_BUDGET_BYTES,
    )

    return _log_file_path


def get_log_file_path() -> Optional[Path]:
    """Return current log file path, if logging was initialized."""
    return _log_file_path
