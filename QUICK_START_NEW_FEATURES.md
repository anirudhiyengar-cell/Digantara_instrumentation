# Quick Start Guide - New Security & Production Features

## 🚀 5-Minute Setup

### 1. Install Updated Dependencies
```bash
pip install -r requirements.txt --upgrade
```

### 2. Create Your Environment File
```bash
# Copy the template
cp .env.example .env

# Edit with your settings (at minimum, change these):
nano .env  # or use any text editor
```

**Minimum Required Settings:**
```bash
# In .env file:
VISA_TIMEOUT_MS=10000
LOG_LEVEL=INFO
GRADIO_SERVER_HOST=127.0.0.1
GRADIO_SERVER_PORT=7860
```

### 3. Run Health Check
```bash
python -m instrument_control.health_check
```

Expected output:
```
================================================================================
SYSTEM HEALTH CHECK REPORT
================================================================================
Overall Status: HEALTHY
...
```

### 4. Test Security Features
```bash
python -m pytest tests/test_security.py -v
```

### 5. Run Your Existing Code
```python
# Your existing code works without changes!
from instrument_control import KeithleyDMM6500

dmm = KeithleyDMM6500("USB0::0x05E6::0x6500::04561287::INSTR")
dmm.connect()
# ... rest of your code unchanged
```

---

## 🔒 Using New Security Features

### Safe File Operations
```python
from instrument_control.security import sanitize_filepath
from pathlib import Path

# Prevent path traversal attacks
base_dir = Path("./data")
user_filename = request.get("filename")  # From user input

# OLD WAY (UNSAFE):
# with open(user_filename, 'w') as f:  # DANGEROUS!

# NEW WAY (SAFE):
safe_path = sanitize_filepath(user_filename, base_dir)
with open(safe_path, 'w') as f:
    f.write(data)  # Guaranteed to be in ./data directory
```

### Validate User Input
```python
from instrument_control.security import (
    validate_numeric_range,
    validate_visa_address
)

# Validate voltage input
try:
    voltage = float(user_input)
    validate_numeric_range(voltage, 0.0, 30.0, "voltage")
    # Safe to use
except ValueError as e:
    print(f"Invalid voltage: {e}")

# Validate VISA address
if validate_visa_address(visa_addr):
    # Safe to connect
    instrument.connect()
else:
    print("Invalid VISA address format")
```

---

## ⚙️ Using Configuration System

### Access Configuration
```python
from instrument_control.config import Config

# Get configuration values
timeout = Config.VISA_TIMEOUT_MS
log_level = Config.LOG_LEVEL
data_dir = Config.DATA_EXPORT_DIR

# Get directories
directories = Config.get_data_directories()
# Returns: {'data': Path('...'), 'screenshots': Path('...'), ...}

# Validate configuration before deployment
Config.validate_configuration()  # Raises ValueError if invalid

# Print current configuration
Config.print_configuration()
```

### Customize via Environment
```bash
# In .env or environment variables:
export VISA_TIMEOUT_MS=15000
export LOG_LEVEL=DEBUG
export DATA_EXPORT_DIR=/mnt/data/exports

# Then run your code - it automatically uses these values
python your_script.py
```

---

## 📊 Using Enhanced Logging

### Basic Setup
```python
from instrument_control.logging_config import setup_logging
from instrument_control.config import Config
import logging

# Setup once at application start
setup_logging(
    level=Config.get_log_level(),
    log_file='instrument_control.log',
    console_output=True,
    colored_output=True
)

# Use in your modules
logger = logging.getLogger(__name__)
logger.info("Application started")
logger.debug("Debug information")
logger.warning("Warning message")
logger.error("Error occurred")
```

### Advanced Usage
```python
from instrument_control.logging_config import (
    log_exception,
    LogContext,
    create_audit_logger
)

# Log exceptions with traceback
try:
    risky_operation()
except Exception as e:
    log_exception(logger, e, "During instrument connection")

# Temporary debug mode for specific section
logger = logging.getLogger(__name__)
with LogContext(logger, logging.DEBUG):
    # This section logs at DEBUG level
    detailed_operation()
# Back to normal log level

# Audit logging for security events
audit = create_audit_logger()
audit.info(f"User {username} connected to {instrument_addr}")
```

---

## 🏥 Health Checks and Monitoring

### Command Line
```bash
# Full health check report
python -m instrument_control.health_check

# JSON output for monitoring systems
python -c "
from instrument_control.health_check import get_health_status_json
import json
print(json.dumps(get_health_status_json(), indent=2))
"
```

### In Python Code
```python
from instrument_control.health_check import (
    run_all_health_checks,
    check_visa_backend,
    check_system_resources
)

# Get full health status
status = run_all_health_checks()
if status['overall_status'] != 'healthy':
    print(f"System not healthy: {status}")

# Check specific component
visa_status = check_visa_backend()
if visa_status['status'] == 'unhealthy':
    print("VISA backend not available!")

# Monitor resources
resources = check_system_resources()
print(f"Memory usage: {resources['memory_percent']}%")
print(f"Disk usage: {resources['disk_percent']}%")
```

---

## 🧪 Running Tests

### Basic Tests
```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_security.py -v

# Run with coverage report
pytest tests/ --cov=instrument_control --cov-report=html
# Open htmlcov/index.html in browser
```

### Test Categories
```bash
# Run only unit tests (fast)
pytest tests/ -m unit

# Run only security tests
pytest tests/ -m security

# Skip slow tests
pytest tests/ -m "not slow"
```

---

## 🔐 Production Deployment

### Enable Authentication (Recommended)
```bash
# In .env file:
GRADIO_AUTH_ENABLED=true
GRADIO_USERNAME=admin
GRADIO_PASSWORD=your_strong_password_here
```

### Enable HTTPS (Recommended)
```bash
# Generate self-signed certificate:
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# In .env file:
GRADIO_SSL_ENABLED=true
SSL_CERTFILE=cert.pem
SSL_KEYFILE=key.pem
```

### Run as Service (Linux)
```bash
# Copy service file
sudo cp deployment/digantara-instruments.service /etc/systemd/system/

# Enable and start
sudo systemctl enable digantara-instruments
sudo systemctl start digantara-instruments

# Check status
sudo systemctl status digantara-instruments

# View logs
sudo journalctl -u digantara-instruments -f
```

See `DEPLOYMENT.md` for complete deployment guide.

---

## 🔄 Migrating Existing Code

### No Changes Required!

Your existing code continues to work without modifications:

```python
# This still works exactly as before:
from instrument_control import KeithleyDMM6500, KeithleyPowerSupply

dmm = KeithleyDMM6500("USB0::...")
dmm.connect()
voltage = dmm.measure_dc_voltage()
dmm.disconnect()
```

### Optional: Use New Features

Add new features gradually:

```python
# 1. Setup logging (optional but recommended)
from instrument_control.logging_config import setup_logging
setup_logging()

# 2. Use configuration (optional)
from instrument_control.config import Config
timeout = Config.VISA_TIMEOUT_MS

# 3. Validate inputs (recommended for user-facing apps)
from instrument_control.security import validate_numeric_range

voltage = float(user_input)
validate_numeric_range(voltage, 0, 30, "voltage")

# 4. Your existing code
dmm = KeithleyDMM6500("USB0::...")
# ... rest unchanged
```

---

## 📋 Common Tasks

### Change Log Level
```bash
# Temporary (for current session):
export LOG_LEVEL=DEBUG
python your_script.py

# Permanent (in .env file):
LOG_LEVEL=DEBUG
```

### Change Server Port
```bash
# In .env file:
GRADIO_SERVER_PORT=8080
```

### Custom Data Directory
```bash
# In .env file:
DATA_EXPORT_DIR=/path/to/your/data
SCREENSHOT_DIR=/path/to/screenshots
```

### Check VISA Backends
```python
import pyvisa

# List available backends
rm = pyvisa.ResourceManager()
print(rm.list_resources())
rm.close()

# Try pyvisa-py backend
rm = pyvisa.ResourceManager('@py')
print(rm.list_resources())
rm.close()
```

---

## 🐛 Troubleshooting

### "Module not found" errors
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Or install in development mode
pip install -e .
```

### Health check fails
```bash
# Run verbose health check
python -m instrument_control.health_check

# Check each component individually
python -c "from instrument_control.health_check import check_visa_backend; print(check_visa_backend())"
```

### Tests fail
```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run with verbose output
pytest tests/ -vv -s
```

### Can't connect to instrument
```bash
# List available VISA resources
python -c "import pyvisa; rm = pyvisa.ResourceManager(); print(rm.list_resources())"

# Check health
python -m instrument_control.health_check
```

---

## 📚 Documentation

- **Full Deployment Guide:** [DEPLOYMENT.md](DEPLOYMENT.md)
- **Upgrade Summary:** [UPGRADE_SUMMARY.md](UPGRADE_SUMMARY.md)
- **Environment Template:** [.env.example](.env.example)
- **API Docs:** (Coming soon - run `sphinx-build` if installed)

---

## ✅ Checklist for New Users

- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Create .env file: `cp .env.example .env`
- [ ] Edit .env with your settings
- [ ] Run health check: `python -m instrument_control.health_check`
- [ ] Run tests: `pytest tests/test_security.py -v`
- [ ] Review security features in code
- [ ] Test with your instruments
- [ ] Set strong password if deploying to production
- [ ] Enable HTTPS if accessible remotely
- [ ] Setup automated backups

---

## 🎯 What's New Summary

| Feature | Status | Benefit |
|---------|--------|---------|
| **Security Validation** | ✅ Added | Prevents injection attacks |
| **Thread Safety** | ✅ Added | Prevents race conditions |
| **Configuration System** | ✅ Added | Easy deployment management |
| **Enhanced Logging** | ✅ Added | Better debugging and audit trails |
| **Health Checks** | ✅ Added | System monitoring |
| **Unit Tests** | ✅ Added | Code quality assurance |
| **Deployment Docs** | ✅ Added | Production-ready guidelines |
| **Environment Support** | ✅ Added | Secure configuration management |

---

**Ready to deploy! 🚀**

For questions, see [DEPLOYMENT.md](DEPLOYMENT.md) or run:
```bash
python -m instrument_control.health_check
```
