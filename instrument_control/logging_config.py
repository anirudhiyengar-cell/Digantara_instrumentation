#!/usr/bin/env python3
"""
Centralized Logging Configuration

Provides consistent logging setup across all modules with support for
file rotation, console output, and configurable log levels.

Author: Digantara Research and Technologies
Version: 1.0.0
License: MIT
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


class ColoredFormatter(logging.Formatter):
    """
    Custom formatter with color-coded log levels for console output.

    Uses ANSI color codes for different log levels to improve readability.
    """

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        """Format log record with color codes."""
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname:8s}{self.RESET}"
        return super().format(record)


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    console_output: bool = True,
    colored_output: bool = True,
    log_format: Optional[str] = None
) -> logging.Logger:
    """
    Configure logging for the application.

    Sets up both console and file logging with rotation support.
    Creates a root logger that all modules can use.

    Args:
        level: Logging level (e.g., logging.INFO, logging.DEBUG)
        log_file: Path to log file (None = no file logging)
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup log files to keep
        console_output: Enable console logging
        colored_output: Use colored output for console (if supported)
        log_format: Custom log format string (None = use default)

    Returns:
        Configured root logger

    Example:
        >>> logger = setup_logging(
        ...     level=logging.DEBUG,
        ...     log_file='instrument_control.log',
        ...     console_output=True
        ... )
        >>> logger.info("Application started")
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Default log format
    if log_format is None:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    date_format = '%Y-%m-%d %H:%M:%S'

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)

        # Use colored formatter for console if requested and supported
        if colored_output and hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
            console_formatter = ColoredFormatter(log_format, datefmt=date_format)
        else:
            console_formatter = logging.Formatter(log_format, datefmt=date_format)

        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # File handler with rotation
    if log_file:
        log_path = Path(log_file)

        # Create log directory if it doesn't exist
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(level)

        # File output doesn't use colors
        file_formatter = logging.Formatter(log_format, datefmt=date_format)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        root_logger.info(f"Logging to file: {log_path}")

    return root_logger


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Logger name (typically __name__ of the module)
        level: Optional logging level override

    Returns:
        Configured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Module initialized")
    """
    logger = logging.getLogger(name)

    if level is not None:
        logger.setLevel(level)

    return logger


def log_system_info() -> None:
    """
    Log system and environment information.

    Useful for debugging and audit trails.
    """
    import platform
    import sys

    logger = logging.getLogger('system_info')

    logger.info("="*80)
    logger.info("SYSTEM INFORMATION")
    logger.info("="*80)
    logger.info(f"Python Version: {sys.version}")
    logger.info(f"Platform: {platform.platform()}")
    logger.info(f"Processor: {platform.processor()}")
    logger.info(f"Architecture: {platform.machine()}")
    logger.info(f"Python Executable: {sys.executable}")
    logger.info("="*80)


def log_exception(logger: logging.Logger, exc: Exception, context: str = "") -> None:
    """
    Log an exception with full traceback.

    Args:
        logger: Logger instance to use
        exc: Exception to log
        context: Additional context string

    Example:
        >>> try:
        ...     risky_operation()
        ... except Exception as e:
        ...     log_exception(logger, e, "During instrument connection")
    """
    import traceback

    context_str = f" ({context})" if context else ""
    logger.error(f"Exception occurred{context_str}: {type(exc).__name__}: {exc}")
    logger.debug(f"Full traceback:\n{''.join(traceback.format_tb(exc.__traceback__))}")


class LogContext:
    """
    Context manager for temporary log level changes.

    Useful for debugging specific sections of code without changing
    global log level.

    Example:
        >>> logger = logging.getLogger(__name__)
        >>> with LogContext(logger, logging.DEBUG):
        ...     logger.debug("This will be logged")
        >>> logger.debug("This won't be logged (if default is INFO)")
    """

    def __init__(self, logger: logging.Logger, level: int):
        """
        Initialize log context manager.

        Args:
            logger: Logger to temporarily modify
            level: Temporary log level
        """
        self.logger = logger
        self.level = level
        self.original_level = None

    def __enter__(self):
        """Save current level and set new level."""
        self.original_level = self.logger.level
        self.logger.setLevel(self.level)
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore original log level."""
        self.logger.setLevel(self.original_level)


def create_audit_logger(log_file: str = "audit.log") -> logging.Logger:
    """
    Create a dedicated audit logger for security-sensitive operations.

    Audit logs are always written to file and never suppressed.

    Args:
        log_file: Path to audit log file

    Returns:
        Audit logger instance

    Example:
        >>> audit = create_audit_logger()
        >>> audit.info(f"User {user} connected to instrument {addr}")
    """
    audit_logger = logging.getLogger('audit')
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False  # Don't pass to root logger

    # Create audit log directory
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Rotating file handler for audit logs
    handler = logging.handlers.RotatingFileHandler(
        filename=log_path,
        maxBytes=50 * 1024 * 1024,  # 50 MB
        backupCount=10,
        encoding='utf-8'
    )

    # Detailed format for audit logs
    formatter = logging.Formatter(
        '%(asctime)s - AUDIT - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    audit_logger.addHandler(handler)

    return audit_logger


# Convenience function for logging instrument commands (for audit trail)
def log_instrument_command(instrument_type: str, address: str, command: str,
                          response: Optional[str] = None, user: str = "system") -> None:
    """
    Log instrument command to audit trail.

    Args:
        instrument_type: Type of instrument (e.g., "DMM", "PSU", "Scope")
        address: VISA address of instrument
        command: SCPI command sent
        response: Instrument response (if any)
        user: User who initiated the command

    Example:
        >>> log_instrument_command("DMM", "USB0::...", "*IDN?", "KEITHLEY,DMM6500,...")
    """
    audit = logging.getLogger('audit.commands')

    log_msg = f"[{user}] {instrument_type}@{address}: {command}"
    if response:
        log_msg += f" => {response[:100]}"  # Truncate long responses

    audit.info(log_msg)
