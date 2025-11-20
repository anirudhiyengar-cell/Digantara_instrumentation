#!/usr/bin/env python3
"""
Security Utilities for Instrument Control

Provides input validation, sanitization, and security functions to prevent
common vulnerabilities including path traversal, injection attacks, and
malformed input exploitation.

Author: Digantara Research and Technologies
Version: 1.0.0
License: MIT
"""

import re
from pathlib import Path
from typing import Union, Optional
import logging

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Raised when security validation fails."""
    pass


def validate_visa_address(address: str) -> bool:
    """
    Validate VISA address format to prevent injection attacks.

    Accepts only standard VISA resource strings following the format:
    - USB: USB0::0x1234::0x5678::SERIALNO::INSTR
    - TCPIP: TCPIP0::192.168.1.100::INSTR
    - GPIB: GPIB0::10::INSTR
    - ASRL: ASRL1::INSTR

    Args:
        address: VISA resource string to validate

    Returns:
        True if valid, False otherwise

    Raises:
        SecurityError: If address contains potentially malicious patterns

    Examples:
        >>> validate_visa_address("USB0::0x05E6::0x6500::04561287::INSTR")
        True
        >>> validate_visa_address("USB0; rm -rf /")
        False
    """
    if not address or not isinstance(address, str):
        return False

    # Check for dangerous characters
    dangerous_chars = [';', '|', '&', '$', '`', '\n', '\r', '<', '>']
    if any(char in address for char in dangerous_chars):
        logger.error(f"VISA address contains dangerous characters: {address}")
        raise SecurityError("VISA address contains prohibited characters")

    # Validate against allowed patterns
    patterns = [
        r'^USB\d+::0x[0-9A-Fa-f]{4}::0x[0-9A-Fa-f]{4}::[0-9A-Za-z]+::INSTR$',  # USB
        r'^TCPIP\d*::[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(::[0-9]+)?::INSTR$',  # TCPIP IPv4
        r'^TCPIP\d*::[a-zA-Z0-9\-\.]+::INSTR$',  # TCPIP hostname
        r'^GPIB\d*::\d+::INSTR$',  # GPIB
        r'^ASRL\d+::INSTR$',  # Serial (ASRL)
    ]

    for pattern in patterns:
        if re.match(pattern, address):
            return True

    logger.warning(f"VISA address failed validation: {address}")
    return False


def sanitize_filename(filename: str, allow_path: bool = False) -> str:
    """
    Sanitize filename to prevent path traversal and injection attacks.

    Removes or replaces dangerous characters while preserving valid filenames.
    By default, strips all path components to prevent directory traversal.

    Args:
        filename: Filename to sanitize
        allow_path: If True, allows forward slashes for relative paths (still blocks ..)

    Returns:
        Sanitized filename string

    Raises:
        SecurityError: If filename contains malicious patterns

    Examples:
        >>> sanitize_filename("test.csv")
        'test.csv'
        >>> sanitize_filename("../../etc/passwd")
        'passwd'
        >>> sanitize_filename("data/output.csv", allow_path=True)
        'data/output.csv'
    """
    if not filename or not isinstance(filename, str):
        raise SecurityError("Filename must be a non-empty string")

    # Check for null bytes
    if '\0' in filename:
        raise SecurityError("Filename contains null byte")

    # Check for path traversal attempts
    if '..' in filename:
        raise SecurityError("Filename contains path traversal sequence (..)")

    # Remove dangerous characters
    dangerous_chars = ['|', ';', '&', '$', '`', '\n', '\r', '<', '>', '"', "'"]
    for char in dangerous_chars:
        if char in filename:
            raise SecurityError(f"Filename contains prohibited character: {char}")

    if not allow_path:
        # Strip all directory components - return only the filename
        return Path(filename).name
    else:
        # Allow forward slashes but validate the path
        # Replace backslashes with forward slashes for consistency
        filename = filename.replace('\\', '/')

        # Ensure it doesn't start with / (absolute path)
        if filename.startswith('/'):
            raise SecurityError("Absolute paths not allowed")

        return filename


def sanitize_filepath(filename: str, base_dir: Union[str, Path], create_dirs: bool = False) -> Path:
    """
    Create a safe file path within a specified base directory.

    Prevents path traversal attacks by ensuring the final path is within
    the specified base directory. Optionally creates intermediate directories.

    Args:
        filename: User-provided filename or relative path
        base_dir: Base directory that must contain the final path
        create_dirs: If True, create intermediate directories

    Returns:
        Validated Path object within base_dir

    Raises:
        SecurityError: If final path would escape base_dir

    Examples:
        >>> sanitize_filepath("output.csv", "/data")
        PosixPath('/data/output.csv')
        >>> sanitize_filepath("../../../etc/passwd", "/data")
        SecurityError: Path traversal attempt detected
    """
    base_dir = Path(base_dir).resolve()

    # Sanitize the filename first
    safe_filename = sanitize_filename(filename, allow_path=True)

    # Construct the full path
    full_path = (base_dir / safe_filename).resolve()

    # Verify the final path is within base_dir
    try:
        full_path.relative_to(base_dir)
    except ValueError:
        raise SecurityError(
            f"Path traversal attempt detected: {filename} would escape {base_dir}"
        )

    # Create directories if requested
    if create_dirs and not full_path.parent.exists():
        full_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {full_path.parent}")

    return full_path


def validate_numeric_range(value: Union[int, float],
                          min_val: Optional[Union[int, float]] = None,
                          max_val: Optional[Union[int, float]] = None,
                          param_name: str = "value") -> bool:
    """
    Validate numeric input is within acceptable range.

    Args:
        value: Numeric value to validate
        min_val: Minimum acceptable value (inclusive)
        max_val: Maximum acceptable value (inclusive)
        param_name: Parameter name for error messages

    Returns:
        True if valid

    Raises:
        ValueError: If value is out of range

    Examples:
        >>> validate_numeric_range(5.0, 0.0, 10.0, "voltage")
        True
        >>> validate_numeric_range(15.0, 0.0, 10.0, "voltage")
        ValueError: voltage must be between 0.0 and 10.0, got 15.0
    """
    if not isinstance(value, (int, float)):
        raise ValueError(f"{param_name} must be numeric, got {type(value).__name__}")

    if min_val is not None and value < min_val:
        raise ValueError(f"{param_name} must be >= {min_val}, got {value}")

    if max_val is not None and value > max_val:
        raise ValueError(f"{param_name} must be <= {max_val}, got {value}")

    return True


def validate_string_input(value: str,
                         allowed_chars: Optional[str] = None,
                         max_length: int = 1024,
                         param_name: str = "input") -> bool:
    """
    Validate string input for dangerous content.

    Args:
        value: String to validate
        allowed_chars: Regex pattern of allowed characters
        max_length: Maximum string length
        param_name: Parameter name for error messages

    Returns:
        True if valid

    Raises:
        ValueError: If validation fails
        SecurityError: If dangerous content detected
    """
    if not isinstance(value, str):
        raise ValueError(f"{param_name} must be a string")

    if len(value) > max_length:
        raise ValueError(f"{param_name} exceeds maximum length of {max_length}")

    # Check for null bytes
    if '\0' in value:
        raise SecurityError(f"{param_name} contains null byte")

    # Check for control characters (except \n, \r, \t)
    control_chars = [chr(i) for i in range(32) if i not in (9, 10, 13)]
    if any(char in value for char in control_chars):
        raise SecurityError(f"{param_name} contains control characters")

    # Validate against allowed characters if specified
    if allowed_chars:
        if not re.match(f'^[{allowed_chars}]+$', value):
            raise ValueError(f"{param_name} contains invalid characters")

    return True
