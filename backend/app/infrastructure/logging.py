import logging
import sys


def configureaza_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )


def obtine_logger(nume: str) -> logging.Logger:
    return logging.getLogger(nume)
