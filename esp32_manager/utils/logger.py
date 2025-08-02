import logging
import logging.config
import sys
from cgitb import handler
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
      - Detailed formatter with module, function, line
      - Idempotent (won't re-configure if already set)
      - Clickable links in supported terminals
    """
    root = logging.getLogger()
    if root.handlers:
        return

    # Validate level
    lvl = level.upper()
    if lvl not in logging._nameToLevel:
        raise ValueError(f"Invalid log level: {level!r}")
    numeric_level = logging._nameToLevel[lvl]

    # Common date format
    datefmt = "%Y-%m-%d %H:%M:%S"

    # Formatters: standard plus detailed
    formatters = {
        'standard': {
            'format': '%(asctime)s - %(name)-12s - %(levelname)-8s - %(message)s',
            'datefmt': datefmt,
        },
        'detailed': {
            'format': (
                '%(asctime)s %(name)-12s %(levelname)-8s '
                '[%(pathname)s:%(lineno)d %(funcName)s()] %(message)s'
            ),
            'datefmt': datefmt,
        },
    }

    handlers = {}
    root_handlers = []

    # Console handler
    handlers['console'] = {
        'class': 'logging.StreamHandler',
        'level': numeric_level,
        'formatter': 'detailed',
        'stream': 'ext://sys.stdout',
    }
    root_handlers.append('console')

    # File Handler
    if log_file:
        handlers['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': numeric_level,
            'formatter': 'detailed',
            'filename': log_file,
            'maxBytes': max_bytes,
            'backupCount': backup_count,
            'encoding': 'utf-8',
        }
        root_handlers.append('file')

    # DictConfig
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': formatters,
        'handlers': handlers,
        'root': {
            'level': numeric_level,
            'handlers': root_handlers,
        },
    }
    logging.config.dictConfig(config)

    # Hook uncaught exceptions into Logger
    def _handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        root.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = _handle_exception