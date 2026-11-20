import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def setup_logging(log_level: int = logging.INFO) -> None:
    """
    Настройка логирования:
    - Консольный вывод с форматированием
    - Ротация логов в файл logs/bot.log (до 10 МБ, 5 бэкапов)
    """
    # Создаем директорию для логов, если её нет
    os.makedirs("logs", exist_ok=True)
    log_file_path = os.path.join("logs", "bot.log")

    log_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 1. Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(log_level)

    # 2. Файловый обработчик с ротацией
    file_handler = RotatingFileHandler(
        filename=log_file_path,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(log_level)

    # Корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Очищаем существующие обработчики во избежание дублирования
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Снижаем шум от сторонних библиотек
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
