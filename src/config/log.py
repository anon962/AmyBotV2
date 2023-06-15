from loguru import logger
import loguru
from config import paths


def init_logger():
    def main():
        logger.add(
            paths.LOG_DIR / "main.log",
            rotation="10 MB",
            compression="gz",
            filter=default_filter,
        )

        logger.add(
            paths.LOG_DIR / "server.log",
            rotation="10 MB",
            compression="gz",
            filter=lambda record: "server" in record["extra"].get("tags", []),
            level="TRACE",
        )

        logger.add(
            paths.LOG_DIR / "discord_bot.log",
            rotation="10 MB",
            compression="gz",
            filter=lambda record: "discord_bot" in record["extra"].get("tags", []),
            level="DEBUG",
        )

        logger.add(
            paths.LOG_DIR / "super.log",
            filter=lambda record: "super" in record["extra"].get("tags", []),
            level="TRACE",
        )

        logger.add(
            paths.LOG_DIR / "kedama.log",
            filter=lambda record: "kedama" in record["extra"].get("tags", []),
            level="DEBUG",
        )

        logger.add(
            paths.LOG_DIR / "lottery.log",
            filter=lambda record: "lottery" in record["extra"].get("tags", []),
            level="DEBUG",
        )

    def default_filter(record: "loguru.Record") -> bool:
        tags: list = record["extra"].get("tags", [])
        return "default" in tags or len(tags) == 0

    main()
