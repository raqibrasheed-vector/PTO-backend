import logging
from logging import Logger, LogRecord


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    green = "\x1b[38;5;70m"
    format_schema: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    FORMATS = {
        logging.DEBUG: green + format_schema + reset,
        logging.INFO: grey + format_schema + reset,
        logging.WARNING: yellow + format_schema + reset,
        logging.ERROR: red + format_schema + reset,
        logging.CRITICAL: bold_red + format_schema + reset,
    }

    def format(self, record: LogRecord) -> str:
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class SingletonLogger:
    _instance = None

    def __new__(cls) -> "SingletonLogger":
        # Ensure that only one instance of the logger is created
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_logger()
        return cls._instance

    def _initialize_logger(self) -> None:
        """Initialize the logger setup."""
        self._logger: Logger = logging.getLogger("workflow_logger")
        self._logger.setLevel(logging.DEBUG)

        # Create a console handler and set level to debug
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)

        console_handler.setFormatter(CustomFormatter())

        # Add the handler to the logger
        self._logger.addHandler(console_handler)

    def get_logger(self) -> Logger:
        """Return the logger instance."""
        return self._logger
