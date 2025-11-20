#!/usr/bin/env python3
"""
Health Check and System Diagnostics

Provides system health monitoring, diagnostics, and status reporting
for instrument control infrastructure.

Author: Digantara Research and Technologies
Version: 1.0.0
License: MIT
"""

import platform
import sys
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class HealthStatus:
    """Health status constants."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


def check_python_version() -> Dict[str, Any]:
    """
    Check Python version compatibility.

    Returns:
        Dictionary with version information and status
    """
    version_info = sys.version_info
    version_str = f"{version_info.major}.{version_info.minor}.{version_info.micro}"

    # Require Python 3.8+
    is_compatible = version_info >= (3, 8)

    return {
        "check": "python_version",
        "status": HealthStatus.HEALTHY if is_compatible else HealthStatus.UNHEALTHY,
        "version": version_str,
        "required": ">=3.8",
        "compatible": is_compatible,
        "details": f"Python {version_str} on {platform.platform()}"
    }


def check_required_packages() -> Dict[str, Any]:
    """
    Check if all required packages are installed.

    Returns:
        Dictionary with package status information
    """
    required_packages = [
        'pyvisa',
        'numpy',
        'pandas',
        'matplotlib',
        'gradio',
        'PIL',  # Pillow
        'dotenv',  # python-dotenv
    ]

    missing_packages = []
    installed_packages = {}

    for package_name in required_packages:
        try:
            if package_name == 'PIL':
                import PIL
                module = PIL
            elif package_name == 'dotenv':
                import dotenv
                module = dotenv
            else:
                module = __import__(package_name)

            version = getattr(module, '__version__', 'unknown')
            installed_packages[package_name] = version

        except ImportError:
            missing_packages.append(package_name)
            installed_packages[package_name] = "NOT INSTALLED"

    status = HealthStatus.HEALTHY if not missing_packages else HealthStatus.UNHEALTHY

    return {
        "check": "required_packages",
        "status": status,
        "installed": installed_packages,
        "missing": missing_packages,
        "details": f"{len(installed_packages) - len(missing_packages)}/{len(required_packages)} packages installed"
    }


def check_visa_backend() -> Dict[str, Any]:
    """
    Check VISA backend availability.

    Returns:
        Dictionary with VISA backend status
    """
    try:
        import pyvisa

        backends = []
        errors = []

        # Try default backend
        try:
            rm = pyvisa.ResourceManager()
            backends.append({
                'name': 'default',
                'available': True,
                'backend': str(rm.visalib)
            })
            rm.close()
        except Exception as e:
            errors.append(f"Default backend error: {e}")

        # Try pyvisa-py backend
        try:
            rm = pyvisa.ResourceManager('@py')
            backends.append({
                'name': 'pyvisa-py',
                'available': True
            })
            rm.close()
        except Exception as e:
            errors.append(f"PyVISA-py backend error: {e}")

        status = HealthStatus.HEALTHY if backends else HealthStatus.UNHEALTHY

        return {
            "check": "visa_backend",
            "status": status,
            "backends": backends,
            "errors": errors,
            "details": f"{len(backends)} backend(s) available"
        }

    except ImportError:
        return {
            "check": "visa_backend",
            "status": HealthStatus.UNHEALTHY,
            "error": "PyVISA not installed",
            "details": "Install with: pip install pyvisa"
        }


def check_data_directories() -> Dict[str, Any]:
    """
    Check that data storage directories exist and are writable.

    Returns:
        Dictionary with directory status
    """
    from .config import Config

    directories = Config.get_data_directories()
    status_list = []

    for name, path in directories.items():
        exists = path.exists()
        writable = path.is_dir() and exists

        # Try to write a test file if directory exists
        if writable:
            try:
                test_file = path / ".health_check_test"
                test_file.write_text("test")
                test_file.unlink()
                writable = True
            except Exception:
                writable = False

        status_list.append({
            "name": name,
            "path": str(path),
            "exists": exists,
            "writable": writable
        })

    all_healthy = all(d["exists"] and d["writable"] for d in status_list)
    status = HealthStatus.HEALTHY if all_healthy else HealthStatus.DEGRADED

    return {
        "check": "data_directories",
        "status": status,
        "directories": status_list,
        "details": f"{sum(d['writable'] for d in status_list)}/{len(status_list)} directories writable"
    }


def check_logging_configuration() -> Dict[str, Any]:
    """
    Check logging configuration.

    Returns:
        Dictionary with logging status
    """
    root_logger = logging.getLogger()

    return {
        "check": "logging",
        "status": HealthStatus.HEALTHY,
        "level": logging.getLevelName(root_logger.level),
        "handlers": len(root_logger.handlers),
        "details": f"Logging at {logging.getLevelName(root_logger.level)} level with {len(root_logger.handlers)} handler(s)"
    }


def check_system_resources() -> Dict[str, Any]:
    """
    Check system resources (memory, disk space).

    Returns:
        Dictionary with resource information
    """
    try:
        import psutil

        # Memory information
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        # Disk information
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent

        # Determine status based on resource usage
        if memory_percent > 90 or disk_percent > 90:
            status = HealthStatus.UNHEALTHY
        elif memory_percent > 75 or disk_percent > 75:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY

        return {
            "check": "system_resources",
            "status": status,
            "memory_percent": round(memory_percent, 1),
            "memory_available_gb": round(memory.available / (1024**3), 2),
            "disk_percent": round(disk_percent, 1),
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "details": f"Memory: {memory_percent:.1f}% used, Disk: {disk_percent:.1f}% used"
        }

    except ImportError:
        return {
            "check": "system_resources",
            "status": HealthStatus.UNKNOWN,
            "details": "psutil not installed (optional)"
        }


def run_all_health_checks() -> Dict[str, Any]:
    """
    Run all health checks and compile results.

    Returns:
        Dictionary with overall health status and individual check results
    """
    checks = [
        check_python_version(),
        check_required_packages(),
        check_visa_backend(),
        check_data_directories(),
        check_logging_configuration(),
        check_system_resources(),
    ]

    # Determine overall status
    statuses = [check['status'] for check in checks if 'status' in check]

    if HealthStatus.UNHEALTHY in statuses:
        overall_status = HealthStatus.UNHEALTHY
    elif HealthStatus.DEGRADED in statuses:
        overall_status = HealthStatus.DEGRADED
    elif HealthStatus.UNKNOWN in statuses and len(statuses) == statuses.count(HealthStatus.UNKNOWN):
        overall_status = HealthStatus.UNKNOWN
    else:
        overall_status = HealthStatus.HEALTHY

    return {
        "overall_status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "checks": checks,
        "summary": {
            "total_checks": len(checks),
            "healthy": statuses.count(HealthStatus.HEALTHY),
            "degraded": statuses.count(HealthStatus.DEGRADED),
            "unhealthy": statuses.count(HealthStatus.UNHEALTHY),
            "unknown": statuses.count(HealthStatus.UNKNOWN)
        }
    }


def print_health_report() -> None:
    """
    Print formatted health check report to console.
    """
    results = run_all_health_checks()

    print("\n" + "="*80)
    print("SYSTEM HEALTH CHECK REPORT")
    print("="*80)
    print(f"Timestamp: {results['timestamp']}")
    print(f"Overall Status: {results['overall_status'].upper()}")
    print("\n" + "-"*80)

    for check in results['checks']:
        status = check.get('status', 'UNKNOWN')
        # Use ASCII symbols for Windows compatibility
        status_symbol = {
            HealthStatus.HEALTHY: "[OK]  ",
            HealthStatus.DEGRADED: "[WARN]",
            HealthStatus.UNHEALTHY: "[FAIL]",
            HealthStatus.UNKNOWN: "[?]   "
        }.get(status, "[?]   ")

        print(f"\n{status_symbol} {check['check'].upper()}: {status.upper()}")
        print(f"  {check.get('details', 'No details available')}")

        # Print additional details for failed checks
        if status in [HealthStatus.UNHEALTHY, HealthStatus.DEGRADED]:
            if 'error' in check:
                print(f"  Error: {check['error']}")
            if 'errors' in check and check['errors']:
                print(f"  Errors: {', '.join(check['errors'])}")
            if 'missing' in check and check['missing']:
                print(f"  Missing: {', '.join(check['missing'])}")

    print("\n" + "="*80)
    print(f"Summary: {results['summary']['healthy']} healthy, "
          f"{results['summary']['degraded']} degraded, "
          f"{results['summary']['unhealthy']} unhealthy")
    print("="*80 + "\n")


def get_health_status_json() -> Dict[str, Any]:
    """
    Get health status in JSON-compatible format for APIs.

    Returns:
        Health status dictionary suitable for JSON serialization
    """
    return run_all_health_checks()


if __name__ == '__main__':
    # Run health check when executed directly
    print_health_report()
