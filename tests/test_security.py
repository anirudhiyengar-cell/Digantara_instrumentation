#!/usr/bin/env python3
"""
Unit Tests for Security Module

Tests input validation, sanitization, and security functions.
"""

import unittest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from instrument_control.security import (
    validate_visa_address,
    sanitize_filename,
    sanitize_filepath,
    validate_numeric_range,
    validate_string_input,
    SecurityError
)


class TestVisaAddressValidation(unittest.TestCase):
    """Test VISA address validation."""

    def test_valid_usb_address(self):
        """Test valid USB VISA address."""
        self.assertTrue(validate_visa_address("USB0::0x05E6::0x6500::04561287::INSTR"))

    def test_valid_tcpip_address(self):
        """Test valid TCPIP VISA address."""
        self.assertTrue(validate_visa_address("TCPIP0::192.168.1.100::INSTR"))

    def test_valid_gpib_address(self):
        """Test valid GPIB VISA address."""
        self.assertTrue(validate_visa_address("GPIB0::10::INSTR"))

    def test_valid_asrl_address(self):
        """Test valid ASRL (serial) VISA address."""
        self.assertTrue(validate_visa_address("ASRL1::INSTR"))

    def test_invalid_address_with_semicolon(self):
        """Test that addresses with semicolons are rejected."""
        with self.assertRaises(SecurityError):
            validate_visa_address("USB0; rm -rf /")

    def test_invalid_address_with_pipe(self):
        """Test that addresses with pipes are rejected."""
        with self.assertRaises(SecurityError):
            validate_visa_address("USB0|cat /etc/passwd")

    def test_invalid_address_format(self):
        """Test that malformed addresses are rejected."""
        self.assertFalse(validate_visa_address("INVALID_ADDRESS"))

    def test_empty_address(self):
        """Test that empty addresses are rejected."""
        self.assertFalse(validate_visa_address(""))

    def test_none_address(self):
        """Test that None is rejected."""
        self.assertFalse(validate_visa_address(None))


class TestFilenameSanitization(unittest.TestCase):
    """Test filename sanitization."""

    def test_valid_filename(self):
        """Test that valid filenames pass through."""
        self.assertEqual(sanitize_filename("test.csv"), "test.csv")

    def test_path_traversal_attack(self):
        """Test that path traversal is blocked."""
        with self.assertRaises(SecurityError):
            sanitize_filename("../../etc/passwd")

    def test_strips_path_components(self):
        """Test that directory components are stripped."""
        self.assertEqual(sanitize_filename("/tmp/test.csv"), "test.csv")

    def test_dangerous_characters(self):
        """Test that dangerous characters are rejected."""
        with self.assertRaises(SecurityError):
            sanitize_filename("test;rm -rf /.csv")

    def test_null_byte_injection(self):
        """Test that null bytes are rejected."""
        with self.assertRaises(SecurityError):
            sanitize_filename("test\x00.csv")

    def test_allow_path_mode(self):
        """Test allow_path mode."""
        result = sanitize_filename("data/output.csv", allow_path=True)
        self.assertEqual(result, "data/output.csv")

    def test_absolute_path_rejected(self):
        """Test that absolute paths are rejected even with allow_path."""
        with self.assertRaises(SecurityError):
            sanitize_filename("/absolute/path.csv", allow_path=True)


class TestFilepathSanitization(unittest.TestCase):
    """Test filepath sanitization."""

    def test_safe_filepath(self):
        """Test that safe filepaths work."""
        base_dir = Path("/tmp/test")
        result = sanitize_filepath("output.csv", base_dir)
        expected = base_dir / "output.csv"
        self.assertEqual(result, expected)

    def test_path_traversal_blocked(self):
        """Test that path traversal is blocked."""
        base_dir = Path("/tmp/test")
        with self.assertRaises(SecurityError):
            sanitize_filepath("../../../etc/passwd", base_dir)

    def test_relative_path_within_base(self):
        """Test that relative paths within base work."""
        base_dir = Path("/tmp/test")
        result = sanitize_filepath("subdir/output.csv", base_dir)
        self.assertTrue(str(result).startswith(str(base_dir)))


class TestNumericValidation(unittest.TestCase):
    """Test numeric range validation."""

    def test_value_within_range(self):
        """Test that values within range are accepted."""
        self.assertTrue(validate_numeric_range(5.0, 0.0, 10.0))

    def test_value_below_minimum(self):
        """Test that values below minimum are rejected."""
        with self.assertRaises(ValueError):
            validate_numeric_range(-1.0, 0.0, 10.0)

    def test_value_above_maximum(self):
        """Test that values above maximum are rejected."""
        with self.assertRaises(ValueError):
            validate_numeric_range(15.0, 0.0, 10.0)

    def test_boundary_values(self):
        """Test that boundary values are accepted."""
        self.assertTrue(validate_numeric_range(0.0, 0.0, 10.0))
        self.assertTrue(validate_numeric_range(10.0, 0.0, 10.0))

    def test_non_numeric_value(self):
        """Test that non-numeric values are rejected."""
        with self.assertRaises(ValueError):
            validate_numeric_range("not a number", 0.0, 10.0)


class TestStringValidation(unittest.TestCase):
    """Test string input validation."""

    def test_valid_string(self):
        """Test that valid strings pass."""
        self.assertTrue(validate_string_input("test string"))

    def test_string_too_long(self):
        """Test that overly long strings are rejected."""
        long_string = "a" * 2000
        with self.assertRaises(ValueError):
            validate_string_input(long_string, max_length=1024)

    def test_null_byte_in_string(self):
        """Test that null bytes are rejected."""
        with self.assertRaises(SecurityError):
            validate_string_input("test\x00string")

    def test_control_characters(self):
        """Test that control characters are rejected."""
        with self.assertRaises(SecurityError):
            validate_string_input("test\x01string")

    def test_allowed_characters_pattern(self):
        """Test allowed characters pattern matching."""
        self.assertTrue(validate_string_input("test123", allowed_chars="a-z0-9"))
        with self.assertRaises(ValueError):
            validate_string_input("test@123", allowed_chars="a-z0-9")


if __name__ == '__main__':
    unittest.main()
