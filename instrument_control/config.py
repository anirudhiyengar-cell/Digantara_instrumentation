#!/usr/bin/env python3
"""
Configuration Management for Instrument Control

Centralized configuration using environment variables with sensible defaults.
Supports .env files for local development and production deployments.

Author: Digantara Research and Technologies
Version: 1.0.0
License: MIT
"""

import os
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded environment from {env_path}")
except ImportError:
    logger.debug("python-dotenv not installed, skipping .env file loading")


class Config:
    """
    Application configuration with environment variable support.

    All settings can be overridden via environment variables.
    Provides type-safe access to configuration values.
    """

    # ========================================================================
    # VISA/SCPI COMMUNICATION SETTINGS
    # ========================================================================

    # Default VISA timeout in milliseconds
    VISA_TIMEOUT_MS: int = int(os.getenv('VISA_TIMEOUT_MS', '10000'))

    # VISA command delay in seconds (between consecutive commands)
    VISA_COMMAND_DELAY: float = float(os.getenv('VISA_COMMAND_DELAY', '0.1'))

    # VISA backend to use (@py for pyvisa-py, empty for system default)
    VISA_BACKEND: str = os.getenv('VISA_BACKEND', '')

    # ========================================================================
    # INSTRUMENT-SPECIFIC TIMING CONSTANTS
    # ========================================================================

    # Keithley Power Supply timing
    PSU_RESET_TIME: float = float(os.getenv('PSU_RESET_TIME', '3.0'))
    PSU_VOLTAGE_SETTLING_TIME: float = float(os.getenv('PSU_VOLTAGE_SETTLING_TIME', '0.5'))
    PSU_CURRENT_SETTLING_TIME: float = float(os.getenv('PSU_CURRENT_SETTLING_TIME', '0.5'))
    PSU_OUTPUT_ENABLE_TIME: float = float(os.getenv('PSU_OUTPUT_ENABLE_TIME', '0.7'))

    # Keithley DMM timing
    DMM_RESET_TIME: float = float(os.getenv('DMM_RESET_TIME', '2.0'))
    DMM_MEASUREMENT_TIMEOUT: int = int(os.getenv('DMM_MEASUREMENT_TIMEOUT', '30000'))

    # Oscilloscope timing
    SCOPE_AUTOSCALE_TIME: float = float(os.getenv('SCOPE_AUTOSCALE_TIME', '2.0'))
    SCOPE_DIGITIZE_TIME: float = float(os.getenv('SCOPE_DIGITIZE_TIME', '0.5'))

    # ========================================================================
    # LOGGING CONFIGURATION
    # ========================================================================

    # Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')

    # Log file path (None = console only)
    LOG_FILE: Optional[str] = os.getenv('LOG_FILE', None)

    # Maximum log file size in bytes before rotation
    LOG_MAX_BYTES: int = int(os.getenv('LOG_MAX_BYTES', '10485760'))  # 10 MB

    # Number of backup log files to keep
    LOG_BACKUP_COUNT: int = int(os.getenv('LOG_BACKUP_COUNT', '5'))

    # ========================================================================
    # WEB INTERFACE (GRADIO) CONFIGURATION
    # ========================================================================

    # Gradio server port (tries ports in range if occupied)
    GRADIO_SERVER_PORT: int = int(os.getenv('GRADIO_SERVER_PORT', '7860'))

    # Gradio server host (0.0.0.0 = all interfaces, 127.0.0.1 = localhost only)
    GRADIO_SERVER_HOST: str = os.getenv('GRADIO_SERVER_HOST', '127.0.0.1')

    # Enable Gradio authentication (requires GRADIO_USERNAME and GRADIO_PASSWORD)
    GRADIO_AUTH_ENABLED: bool = os.getenv('GRADIO_AUTH_ENABLED', 'false').lower() == 'true'

    # Gradio authentication credentials
    GRADIO_USERNAME: str = os.getenv('GRADIO_USERNAME', 'admin')
    GRADIO_PASSWORD: str = os.getenv('GRADIO_PASSWORD', '')

    # Enable HTTPS (requires SSL_CERTFILE and SSL_KEYFILE)
    GRADIO_SSL_ENABLED: bool = os.getenv('GRADIO_SSL_ENABLED', 'false').lower() == 'true'
    SSL_CERTFILE: Optional[str] = os.getenv('SSL_CERTFILE', None)
    SSL_KEYFILE: Optional[str] = os.getenv('SSL_KEYFILE', None)

    # ========================================================================
    # DATA STORAGE AND EXPORT
    # ========================================================================

    # Base directory for data exports
    DATA_EXPORT_DIR: str = os.getenv('DATA_EXPORT_DIR', './data')

    # Base directory for screenshots
    SCREENSHOT_DIR: str = os.getenv('SCREENSHOT_DIR', './screenshots')

    # Base directory for waveform data
    WAVEFORM_DIR: str = os.getenv('WAVEFORM_DIR', './waveforms')

    # Maximum number of data points to store in memory
    MAX_DATA_POINTS: int = int(os.getenv('MAX_DATA_POINTS', '10000'))

    # ========================================================================
    # THREADING AND PERFORMANCE
    # ========================================================================

    # Number of worker threads for measurements
    WORKER_THREADS: int = int(os.getenv('WORKER_THREADS', '3'))

    # Queue size for thread communication
    QUEUE_SIZE: int = int(os.getenv('QUEUE_SIZE', '100'))

    # Measurement polling interval in seconds (for continuous measurements)
    MEASUREMENT_INTERVAL: float = float(os.getenv('MEASUREMENT_INTERVAL', '1.0'))

    # ========================================================================
    # SECURITY SETTINGS
    # ========================================================================

    # Maximum file upload size in bytes
    MAX_UPLOAD_SIZE: int = int(os.getenv('MAX_UPLOAD_SIZE', '10485760'))  # 10 MB

    # Allowed file extensions for uploads (comma-separated)
    ALLOWED_EXTENSIONS: str = os.getenv('ALLOWED_EXTENSIONS', '.csv,.txt,.json,.png,.jpg')

    # Enable input validation
    ENABLE_INPUT_VALIDATION: bool = os.getenv('ENABLE_INPUT_VALIDATION', 'true').lower() == 'true'

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    @classmethod
    def get_data_directories(cls) -> dict:
        """
        Get all data storage directories as Path objects.

        Returns:
            Dictionary mapping directory names to Path objects
        """
        return {
            'data': Path(cls.DATA_EXPORT_DIR),
            'screenshots': Path(cls.SCREENSHOT_DIR),
            'waveforms': Path(cls.WAVEFORM_DIR)
        }

    @classmethod
    def create_data_directories(cls) -> None:
        """
        Create all configured data directories if they don't exist.

        Logs creation of each directory.
        """
        for name, path in cls.get_data_directories().items():
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created {name} directory: {path}")

    @classmethod
    def validate_configuration(cls) -> bool:
        """
        Validate configuration settings.

        Returns:
            True if all settings are valid

        Raises:
            ValueError: If critical settings are invalid
        """
        # Validate VISA timeout
        if cls.VISA_TIMEOUT_MS < 1000 or cls.VISA_TIMEOUT_MS > 300000:
            raise ValueError(f"VISA_TIMEOUT_MS must be 1000-300000, got {cls.VISA_TIMEOUT_MS}")

        # Validate Gradio port
        if cls.GRADIO_SERVER_PORT < 1024 or cls.GRADIO_SERVER_PORT > 65535:
            raise ValueError(f"GRADIO_SERVER_PORT must be 1024-65535, got {cls.GRADIO_SERVER_PORT}")

        # Validate SSL configuration
        if cls.GRADIO_SSL_ENABLED:
            if not cls.SSL_CERTFILE or not cls.SSL_KEYFILE:
                raise ValueError("SSL enabled but SSL_CERTFILE or SSL_KEYFILE not set")

            cert_path = Path(cls.SSL_CERTFILE)
            key_path = Path(cls.SSL_KEYFILE)

            if not cert_path.exists():
                raise ValueError(f"SSL certificate not found: {cert_path}")

            if not key_path.exists():
                raise ValueError(f"SSL key file not found: {key_path}")

        # Validate authentication
        if cls.GRADIO_AUTH_ENABLED and not cls.GRADIO_PASSWORD:
            raise ValueError("Authentication enabled but GRADIO_PASSWORD not set")

        logger.info("Configuration validation passed")
        return True

    @classmethod
    def get_visa_backend_string(cls) -> str:
        """
        Get the VISA backend string for ResourceManager.

        Returns:
            VISA backend string (e.g., '@py' or '')
        """
        if cls.VISA_BACKEND:
            return f"@{cls.VISA_BACKEND}" if not cls.VISA_BACKEND.startswith('@') else cls.VISA_BACKEND
        return ''

    @classmethod
    def get_log_level(cls) -> int:
        """
        Get numeric log level from string.

        Returns:
            Logging level constant (e.g., logging.INFO)
        """
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        return level_map.get(cls.LOG_LEVEL.upper(), logging.INFO)

    @classmethod
    def print_configuration(cls) -> None:
        """Print current configuration (redacts sensitive values)."""
        print("\n" + "="*80)
        print("INSTRUMENT CONTROL SYSTEM - CONFIGURATION")
        print("="*80)

        config_items = [
            ("VISA Configuration", [
                ("Timeout", f"{cls.VISA_TIMEOUT_MS}ms"),
                ("Command Delay", f"{cls.VISA_COMMAND_DELAY}s"),
                ("Backend", cls.VISA_BACKEND or "System Default"),
            ]),
            ("Logging", [
                ("Level", cls.LOG_LEVEL),
                ("File", cls.LOG_FILE or "Console Only"),
                ("Max Size", f"{cls.LOG_MAX_BYTES / 1024 / 1024:.1f} MB"),
            ]),
            ("Gradio Server", [
                ("Host", cls.GRADIO_SERVER_HOST),
                ("Port", cls.GRADIO_SERVER_PORT),
                ("Auth", "Enabled" if cls.GRADIO_AUTH_ENABLED else "Disabled"),
                ("SSL", "Enabled" if cls.GRADIO_SSL_ENABLED else "Disabled"),
            ]),
            ("Data Storage", [
                ("Export Dir", cls.DATA_EXPORT_DIR),
                ("Screenshot Dir", cls.SCREENSHOT_DIR),
                ("Waveform Dir", cls.WAVEFORM_DIR),
                ("Max Points", cls.MAX_DATA_POINTS),
            ]),
        ]

        for section, items in config_items:
            print(f"\n{section}:")
            for key, value in items:
                print(f"  {key:20s}: {value}")

        print("\n" + "="*80 + "\n")


# Initialize directories on module import
Config.create_data_directories()
