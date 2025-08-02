import logging
from logging.handlers import RotatingFileHandler
from typing import Optional


def setup_logging(
        level: str = "INFO",
        log_file: Optional[str] = None,
        *,
        max_bytes: int = 5_000_000,
        backup_count: int = 3,
):
    """
    Configure root logger:
      - Console output
      - Optional rotating file output
      - Idempotent (won't add handlers twice)
    """
    root = logging.getLogger()
    if root.handlers:
        return

    # Validate level
    lvl = level.upper()
    if lvl not in logging._nameToLevel:
        raise ValueError(f"Invalid log level: {level!r}")
    numeric_level = logging._nameToLevel[lvl]

    fmt = "%(asctime)s %(name)-12s %(levelname)-8s %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers = [logging.StreamHandler()]

    if log_file:
        rfh = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
        handlers.append(rfh)

    logging.basicConfig(
        level=numeric_level,
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
    )