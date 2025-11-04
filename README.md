# Digantara Instruments

A Python library for controlling and automating test instruments used in Digantara's testing infrastructure.

## Features

- Unified interface for various test equipment
- Support for multiple instrument types (oscilloscopes, power supplies, DMMs)
- Web-based control interface
- Scriptable test automation

## Installation

### Prerequisites

- Python 3.8 or higher
- Required system dependencies (VISA, USB drivers, etc.)

### Using pip

```bash
pip install -e .
```

For development with additional tools:

```bash
pip install -e ".[dev]"
```

## Usage

```python
from instrument_control import KeithleyPowerSupply

# Connect to power supply
psu = KeithleyPowerSupply("TCPIP0::192.168.1.100::inst0::INSTR")
psu.set_voltage(3.3)
psu.set_current_limit(1.0)
psu.output_on()
```

## Supported Instruments

- **Keithley 2400 Series** - SourceMeter
- **Keysight DSOX1000 Series** - Oscilloscopes
- And more...

## Development

### Code Style

This project uses:
- Black for code formatting
- isort for import sorting
- mypy for static type checking

### Testing

Run tests with:

```bash
pytest
```

## License

Proprietary - © Digantara Research and Technologies Pvt. Ltd.

## Contributing

For internal contributions, please follow the standard Git workflow:
1. Create a feature branch
2. Make your changes
3. Submit a pull request for review
