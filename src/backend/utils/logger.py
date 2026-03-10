import logging
import os
import pathlib

_file_handler_attached = False


def _attach_file_handler(logger: logging.Logger) -> None:
    """Add a rotating file handler to root logger once when APP_MODE=1."""
    global _file_handler_attached
    if _file_handler_attached:
        return
    _file_handler_attached = True
    try:
        log_dir = pathlib.Path.home() / "MeetTranscript"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "backend.log"
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler(
            log_path, maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8"
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logging.getLogger().addHandler(fh)
        logger.info(f"Logging to file: {log_path}")
    except Exception as e:
        logger.warning(f"Could not attach file log handler: {e}")


class CustomLog:
    def __init__(self, name="GoogleMeetBot"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)

        if not self.logger.hasHandlers():
            self.logger.addHandler(console_handler)

        if os.environ.get("APP_MODE") == "1":
            _attach_file_handler(self.logger)

    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)
