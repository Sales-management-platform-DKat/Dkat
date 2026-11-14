import logging
import sys

_FORMAT = "%(asctime)s %(levelname)-5s [%(name)s] %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(handler)
    root.setLevel(level)
    # Use our request logger instead of uvicorn's access log
    logging.getLogger("uvicorn.access").disabled = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
