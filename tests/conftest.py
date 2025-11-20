#!/usr/bin/env python3
"""
Pytest Configuration and Fixtures

Shared fixtures for all tests.
"""

import pytest
import sys
from pathlib import Path
import logging

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def test_data_dir(tmp_path_factory):
    """Create temporary directory for test data."""
    return tmp_path_factory.mktemp("test_data")


@pytest.fixture(scope="session")
def sample_visa_addresses():
    """Provide sample VISA addresses for testing."""
    return {
        'usb': "USB0::0x05E6::0x6500::04561287::INSTR",
        'tcpip': "TCPIP0::192.168.1.100::INSTR",
        'gpib': "GPIB0::10::INSTR",
        'asrl': "ASRL1::INSTR",
        'invalid': "INVALID_ADDRESS",
        'malicious': "USB0; rm -rf /"
    }


@pytest.fixture(autouse=True)
def setup_logging():
    """Configure logging for tests."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


@pytest.fixture
def mock_visa_instrument(mocker):
    """Mock PyVISA instrument for testing without hardware."""
    mock_rm = mocker.Mock()
    mock_instrument = mocker.Mock()

    mock_instrument.query.return_value = "KEITHLEY,DMM6500,12345678,1.0.0"
    mock_instrument.write.return_value = None
    mock_instrument.timeout = 10000

    mock_rm.open_resource.return_value = mock_instrument
    mocker.patch('pyvisa.ResourceManager', return_value=mock_rm)

    return mock_instrument


@pytest.fixture
def temp_env_file(tmp_path):
    """Create temporary .env file for testing."""
    env_file = tmp_path / ".env"
    env_file.write_text("""
VISA_TIMEOUT_MS=5000
LOG_LEVEL=DEBUG
GRADIO_SERVER_PORT=7861
    """)
    return env_file
