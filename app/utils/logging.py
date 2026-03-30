from __future__ import annotations

import logging
import sys

from pythonjsonlogger.jsonlogger import JsonFormatter

from app.config import Settings


def configure_logging(settings: Settings) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level.upper())
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(pathname)s %(lineno)d"
        )
    )
    root_logger.addHandler(handler)
