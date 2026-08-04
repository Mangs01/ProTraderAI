from loguru import logger
import sys

logger.remove()

logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    level="INFO"
)

logger.add(
    "logs/protrader.log",
    rotation="10 MB",
    retention="10 days",
    level="DEBUG"
)