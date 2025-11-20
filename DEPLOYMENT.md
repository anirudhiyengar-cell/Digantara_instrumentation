# Deployment Guide

## Table of Contents
1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Production Installation](#production-installation)
3. [Configuration](#configuration)
4. [Security Hardening](#security-hardening)
5. [Running in Production](#running-in-production)
6. [Health Checks and Monitoring](#health-checks-and-monitoring)
7. [Troubleshooting](#troubleshooting)
8. [Backup and Recovery](#backup-and-recovery)

---

## Pre-Deployment Checklist

Before deploying to production, ensure:

- [ ] All unit tests pass (`pytest tests/`)
- [ ] Security scan passes (`bandit -r instrument_control/`)
- [ ] Dependency check passes (`safety check`)
- [ ] `.env` file configured with production values
- [ ] Strong passwords set for authentication
- [ ] SSL certificates obtained and configured (if using HTTPS)
- [ ] Firewall rules configured
- [ ] VISA drivers installed on target system
- [ ] Instruments accessible and tested
- [ ] Backup strategy in place

---

## Production Installation

### 1. System Requirements

**Operating System:**
- Windows 10/11 (recommended for VISA support)
- Ubuntu 20.04+ / Debian 11+
- macOS 11+

**Python:**
- Python 3.8 or higher (3.9+ recommended)

**VISA Drivers:**
- Keysight IO Libraries Suite 2023+ **OR**
- National Instruments NI-VISA 2023+

### 2. Install Python and Create Virtual Environment

```bash
# Create project directory
mkdir -p /opt/digantara
cd /opt/digantara

# Clone or copy project files
git clone <repository-url> instrument-control
cd instrument-control

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install production dependencies
pip install -r requirements.txt

# Install package in development mode (optional, for development)
pip install -e .
```

### 4. Verify Installation

```bash
# Run health check
python -m instrument_control.health_check

# Run tests
pytest tests/ -v

# Check security
bandit -r instrument_control/
```

---

## Configuration

### 1. Create Production Environment File

```bash
# Copy example environment file
cp .env.example .env

# Edit with production values
nano .env  # or your preferred editor
```

### 2. Essential Production Settings

Edit `.env` with the following **minimum** settings:

```bash
# VISA Configuration
VISA_TIMEOUT_MS=10000
LOG_LEVEL=WARNING

# Web Interface
GRADIO_SERVER_HOST=0.0.0.0
GRADIO_SERVER_PORT=7860

# Authentication (REQUIRED for production)
GRADIO_AUTH_ENABLED=true
GRADIO_USERNAME=admin
GRADIO_PASSWORD=<STRONG_PASSWORD_HERE>

# SSL/TLS (STRONGLY RECOMMENDED)
GRADIO_SSL_ENABLED=true
SSL_CERTFILE=/path/to/cert.pem
SSL_KEYFILE=/path/to/key.pem

# Data Storage
DATA_EXPORT_DIR=/opt/digantara/data
SCREENSHOT_DIR=/opt/digantara/screenshots
WAVEFORM_DIR=/opt/digantara/waveforms
```

### 3. Generate SSL Certificates

For production HTTPS:

```bash
# Self-signed certificate (for internal use)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# OR use Let's Encrypt for public-facing deployments:
# Install certbot and obtain certificate
sudo apt-get install certbot
sudo certbot certonly --standalone -d yourdomain.com
```

---

## Security Hardening

### 1. Set Secure File Permissions

```bash
# Restrict .env file access
chmod 600 .env

# Set appropriate ownership
chown root:root .env
```

### 2. Configure Firewall

```bash
# On Linux (UFW):
sudo ufw allow 7860/tcp comment 'Digantara Instrument Control'
sudo ufw enable

# On Windows:
# Use Windows Defender Firewall to allow port 7860
```

### 3. Run as Non-Root User

```bash
# Create dedicated user (Linux)
sudo useradd -r -s /bin/false digantara

# Set ownership
sudo chown -R digantara:digantara /opt/digantara

# Run as digantara user
sudo -u digantara ./venv/bin/python Unified.py
```

### 4. Enable Security Features

Ensure in `.env`:

```bash
ENABLE_INPUT_VALIDATION=true
GRADIO_AUTH_ENABLED=true
GRADIO_SSL_ENABLED=true
```

### 5. Regular Security Updates

```bash
# Update dependencies monthly
pip install --upgrade -r requirements.txt

# Check for vulnerabilities
safety check
bandit -r instrument_control/
```

---

## Running in Production

### Option 1: Systemd Service (Linux - Recommended)

Create `/etc/systemd/system/digantara-instruments.service`:

```ini
[Unit]
Description=Digantara Instrument Control System
After=network.target

[Service]
Type=simple
User=digantara
Group=digantara
WorkingDirectory=/opt/digantara/instrument-control
Environment="PATH=/opt/digantara/instrument-control/venv/bin"
ExecStart=/opt/digantara/instrument-control/venv/bin/python Unified.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable digantara-instruments
sudo systemctl start digantara-instruments

# Check status
sudo systemctl status digantara-instruments

# View logs
sudo journalctl -u digantara-instruments -f
```

### Option 2: Docker Container

Create `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libusb-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 digantara && chown -R digantara:digantara /app
USER digantara

# Expose port
EXPOSE 7860

# Run application
CMD ["python", "Unified.py"]
```

Build and run:

```bash
# Build image
docker build -t digantara-instruments:latest .

# Run container
docker run -d \
  --name digantara-instruments \
  -p 7860:7860 \
  -v /opt/digantara/data:/app/data \
  -v /opt/digantara/.env:/app/.env:ro \
  --device=/dev/bus/usb \
  --restart unless-stopped \
  digantara-instruments:latest

# View logs
docker logs -f digantara-instruments
```

### Option 3: Windows Service

Use NSSM (Non-Sucking Service Manager):

```powershell
# Download and install NSSM
# https://nssm.cc/download

# Install service
nssm install DigantaraInstruments "C:\Digantara\venv\Scripts\python.exe" "C:\Digantara\Unified.py"

# Configure
nssm set DigantaraInstruments AppDirectory "C:\Digantara"
nssm set DigantaraInstruments AppStdout "C:\Digantara\logs\stdout.log"
nssm set DigantaraInstruments AppStderr "C:\Digantara\logs\stderr.log"

# Start service
nssm start DigantaraInstruments
```

---

## Health Checks and Monitoring

### 1. Built-in Health Check

Run health check to verify system status:

```bash
python -m instrument_control.health_check
```

Expected output for healthy system:

```
================================================================================
SYSTEM HEALTH CHECK REPORT
================================================================================
Timestamp: 2025-01-15T10:30:00.000000
Overall Status: HEALTHY

--------------------------------------------------------------------------------

✓ PYTHON_VERSION: HEALTHY
  Python 3.9.7 on Linux-5.15.0-91-generic-x86_64-with-glibc2.31

✓ REQUIRED_PACKAGES: HEALTHY
  8/8 packages installed

✓ VISA_BACKEND: HEALTHY
  2 backend(s) available

✓ DATA_DIRECTORIES: HEALTHY
  3/3 directories writable

✓ LOGGING: HEALTHY
  Logging at WARNING level with 2 handler(s)

✓ SYSTEM_RESOURCES: HEALTHY
  Memory: 45.3% used, Disk: 62.1% used

================================================================================
Summary: 6 healthy, 0 degraded, 0 unhealthy
================================================================================
```

### 2. Monitoring Logs

```bash
# Tail application logs
tail -f logs/instrument_control.log

# Search for errors
grep ERROR logs/instrument_control.log

# View systemd logs (Linux)
journalctl -u digantara-instruments -f --since today
```

### 3. Performance Monitoring

Monitor resource usage:

```bash
# CPU and memory
top -p $(pgrep -f "python Unified.py")

# Detailed statistics
python -c "from instrument_control.health_check import check_system_resources; import json; print(json.dumps(check_system_resources(), indent=2))"
```

---

## Troubleshooting

### Common Issues

#### 1. Cannot Connect to Instrument

**Symptoms:** VISA errors, timeout errors

**Solutions:**
```bash
# Check VISA backend
python -c "import pyvisa; rm = pyvisa.ResourceManager(); print(rm.list_resources())"

# Verify instrument power and connection
# Check VISA address in .env

# Test with NI MAX or Keysight Connection Expert
```

#### 2. Permission Denied Errors

**Symptoms:** Cannot write to data directories

**Solutions:**
```bash
# Fix permissions
sudo chown -R digantara:digantara /opt/digantara
chmod 755 /opt/digantara/data
```

#### 3. Port Already in Use

**Symptoms:** Gradio server won't start

**Solutions:**
```bash
# Find process using port 7860
sudo lsof -i :7860
# Kill the process or change port in .env
GRADIO_SERVER_PORT=7861
```

#### 4. SSL Certificate Errors

**Symptoms:** HTTPS not working

**Solutions:**
```bash
# Verify certificate files exist
ls -l /path/to/cert.pem /path/to/key.pem

# Check certificate validity
openssl x509 -in cert.pem -text -noout

# Regenerate if expired
```

---

## Backup and Recovery

### 1. What to Backup

- Configuration: `.env` file
- Data: All files in `data/`, `screenshots/`, `waveforms/` directories
- Logs: `logs/` directory
- Custom scripts: Any user-created automation scripts

### 2. Backup Script

Create `backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/backup/digantara/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup configuration
cp .env "$BACKUP_DIR/"

# Backup data
cp -r data/ "$BACKUP_DIR/"
cp -r screenshots/ "$BACKUP_DIR/"
cp -r waveforms/ "$BACKUP_DIR/"
cp -r logs/ "$BACKUP_DIR/"

# Create archive
cd /backup/digantara
tar -czf "digantara_backup_$(date +%Y%m%d_%H%M%S).tar.gz" "$(basename $BACKUP_DIR)"

echo "Backup completed: $BACKUP_DIR"
```

### 3. Automated Backups

Add to crontab:

```bash
# Backup daily at 2 AM
0 2 * * * /opt/digantara/instrument-control/backup.sh

# Clean old backups (keep 30 days)
0 3 * * * find /backup/digantara -name "*.tar.gz" -mtime +30 -delete
```

### 4. Recovery Procedure

```bash
# Stop service
sudo systemctl stop digantara-instruments

# Extract backup
tar -xzf digantara_backup_YYYYMMDD_HHMMSS.tar.gz
cd digantara_backup_YYYYMMDD_HHMMSS

# Restore files
cp .env /opt/digantara/instrument-control/
cp -r data/ /opt/digantara/instrument-control/
cp -r screenshots/ /opt/digantara/instrument-control/
cp -r waveforms/ /opt/digantara/instrument-control/

# Restart service
sudo systemctl start digantara-instruments
```

---

## Production Checklist

Before going live:

- [ ] Health check passes
- [ ] All tests pass
- [ ] Security scan passes
- [ ] SSL certificates valid
- [ ] Strong authentication enabled
- [ ] Firewall configured
- [ ] Monitoring enabled
- [ ] Backup system tested
- [ ] Recovery procedure documented
- [ ] User training completed
- [ ] Support contact information documented

---

## Support

For production support:

- **Technical Issues:** Create GitHub issue
- **Security Vulnerabilities:** Email security@digantara.com
- **Emergency:** Contact on-call engineer

---

**Last Updated:** 2025-01-15
**Version:** 1.0.0
**Maintained by:** Digantara Research and Technologies
