import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import settings


LOG_FORMAT = "[%(levelname)s] %(message)s | ts=%(asctime)s | module=%(module)s"
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_FILE = LOG_DIR / "ats_pipeline.log"


def _configure_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("ats")
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter(LOG_FORMAT)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


logger = _configure_logger()


def get_logger(name: str | None = None) -> logging.Logger:
    if not name:
        return logger
    return logging.getLogger("ats").getChild(name)
