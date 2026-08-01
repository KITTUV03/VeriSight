"""
Structured logging for VeriSight framework.

Provides colored console output via Rich and file logging for audit trails.
Each agent and module gets a named logger with consistent formatting.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# Custom theme for VeriSight log output
VERISIGHT_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "critical": "bold white on red",
    "agent": "bold magenta",
    "parser": "bold green",
    "rag": "bold blue",
})

console = Console(theme=VERISIGHT_THEME)

_configured = False


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
) -> None:
    """
    Configure logging for the VeriSight framework.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        log_file: Optional path to write logs to a file.
    """
    global _configured
    if _configured:
        return

    log_level = getattr(logging, level.upper(), logging.INFO)

    # Rich handler for console
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        markup=True,
        rich_tracebacks=True,
    )
    rich_handler.setLevel(log_level)

    handlers: list[logging.Handler] = [rich_handler]

    # File handler if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_path))
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s"
            )
        )
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True,
    )

    # Suppress noisy third-party loggers
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger for a VeriSight component.

    Args:
        name: Component name (e.g., 'agent1', 'rtl_parser', 'rag').

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(f"verisight.{name}")
