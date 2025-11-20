#!/usr/bin/env python3
"""
SCPI/VISA Communication Wrapper

Provides secure, thread-safe wrapper around PyVISA for SCPI instrument communication.
Includes input validation, proper error handling, and resource management.

Author: Digantara Research and Technologies
Version: 2.0.0
License: MIT
"""

import pyvisa
from typing import Optional, Union, List
import logging
import threading
from .security import validate_visa_address, SecurityError
from .config import Config

logger = logging.getLogger(__name__)


class SCPIError(Exception):
    """Base exception for SCPI communication errors."""
    pass


class SCPIWrapper:
    """
    Thread-safe SCPI/VISA communication wrapper.

    Provides validated, secure communication with SCPI-compliant instruments
    using PyVISA. Includes automatic resource cleanup and error handling.

    Thread Safety:
        All operations are protected by an internal lock for thread-safe access.
    """

    def __init__(self, visa_address: str, timeout_ms: int = None):
        """
        Initialize SCPI wrapper with security validation.

        Args:
            visa_address: VISA resource string (validated for security)
            timeout_ms: Communication timeout in milliseconds (None = use config default)

        Raises:
            ValueError: If visa_address is invalid
            SecurityError: If visa_address contains malicious patterns
        """
        if not visa_address or not isinstance(visa_address, str):
            raise ValueError("visa_address must be a non-empty string")

        # Validate VISA address for security
        if not validate_visa_address(visa_address):
            raise SecurityError(f"Invalid VISA address format: {visa_address}")

        self._visa_address = visa_address
        self._timeout_ms = timeout_ms if timeout_ms is not None else Config.VISA_TIMEOUT_MS
        self._resource_manager: Optional[pyvisa.ResourceManager] = None
        self._instrument: Optional[pyvisa.resources.Resource] = None
        self._is_connected = False
        self._lock = threading.RLock()  # Reentrant lock for thread safety

        logger.debug(f"SCPIWrapper initialized for {visa_address}")

    def connect(self) -> bool:
        """
        Establish connection to VISA instrument with proper error handling.

        Returns:
            True if connection successful, False otherwise

        Thread Safety:
            Protected by internal lock
        """
        with self._lock:
            if self._is_connected:
                logger.warning(f"Already connected to {self._visa_address}")
                return True

            try:
                # Get VISA backend from config
                backend = Config.get_visa_backend_string()
                self._resource_manager = pyvisa.ResourceManager(backend)
                logger.debug(f"VISA ResourceManager created (backend: {backend or 'default'})")

                # Open resource connection
                self._instrument = self._resource_manager.open_resource(self._visa_address)
                logger.info(f"Opened connection to {self._visa_address}")

                # Configure communication parameters
                self._instrument.timeout = self._timeout_ms
                self._instrument.read_termination = '\n'
                self._instrument.write_termination = '\n'

                self._is_connected = True
                logger.info(f"Successfully connected to {self._visa_address}")
                return True

            except pyvisa.errors.VisaIOError as e:
                logger.error(f"VISA I/O error connecting to {self._visa_address}: {e}")
                self._cleanup_connection()
                return False

            except Exception as e:
                logger.error(f"Unexpected error connecting to {self._visa_address}")
                logger.debug(f"Exception details: {e}", exc_info=True)
                self._cleanup_connection()
                return False

    def disconnect(self) -> None:
        """
        Safely disconnect from instrument with proper resource cleanup.

        Uses try-finally to ensure resources are always cleaned up,
        even if errors occur during disconnection.

        Thread Safety:
            Protected by internal lock
        """
        with self._lock:
            if not self._is_connected:
                logger.debug("disconnect() called but not connected")
                return

            try:
                if self._instrument:
                    try:
                        self._instrument.close()
                        logger.debug("Instrument connection closed")
                    except Exception as e:
                        logger.warning(f"Error closing instrument: {e}")

                if self._resource_manager:
                    try:
                        self._resource_manager.close()
                        logger.debug("ResourceManager closed")
                    except Exception as e:
                        logger.warning(f"Error closing ResourceManager: {e}")

            finally:
                # Always cleanup state, even if close() fails
                self._cleanup_connection()
                logger.info(f"Disconnected from {self._visa_address}")

    def _cleanup_connection(self) -> None:
        """
        Reset internal state after disconnection.

        Should only be called from connect() or disconnect().
        """
        self._is_connected = False
        self._instrument = None
        self._resource_manager = None

    @property
    def is_connected(self) -> bool:
        """
        Check connection status.

        Returns:
            True if connected, False otherwise

        Thread Safety:
            Read-only property, no lock needed
        """
        return self._is_connected

    @property
    def visa_address(self) -> str:
        """Get the VISA address for this wrapper."""
        return self._visa_address

    def write(self, command: str) -> None:
        """
        Write SCPI command to instrument.

        Args:
            command: SCPI command string

        Raises:
            ConnectionError: If not connected
            SCPIError: If write operation fails

        Thread Safety:
            Protected by internal lock
        """
        with self._lock:
            if not self.is_connected or not self._instrument:
                raise ConnectionError(f"Instrument not connected: {self._visa_address}")

            try:
                self._instrument.write(command)
                logger.debug(f"SCPI Write: {command}")

            except pyvisa.errors.VisaIOError as e:
                logger.error(f"VISA I/O error writing command '{command}': {e}")
                raise SCPIError(f"Failed to write command: {e}") from e

            except Exception as e:
                logger.error(f"Unexpected error writing command '{command}'")
                logger.debug(f"Exception details: {e}", exc_info=True)
                raise SCPIError(f"Unexpected error during write: {e}") from e

    def query(self, command: str) -> str:
        """
        Query instrument with SCPI command and return response.

        Args:
            command: SCPI query command (typically ends with '?')

        Returns:
            Instrument response string

        Raises:
            ConnectionError: If not connected
            SCPIError: If query operation fails

        Thread Safety:
            Protected by internal lock
        """
        with self._lock:
            if not self.is_connected or not self._instrument:
                raise ConnectionError(f"Instrument not connected: {self._visa_address}")

            try:
                response = self._instrument.query(command)
                logger.debug(f"SCPI Query: {command} => {response.strip()}")
                return response

            except pyvisa.errors.VisaIOError as e:
                logger.error(f"VISA I/O error querying '{command}': {e}")
                raise SCPIError(f"Failed to query: {e}") from e

            except Exception as e:
                logger.error(f"Unexpected error querying '{command}'")
                logger.debug(f"Exception details: {e}", exc_info=True)
                raise SCPIError(f"Unexpected error during query: {e}") from e

    def query_binary_values(self, command: str, datatype: str = 'B',
                           is_big_endian: bool = False,
                           container: type = list) -> Union[List, bytes]:
        """
        Query instrument for binary data.

        Args:
            command: SCPI query command
            datatype: Data type specifier ('B'=unsigned byte, 'H'=short, 'f'=float, etc.)
            is_big_endian: True for big-endian byte order
            container: Container type for returned data (list, bytes, etc.)

        Returns:
            Binary data in specified container type

        Raises:
            ConnectionError: If not connected
            SCPIError: If query operation fails

        Thread Safety:
            Protected by internal lock
        """
        with self._lock:
            if not self.is_connected or not self._instrument:
                raise ConnectionError(f"Instrument not connected: {self._visa_address}")

            try:
                data = self._instrument.query_binary_values(
                    command,
                    datatype=datatype,
                    is_big_endian=is_big_endian,
                    container=container
                )
                logger.debug(f"SCPI Binary Query: {command} => {len(data)} values")
                return data

            except pyvisa.errors.VisaIOError as e:
                logger.error(f"VISA I/O error in binary query '{command}': {e}")
                raise SCPIError(f"Failed to query binary data: {e}") from e

            except Exception as e:
                logger.error(f"Unexpected error in binary query '{command}'")
                logger.debug(f"Exception details: {e}", exc_info=True)
                raise SCPIError(f"Unexpected error during binary query: {e}") from e

    def read_raw(self) -> bytes:
        """
        Read raw bytes from instrument.

        Returns:
            Raw bytes from instrument

        Raises:
            ConnectionError: If not connected
            SCPIError: If read operation fails

        Thread Safety:
            Protected by internal lock
        """
        with self._lock:
            if not self.is_connected or not self._instrument:
                raise ConnectionError(f"Instrument not connected: {self._visa_address}")

            try:
                data = self._instrument.read_raw()
                logger.debug(f"SCPI Read Raw: {len(data)} bytes")
                return data

            except pyvisa.errors.VisaIOError as e:
                logger.error(f"VISA I/O error reading raw data: {e}")
                raise SCPIError(f"Failed to read raw data: {e}") from e

            except Exception as e:
                logger.error("Unexpected error reading raw data")
                logger.debug(f"Exception details: {e}", exc_info=True)
                raise SCPIError(f"Unexpected error during read: {e}") from e

    def clear(self) -> None:
        """
        Clear instrument input/output buffers.

        Raises:
            ConnectionError: If not connected
            SCPIError: If clear operation not supported or fails
        """
        with self._lock:
            if not self.is_connected or not self._instrument:
                raise ConnectionError(f"Instrument not connected: {self._visa_address}")

            try:
                self._instrument.clear()
                logger.debug("Instrument buffers cleared")

            except pyvisa.errors.VisaIOError as e:
                logger.debug(f"Clear operation not supported or failed: {e}")
                # Don't raise - clear() not supported by all instruments

            except Exception as e:
                logger.warning(f"Unexpected error clearing buffers: {e}")

    def __enter__(self):
        """Context manager entry - auto-connect."""
        if not self.connect():
            raise ConnectionError(f"Failed to connect to {self._visa_address}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - auto-disconnect."""
        self.disconnect()

    def __repr__(self) -> str:
        """String representation for debugging."""
        status = "connected" if self._is_connected else "disconnected"
        return f"SCPIWrapper('{self._visa_address}', status={status})"
