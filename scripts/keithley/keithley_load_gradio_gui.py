#!/usr/bin/env python3
"""
=================================================================================
DIGANTARA Keithley 2380 ELECTRONIC LOAD CONTROL - GRADIO WEB INTERFACE
=================================================================================

PURPOSE:
    This application provides a web-based graphical user interface (GUI) for
    controlling a Keithley 2380 electronic load remotely. It allows engineers
    to configure the load, perform battery discharge tests, power supply tests,
    and analyze electrical characteristics through a web browser instead of
    manually operating the physical instrument.

KEY CAPABILITIES:
    - Connect/disconnect to electronic load via GPIB, USB, Ethernet, or Serial
    - Configure operation modes: CC (Constant Current), CV (Constant Voltage),
      CR (Constant Resistance), CP (Constant Power)
    - Set up transient operations for dynamic load testing
    - Control protection settings (OVP, OCP, OPP, OTP)
    - Perform automated measurements (voltage, current, power, resistance)
    - Capture measurement data and export to CSV files
    - Generate plots and graphs for analysis
    - Run battery discharge tests and power supply characterization
    - Configure trigger system for synchronized testing

TARGET USERS:
    Test engineers, power electronics engineers, battery test engineers, and
    automation developers who need to remotely control electronic loads for
    power supply testing, battery characterization, and DC load testing.

TECHNOLOGY STACK:
    - Python 3: Programming language
    - Gradio: Web interface framework (creates the web UI automatically)
    - Matplotlib: Plotting library for graphs
    - PyVISA: Instrument communication library (SCPI protocol)
    - Pandas: Data manipulation and CSV export

ELECTRONIC LOAD BASICS:
    An electronic load is a programmable device that acts as a controllable
    current sink. It "pulls" current from a power source (like a battery or
    power supply) to test how the source behaves under different load conditions.

    OPERATION MODES:
    - CC (Constant Current): Load draws a fixed current (e.g., 2A)
    - CV (Constant Voltage): Load maintains a fixed voltage across terminals
    - CR (Constant Resistance): Load simulates a fixed resistance (Ohm's law)
    - CP (Constant Power): Load draws constant power (P = V × I)

    COMMON APPLICATIONS:
    - Battery discharge testing (how long does a battery last at 1A draw?)
    - Power supply characterization (does voltage drop under heavy load?)
    - LED driver testing (constant current regulation)
    - DC-DC converter validation

=================================================================================
"""

# =============================================================================
# ⚙️ FILE SAVE LOCATION CONFIGURATION - EDIT THESE PATHS
# =============================================================================
# INSTRUCTIONS: Enter the FULL file paths where you want to save files.
# - Use raw strings (prefix with r) for Windows paths
# - Example: r"C:\Users\YourName\Documents\ElectronicLoad\Data"
# - Make sure the server has write permissions to these directories
# - Directories will be created automatically if they don't exist
# =============================================================================

# Measurement data files location (CSV exports)
KEITHLEY_CSV_DATA_PATH = r"C:\Users\AnirudhIyengar\Desktop\electronic_load_data"

# Graph/plot images location (PNG files)
KEITHLEY_GRAPH_PATH = r"C:\Users\AnirudhIyengar\Desktop\electronic_load_graphs"

# Log files location (measurement logging)
KEITHLEY_LOG_PATH = r"C:\Users\AnirudhIyengar\Desktop\electronic_load_logs"

# =============================================================================
# END OF CONFIGURATION - DO NOT EDIT BELOW THIS LINE UNLESS YOU KNOW WHAT YOU'RE DOING
# =============================================================================

# =============================================================================
# IMPORT STATEMENTS - External Libraries Required by This Application
# =============================================================================

# --- CORE PYTHON LIBRARIES (built into Python) ---
import sys                  # System-specific parameters (exit, path manipulation)
import logging              # Error and information logging to track application behavior
import threading            # Multi-threading support for concurrent operations
import queue                # Thread-safe queue for data exchange between threads
import time                 # Time-related functions (delays, timestamps)
from pathlib import Path    # Modern file path handling (works on Windows/Mac/Linux)
from datetime import datetime   # Date and time handling for timestamps
from typing import Optional, Dict, Any, List, Tuple, Union  # Type hints for code clarity
import signal               # Handle system signals (e.g., Ctrl+C interrupt)
import atexit               # Register cleanup functions to run on exit
import os                   # Operating system interface (file operations, environment)
import socket               # Network socket operations (check port availability)

# --- THIRD-PARTY LIBRARIES (must be installed via pip) ---
import gradio as gr         # Web UI framework - creates browser-based interfaces automatically
import pandas as pd         # Data manipulation library - handles CSV and tabular data
import matplotlib           # Plotting library for generating graphs
matplotlib.use('Agg')       # Use non-interactive backend (generates files, not windows)
import matplotlib.pyplot as plt  # Plotting interface for creating charts
import numpy as np          # Numerical computing library - handles arrays and math

# --- MATPLOTLIB CONFIGURATION ---
# These settings optimize plotting performance when handling large datasets
plt.rcParams['agg.path.chunksize'] = 10000      # Process 10,000 points at a time
plt.rcParams['path.simplify_threshold'] = 0.5   # Simplify complex paths to reduce file size

# =============================================================================
# DYNAMIC PATH CONFIGURATION - Import Custom Electronic Load Driver Module
# =============================================================================

# Calculate the project root directory (3 levels up from this script)
# This allows the script to import our custom electronic load control module
# Example: If this file is in /project/scripts/keithley/, root is /project/
#
# Path hierarchy:
#   keithley_load_gradio_gui.py (this file)
#   └── parent (scripts/keithley/)
#       └── parent (scripts/)
#           └── parent (Digantara_instrumentation/) ← This is what we need
script_dir = Path(__file__).resolve().parent.parent.parent

# Add the project root to Python's module search path if not already present
# This enables: "from instrument_control.keithley_load import ..."
# Using insert(0, ...) ensures our module takes priority over system modules
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

# Import our custom electronic load driver classes
# Keithley2380: Main class for controlling the electronic load
# Keithley2380Error: Custom exception class for error handling
try:
    from instrument_control.keithley_load import Keithley2380, Keithley2380Error
except ImportError as e:
    # If import fails, the driver module is missing or incorrectly installed
    print(f"Error importing electronic load module: {e}")
    print(f"\nScript directory: {script_dir}")
    print(f"sys.path: {sys.path[:3]}...")
    import traceback
    traceback.print_exc()
    sys.exit(1)  # Exit with error code 1

# Import auto-detection utilities for automatic VISA instrument discovery
try:
    from instrument_control.scpi_wrapper import (
        scan_and_identify_instruments,
        list_available_instruments
    )
except ImportError as e:
    print(f"Warning: Auto-detection utilities not available: {e}")
    # Continue anyway - manual entry will still work
    scan_and_identify_instruments = None
    list_available_instruments = None

# =============================================================================
# UTILITY FUNCTIONS AND HELPERS
# =============================================================================
# These helper functions provide common operations used throughout the
# application, such as unit conversions and data formatting for display.

# -----------------------------------------------------------------------------
# HELPER FUNCTION: Format Values with SI Prefixes
# -----------------------------------------------------------------------------
def format_si_value(value: float, kind: str) -> str:
    """
    Format numeric values with appropriate SI (International System) unit prefixes.

    WHAT IT DOES:
        Converts raw numeric values into human-readable strings with appropriate
        units and prefixes. For example, instead of displaying "0.001 A",
        it shows "1.000 mA" which is much easier to read.

    SI PREFIXES USED:
        - M (Mega) = 1,000,000 (million)
        - k (kilo) = 1,000 (thousand)
        - m (milli) = 0.001 (thousandth)
        - µ (micro) = 0.000001 (millionth)

    SUPPORTED TYPES:
        - "current": Current values (A, mA, µA)
        - "voltage": Voltage values (kV, V, mV, µV)
        - "power": Power values (kW, W, mW, µW)
        - "resistance": Resistance values (MΩ, kΩ, Ω, mΩ)
        - "time": Time values (h, min, s, ms, µs)
        - "capacity": Capacity values (Ah, mAh)

    EXAMPLE CONVERSIONS:
        format_si_value(0.025, "current") → "25.000 mA"
        format_si_value(1500, "voltage") → "1.500 kV"
        format_si_value(0.5, "power") → "500.000 mW"
        format_si_value(10000, "resistance") → "10.000 kΩ"
        format_si_value(0.001, "time") → "1.000 ms"
        format_si_value(2.5, "capacity") → "2.500 Ah"

    PARAMETERS:
        value: The numeric value to format
        kind: The type of measurement (current, voltage, power, resistance, time, capacity)

    RETURNS:
        Formatted string with value and appropriate unit (e.g., "25.000 mA")
    """
    v = abs(value)  # Use absolute value for magnitude comparison (ignore negative sign)

    # CURRENT FORMATTING (A, mA, µA)
    if kind == "current":
        if v >= 1:  # 1 amp or more → A
            return f"{value:.3f} A"
        if v >= 1e-3:  # 1 milliamp or more → mA
            return f"{value*1e3:.3f} mA"
        return f"{value*1e6:.3f} µA"  # Less than 1 mA → µA

    # VOLTAGE FORMATTING (kV, V, mV, µV)
    if kind == "voltage":
        if v >= 1e3:  # 1000 volts or more → kV
            return f"{value/1e3:.3f} kV"
        if v >= 1:  # 1 volt or more → V
            return f"{value:.3f} V"
        if v >= 1e-3:  # 1 millivolt or more → mV
            return f"{value*1e3:.3f} mV"
        return f"{value*1e6:.3f} µV"  # Less than 1 mV → µV

    # POWER FORMATTING (kW, W, mW, µW)
    if kind == "power":
        if v >= 1e3:  # 1000 watts or more → kW
            return f"{value/1e3:.3f} kW"
        if v >= 1:  # 1 watt or more → W
            return f"{value:.3f} W"
        if v >= 1e-3:  # 1 milliwatt or more → mW
            return f"{value*1e3:.3f} mW"
        return f"{value*1e6:.3f} µW"  # Less than 1 mW → µW

    # RESISTANCE FORMATTING (MΩ, kΩ, Ω, mΩ)
    if kind == "resistance":
        if v >= 1e6:  # 1 million ohms or more → MΩ
            return f"{value/1e6:.3f} MΩ"
        if v >= 1e3:  # 1000 ohms or more → kΩ
            return f"{value/1e3:.3f} kΩ"
        if v >= 1:  # 1 ohm or more → Ω
            return f"{value:.3f} Ω"
        return f"{value*1e3:.3f} mΩ"  # Less than 1 Ω → mΩ

    # TIME FORMATTING (h, min, s, ms, µs)
    if kind == "time":
        if v >= 3600:  # 3600 seconds or more → hours
            return f"{value/3600:.2f} h"
        if v >= 60:  # 60 seconds or more → minutes
            return f"{value/60:.2f} min"
        if v >= 1:  # 1 second or more → s
            return f"{value:.3f} s"
        if v >= 1e-3:  # 1 millisecond or more → ms
            return f"{value*1e3:.3f} ms"
        return f"{value*1e6:.3f} µs"  # Less than 1 ms → µs

    # CAPACITY FORMATTING (Ah, mAh)
    # Used for battery capacity measurements
    if kind == "capacity":
        if v >= 1:  # 1 Amp-hour or more → Ah
            return f"{value:.3f} Ah"
        return f"{value*1e3:.3f} mAh"  # Less than 1 Ah → mAh

    # DEFAULT: Return raw number if type not recognized
    return f"{value:.3f}"

# =============================================================================
# DATA LOGGING CLASS
# =============================================================================
# This class handles all data capture, export, and visualization operations
# for the electronic load. It provides thread-safe methods to log measurements,
# save data to CSV files, and generate plots.

class ElectronicLoadDataLogger:
    """
    =========================================================================
    DATA LOGGING HANDLER FOR DIGANTARA Keithley 2380 ELECTRONIC LOAD
    =========================================================================

    PURPOSE:
        This class is responsible for capturing measurement data from the
        electronic load, processing it, and exporting it in various formats
        (CSV files, plots).

    KEY RESPONSIBILITIES:
        1. Continuous measurement logging (time-series data capture)
        2. Save measurement data to CSV files with metadata
        3. Generate professional plots/graphs of measurement data
        4. Handle thread-safe operations (multiple operations can't interfere)

    THREAD SAFETY:
        This class uses locks (io_lock) to ensure that multiple operations
        don't try to communicate with the electronic load at the same time,
        which could cause errors or data corruption.

    DATA FLOW:
        1. start_measurement_logging() → Begins continuous logging in background
        2. _logging_worker() → Worker thread that collects measurements
        3. _save_logged_data() → Exports time-series data to CSV file
        4. export_single_measurement() → Exports single reading to CSV
        5. generate_measurement_plot() → Creates PNG image of measurements
    """

    def __init__(self, load_instance, io_lock: Optional[threading.RLock] = None):
        """
        Initialize the data logging handler.

        PARAMETERS:
            load_instance: Reference to the Keithley2380 object that controls
                          the physical electronic load
            io_lock: Optional threading lock to prevent simultaneous
                    communication with the load (prevents conflicts)

        SETS UP:
            - Connection to electronic load
            - Logger for tracking operations and errors
            - Default directories for saving data, graphs, and logs
            - Thread synchronization components
            - Logging state tracking variables
        """
        # Store reference to the electronic load controller
        self.load = load_instance

        # Create a logger for this class to track operations and errors
        # Logger name will be "ElectronicLoadDataLogger"
        self._logger = logging.getLogger(f'{self.__class__.__name__}')

        # Set up default directories for saving files
        # Path.cwd() gets the current working directory
        # The "/" operator creates subdirectories
        self.default_data_dir = Path.cwd() / "data"            # For CSV files
        self.default_graph_dir = Path.cwd() / "graphs"         # For plot images
        self.default_log_dir = Path.cwd() / "logs"             # For log files

        # Store the threading lock for thread-safe operations
        # RLock = "Reentrant Lock" - allows same thread to acquire lock multiple times
        self.io_lock = io_lock

        # Thread management variables
        self._logging_active = False        # Flag: Is logging currently running?
        self._logging_thread = None         # Reference to logging thread object
        self._stop_logging = threading.Event()  # Event to signal thread to stop

    def start_measurement_logging(self, interval_seconds: float = 1.0, duration_seconds: Optional[float] = None) -> bool:
        """
        Start continuous measurement logging in a background thread.

        WHAT IT DOES:
            Starts a background thread that continuously reads measurements
            from the electronic load at regular intervals. This is useful for
            long-duration tests like battery discharge testing.

        HOW IT WORKS:
            1. Check if logging is already running (can't start twice)
            2. Create a new background thread (daemon thread)
            3. The thread runs _logging_worker() which collects measurements
            4. Measurements are stored in memory and saved to file when stopped

        USE CASE EXAMPLE:
            Battery discharge test: Log voltage, current, power every 1 second
            for 2 hours (7200 seconds) to see how battery voltage drops over time.

        PARAMETERS:
            interval_seconds: Time between measurements (e.g., 1.0 = 1 second)
            duration_seconds: Total logging duration (None = run until manually stopped)

        RETURNS:
            True if logging started successfully, False if already running or error
        """
        # Check if logging is already active
        if self._logging_active:
            self._logger.warning("Logging already active")
            return False  # Can't start logging twice

        try:
            # Clear the stop event (in case it was set from previous run)
            self._stop_logging.clear()

            # Create a new background thread for measurement collection
            # daemon=True means thread will automatically stop when program exits
            self._logging_thread = threading.Thread(
                target=self._logging_worker,           # Function to run in thread
                args=(interval_seconds, duration_seconds),  # Arguments to pass
                daemon=True  # Daemon thread (stops with program)
            )

            # Mark logging as active and start the thread
            self._logging_active = True
            self._logging_thread.start()

            self._logger.info(f"Started measurement logging: interval={interval_seconds}s")
            return True  # Success
        except Exception as e:
            self._logger.error(f"Failed to start logging: {e}")
            return False  # Failed to start

    def stop_measurement_logging(self) -> bool:
        """
        Stop continuous measurement logging and save collected data.

        WHAT IT DOES:
            Signals the background logging thread to stop, waits for it to
            finish, and saves all collected measurements to a CSV file.

        HOW IT WORKS:
            1. Set the stop event to signal the thread to exit its loop
            2. Wait up to 5 seconds for the thread to finish cleanly
            3. The thread automatically saves all measurements before exiting
            4. Mark logging as inactive

        RETURNS:
            True if stopped successfully, False if error occurred
        """
        # Check if logging is running
        if not self._logging_active:
            return True  # Already stopped, nothing to do

        try:
            # Signal the logging thread to stop
            self._stop_logging.set()

            # Wait for the thread to finish (timeout after 5 seconds)
            if self._logging_thread and self._logging_thread.is_alive():
                self._logging_thread.join(timeout=5.0)  # Wait max 5 seconds

            # Mark logging as inactive
            self._logging_active = False
            self._logger.info("Measurement logging stopped")
            return True  # Success
        except Exception as e:
            self._logger.error(f"Error stopping logging: {e}")
            return False  # Error occurred

    def _logging_worker(self, interval: float, duration: Optional[float]):
        """
        Background worker thread that continuously collects measurements.

        WHAT IT DOES:
            This method runs in a separate thread and repeatedly calls
            measure_all() on the electronic load to collect time-series data.

        HOW IT WORKS:
            1. Loop continuously until stop signal received or duration expires
            2. Each iteration: read measurements from load, add timestamp, store
            3. Sleep for 'interval' seconds between measurements
            4. When stopped: save all collected measurements to CSV file

        THREAD SAFETY:
            Uses io_lock to prevent conflicts with other operations that
            might be communicating with the load simultaneously.

        DATA COLLECTED:
            Each measurement includes: voltage, current, power, timestamp

        PARAMETERS:
            interval: Seconds between measurements (e.g., 1.0 = 1 Hz sampling)
            duration: Optional time limit in seconds (None = run indefinitely)
        """
        # Record when logging started (for duration check)
        start_time = time.time()

        # List to store all measurements
        measurements = []

        # Loop until stop signal received
        while not self._stop_logging.is_set():
            try:
                # Check if duration limit has been reached
                if duration and (time.time() - start_time) > duration:
                    break  # Time limit reached, exit loop

                # THREAD-SAFE MEASUREMENT ACQUISITION
                # If a lock is provided, acquire it before communicating
                if self.io_lock:
                    with self.io_lock:  # Automatically acquires and releases lock
                        data = self.load.measure_all()  # Get all measurements
                else:
                    # No lock needed (single-threaded operation)
                    data = self.load.measure_all()

                # If measurement was successful, add timestamp and store it
                if data:
                    timestamp = datetime.now()
                    data['timestamp'] = timestamp.isoformat()  # ISO format: 2025-01-06T10:30:45
                    measurements.append(data)  # Add to collection

                # Sleep until next measurement interval
                time.sleep(interval)

            except Exception as e:
                # Log errors but continue logging (don't stop on single failure)
                self._logger.error(f"Error in logging worker: {e}")

        # When loop exits (logging stopped), save all measurements to file
        if measurements:
            self._save_logged_data(measurements)

    def _save_logged_data(self, measurements: List[Dict]) -> Optional[str]:
        """Save logged measurement data to CSV file"""
        try:
            save_dir = Path(KEITHLEY_CSV_DATA_PATH)
            save_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"load_measurements_{timestamp}.csv"
            filepath = save_dir / filename

            df = pd.DataFrame(measurements)
            df.to_csv(filepath, index=False)

            self._logger.info(f"Logged data saved: {filepath}")
            return str(filepath)
        except Exception as e:
            self._logger.error(f"Failed to save logged data: {e}")
            return None

    def export_single_measurement(self, measurements: Dict[str, Any], custom_path: Optional[str] = None) -> Optional[str]:
        """Export single measurement to CSV"""
        if not measurements:
            return None

        try:
            save_dir = Path(custom_path) if custom_path else Path(KEITHLEY_CSV_DATA_PATH)
            save_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"load_measurement_{timestamp}.csv"
            filepath = save_dir / filename

            # Add timestamp
            measurements['timestamp'] = datetime.now().isoformat()

            # Create DataFrame with single row
            df = pd.DataFrame([measurements])
            
            # Write with header information
            with open(filepath, 'w') as f:
                f.write("# Keithley 2380 Electronic Load Measurement\n")
                f.write(f"# Timestamp: {measurements['timestamp']}\n")
                f.write("# All values are instantaneous measurements\n\n")
                df.to_csv(filepath, mode='a', index=False)

            self._logger.info(f"Measurement exported: {filepath}")
            return str(filepath)
        except Exception as e:
            self._logger.error(f"Export failed: {e}")
            return None

    def generate_measurement_plot(self, measurements: Dict[str, Any], custom_path: Optional[str] = None) -> Optional[str]:
        """Generate measurement visualization"""
        if not measurements:
            return None

        try:
            save_dir = Path(custom_path) if custom_path else Path(KEITHLEY_GRAPH_PATH)
            save_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"load_measurement_plot_{timestamp}.png"
            filepath = save_dir / filename

            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 8))

            # Voltage bar
            voltage = measurements.get('voltage', 0)
            ax1.bar(['Voltage'], [voltage], color='blue', alpha=0.7)
            ax1.set_ylabel('Voltage (V)')
            ax1.set_title(f'Voltage: {format_si_value(voltage, "voltage")}')
            ax1.grid(True, alpha=0.3)

            # Current bar
            current = measurements.get('current', 0)
            ax2.bar(['Current'], [current], color='red', alpha=0.7)
            ax2.set_ylabel('Current (A)')
            ax2.set_title(f'Current: {format_si_value(current, "current")}')
            ax2.grid(True, alpha=0.3)

            # Power bar
            power = measurements.get('power', 0)
            ax3.bar(['Power'], [power], color='green', alpha=0.7)
            ax3.set_ylabel('Power (W)')
            ax3.set_title(f'Power: {format_si_value(power, "power")}')
            ax3.grid(True, alpha=0.3)

            # Resistance calculation if available
            if voltage and current and current > 0:
                resistance = voltage / current
                ax4.bar(['Resistance'], [resistance], color='orange', alpha=0.7)
                ax4.set_ylabel('Resistance (Ω)')
                ax4.set_title(f'Resistance: {format_si_value(resistance, "resistance")}')
            else:
                ax4.text(0.5, 0.5, 'Resistance\nN/A', ha='center', va='center', 
                        transform=ax4.transAxes, fontsize=14)
                ax4.set_title('Resistance: N/A')
            ax4.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.suptitle('Electronic Load Measurements', fontsize=16, y=1.02)
            plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
            plt.close(fig)

            self._logger.info(f"Plot generated: {filepath}")
            return str(filepath)
        except Exception as e:
            self._logger.error(f"Plot generation failed: {e}")
            return None

# ============================================================================
# MAIN GRADIO GUI CLASS
# ============================================================================

class GradioElectronicLoadGUI:
    """
    Professional electronic load control interface with comprehensive feature set.
    Implements connection management, all operation modes, transient control,
    measurements, protection settings, and complete data acquisition workflow.
    """

    def __init__(self):
        self.electronic_load = None
        self.data_logger = None
        self.last_measurements = None
        self.io_lock = threading.RLock()
        self._shutdown_flag = threading.Event()
        self._gradio_interface = None

        # Use the configured paths from the top of the file
        self.save_locations = {
            'data': KEITHLEY_CSV_DATA_PATH,
            'graphs': KEITHLEY_GRAPH_PATH,
            'logs': KEITHLEY_LOG_PATH
        }

        self.setup_logging()
        self.setup_cleanup_handlers()

        # Operation modes and settings
        self.operation_modes = ["CURRent", "VOLTage", "RESistance", "POWer"]
        self.transient_modes = ["CONTinuous", "PULSe", "TOGGle"]
        self.trigger_sources = ["BUS", "EXTernal", "HOLD", "MANUal", "TIMer"]

    def setup_logging(self):
        """Configure logging for system diagnostics"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('GradioElectronicLoadAutomation')

    def setup_cleanup_handlers(self):
        """Register cleanup procedures for graceful shutdown"""
        atexit.register(self.cleanup)
        signal.signal(signal.SIGINT, self._signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle system signals for clean shutdown"""
        print(f"\nReceived signal {signum}, shutting down...")
        self.cleanup()
        sys.exit(0)

    def cleanup(self):
        """Cleanup resources and disconnect electronic load"""
        try:
            self._shutdown_flag.set()
            
            if self.data_logger:
                self.data_logger.stop_measurement_logging()
            
            if self.electronic_load and hasattr(self.electronic_load, 'is_connected'):
                if self.electronic_load.is_connected:
                    print("Safely shutting down electronic load...")
                    self.electronic_load.safe_shutdown()
                    self.electronic_load.disconnect()
            
            self.electronic_load = None
            self.data_logger = None
            plt.close('all')
            print("Cleanup completed.")
        except Exception as e:
            print(f"Cleanup error: {e}")

    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================

    def connect_electronic_load(self, visa_address: str):
        """Establish VISA connection and query instrument identification"""
        try:
            if not visa_address:
                return "Error: VISA address is empty", "Disconnected"

            self.electronic_load = Keithley2380(visa_address)

            if self.electronic_load.connect():
                self.data_logger = ElectronicLoadDataLogger(self.electronic_load, io_lock=self.io_lock)
                
                info = self.electronic_load.get_instrument_info()
                if info:
                    info_text = f"Connected: {info['manufacturer']} {info['model']} | S/N: {info['serial_number']} | FW: {info['firmware_version']}"
                    info_text += f"\nSpecs: {info['max_current_a']}A, {info['max_voltage_v']}V, {info['max_power_w']}W"
                    return info_text, "Connected"
                else:
                    return "Connected (no info available)", "Connected"
            else:
                return "Connection failed", "Disconnected"
        except Exception as e:
            return f"Error: {str(e)}", "Disconnected"

    def disconnect_electronic_load(self):
        """Close connection to electronic load"""
        try:
            if self.data_logger:
                self.data_logger.stop_measurement_logging()
            
            if self.electronic_load:
                self.electronic_load.safe_shutdown()
                self.electronic_load.disconnect()
            
            self.electronic_load = None
            self.data_logger = None
            self.last_measurements = None
            self.logger.info("Disconnected successfully")
            return "Disconnected successfully", "Disconnected"
        except Exception as e:
            self.logger.error(f"Disconnect error: {e}")
            return f"Disconnect error: {str(e)}", "Disconnected"

    def test_connection(self):
        """Verify electronic load connectivity"""
        if self.electronic_load and self.electronic_load.is_connected:
            return "✓ Connection test: PASSED"
        else:
            return "✗ Connection test: FAILED - Not connected"

    # ========================================================================
    # BASIC OPERATION CONTROL
    # ========================================================================

    def set_operation_mode(self, mode):
        """Set electronic load operation mode"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                success = self.electronic_load.set_function(mode)
            
            if success:
                return f"Operation mode set to: {mode}"
            else:
                return "Failed to set operation mode"
        except Exception as e:
            return f"Error: {str(e)}"

    def enable_disable_input(self, enable):
        """Enable or disable electronic load input"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                if enable:
                    success = self.electronic_load.enable_input()
                else:
                    success = self.electronic_load.disable_input()

            status = "enabled" if enable else "disabled"
            if success:
                return f"Input {status}"
            else:
                return f"Failed to {status} input"
        except Exception as e:
            return f"Error: {str(e)}"

    def disable_transient_quick(self):
        """Quick disable of transient mode"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "❌ Error: Not connected to electronic load"

        try:
            with self.io_lock:
                success = self.electronic_load.enable_transient(False)

            if success:
                return "✓ Transient mode disabled - You can now change operation modes"
            else:
                return "❌ Failed to disable transient mode"
        except Exception as e:
            return f"❌ Error: {str(e)}"

    def quick_setup_cc(self, current_value, enable_input):
        """Quick setup for constant current mode"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                success = self.electronic_load.quick_cc_setup(current_value, enable_input)
            
            if success:
                status = "enabled" if enable_input else "configured"
                return f"CC mode setup complete: {current_value}A, input {status}"
            else:
                return "CC setup failed"
        except Exception as e:
            return f"Error: {str(e)}"

    def quick_setup_cv(self, voltage_value, enable_input):
        """Quick setup for constant voltage mode"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                success = self.electronic_load.quick_cv_setup(voltage_value, enable_input)
            
            if success:
                status = "enabled" if enable_input else "configured"
                return f"CV mode setup complete: {voltage_value}V, input {status}"
            else:
                return "CV setup failed"
        except Exception as e:
            return f"Error: {str(e)}"

    def quick_setup_cr(self, resistance_value, enable_input):
        """Quick setup for constant resistance mode"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                success = self.electronic_load.quick_cr_setup(resistance_value, enable_input)
            
            if success:
                status = "enabled" if enable_input else "configured"
                return f"CR mode setup complete: {resistance_value}Ω, input {status}"
            else:
                return "CR setup failed"
        except Exception as e:
            return f"Error: {str(e)}"

    def quick_setup_cp(self, power_value, enable_input):
        """Quick setup for constant power mode"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                success = self.electronic_load.quick_cp_setup(power_value, enable_input)
            
            if success:
                status = "enabled" if enable_input else "configured"
                return f"CP mode setup complete: {power_value}W, input {status}"
            else:
                return "CP setup failed"
        except Exception as e:
            return f"Error: {str(e)}"

    # ========================================================================
    # DETAILED CONFIGURATION
    # ========================================================================

    def configure_current_settings(self, level, slew_rate, protection_enable, protection_level):
        """Configure detailed current mode settings"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "❌ Error: Not connected to electronic load"

        try:
            results = []

            with self.io_lock:
                # Disable input first for safety (prevent unexpected changes on live load)
                self.electronic_load.disable_input()
                results.append("✓ Input disabled (for safe configuration)")

                # Disable transient mode to avoid conflicts
                self.electronic_load.enable_transient(False)

                # Set operation mode to current
                if self.electronic_load.set_function("CURRent"):
                    results.append("✓ Mode set to: Current")

                # Set slew rate FIRST (before setting current level)
                # This determines how fast current will ramp when level changes
                if slew_rate and slew_rate > 0:
                    # Enable slow mode (A/ms) for slew rate
                    if self.electronic_load.set_current_slow_rate_mode(True):
                        results.append("✓ Slew rate mode: slow (A/ms)")

                    if self.electronic_load.set_current_slew_rate(slew_rate):
                        results.append(f"✓ Slew rate: {slew_rate} A/ms")
                        results.append("  (Current will ramp at this rate when input is enabled)")

                # Set current level (will ramp at slew rate if set)
                if self.electronic_load.set_current_level(level):
                    if slew_rate and slew_rate > 0:
                        ramp_time = level / slew_rate  # Calculate ramp time in ms
                        results.append(f"✓ Current level: {level}A (will ramp in ~{ramp_time:.1f}ms)")
                    else:
                        results.append(f"✓ Current level: {level}A (instant change)")

                # Configure protection
                if self.electronic_load.set_current_protection(protection_enable, protection_level):
                    prot_status = f"enabled at {protection_level}A" if protection_enable else "disabled"
                    results.append(f"✓ Protection: {prot_status}")

            return "\n".join(results) if results else "❌ Configuration failed"
        except Exception as e:
            self.logger.error(f"Current configuration error: {e}")
            return f"❌ Error: {str(e)}"

    def configure_voltage_settings(self, level, von_level, auto_range):
        """Configure detailed voltage mode settings"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "❌ Error: Not connected to electronic load"

        try:
            results = []

            with self.io_lock:
                # Disable input first for safety
                self.electronic_load.disable_input()
                results.append("✓ Input disabled (for safe configuration)")

                # Disable transient mode to avoid conflicts
                self.electronic_load.enable_transient(False)

                # Set operation mode to voltage
                if self.electronic_load.set_function("VOLTage"):
                    results.append("✓ Mode set to: Voltage")

                # Set voltage range first (before setting level for best results)
                if self.electronic_load.set_voltage_range(level, auto_range):
                    range_status = "auto" if auto_range else "manual"
                    results.append(f"✓ Range: {range_status}")

                # Set voltage level
                if self.electronic_load.set_voltage_level(level):
                    results.append(f"✓ Voltage level: {level}V")

                # Set Von level if specified
                if von_level and von_level > 0:
                    if self.electronic_load.set_voltage_on_level(von_level):
                        results.append(f"✓ Von level: {von_level}V (turn-on threshold)")

            return "\n".join(results) if results else "❌ Configuration failed"
        except Exception as e:
            self.logger.error(f"Voltage configuration error: {e}")
            return f"❌ Error: {str(e)}"

    def configure_resistance_settings(self, level, resistance_range):
        """Configure detailed resistance mode settings"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "❌ Error: Not connected to electronic load"

        try:
            results = []

            with self.io_lock:
                # Disable input first for safety
                self.electronic_load.disable_input()
                results.append("✓ Input disabled (for safe configuration)")

                # Disable transient mode to avoid conflicts
                self.electronic_load.enable_transient(False)

                # Set operation mode to resistance
                if self.electronic_load.set_function("RESistance"):
                    results.append("✓ Mode set to: Resistance")

                # Set resistance range first if specified
                if resistance_range and resistance_range > 0:
                    if self.electronic_load.set_resistance_range(resistance_range):
                        results.append(f"✓ Range: {resistance_range}Ω")

                # Set resistance level
                if self.electronic_load.set_resistance_level(level):
                    results.append(f"✓ Resistance level: {level}Ω")

            return "\n".join(results) if results else "❌ Configuration failed"
        except Exception as e:
            self.logger.error(f"Resistance configuration error: {e}")
            return f"❌ Error: {str(e)}"

    def configure_power_settings(self, level, power_range, protection_level):
        """Configure detailed power mode settings"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "❌ Error: Not connected to electronic load"

        try:
            results = []

            with self.io_lock:
                # Disable input first for safety
                self.electronic_load.disable_input()
                results.append("✓ Input disabled (for safe configuration)")

                # Disable transient mode to avoid conflicts
                self.electronic_load.enable_transient(False)

                # Set operation mode to power
                if self.electronic_load.set_function("POWer"):
                    results.append("✓ Mode set to: Power")

                # Set power range first if specified
                if power_range and power_range > 0:
                    if self.electronic_load.set_power_range(power_range):
                        results.append(f"✓ Range: {power_range}W")

                # Set power level
                if self.electronic_load.set_power_level(level):
                    results.append(f"✓ Power level: {level}W")

                # Set power protection if specified
                if protection_level and protection_level > 0:
                    if self.electronic_load.set_power_protection(protection_level):
                        results.append(f"✓ Protection: {protection_level}W")

            return "\n".join(results) if results else "❌ Configuration failed"
        except Exception as e:
            self.logger.error(f"Power configuration error: {e}")
            return f"❌ Error: {str(e)}"

    # ========================================================================
    # TRANSIENT OPERATIONS
    # ========================================================================

    def configure_transient(self, enable, mode, operation_type, a_level, b_level, a_width, b_width):
        """Configure transient operation"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "Error: Not connected"

        try:
            results = []
            
            with self.io_lock:
                # Enable/disable transient
                if self.electronic_load.enable_transient(enable):
                    status = "enabled" if enable else "disabled"
                    results.append(f"Transient: {status}")
                
                if enable:
                    # Configure specific transient type
                    success = False
                    if operation_type == "Current":
                        success = self.electronic_load.set_current_transient(mode, a_level, b_level, a_width, b_width)
                    elif operation_type == "Voltage":
                        success = self.electronic_load.set_voltage_transient(mode, a_level, b_level, a_width, b_width)
                    elif operation_type == "Resistance":
                        success = self.electronic_load.set_resistance_transient(mode, a_level, b_level, a_width, b_width)
                    elif operation_type == "Power":
                        success = self.electronic_load.set_power_transient(mode, a_level, b_level, a_width, b_width)
                    
                    if success:
                        results.append(f"{operation_type} transient: {mode}, A={a_level}, B={b_level}")
            
            return "\n".join(results) if results else "Transient configuration failed"
        except Exception as e:
            return f"Error: {str(e)}"

    # ========================================================================
    # MEASUREMENTS
    # ========================================================================

    def perform_single_measurement(self):
        """Perform single comprehensive measurement"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                measurements = self.electronic_load.measure_all()
            
            if measurements:
                self.last_measurements = measurements
                result_lines = []
                
                for key, value in measurements.items():
                    if key == "voltage":
                        result_lines.append(f"Voltage: {format_si_value(value, 'voltage')}")
                    elif key == "current":
                        result_lines.append(f"Current: {format_si_value(value, 'current')}")
                    elif key == "power":
                        result_lines.append(f"Power: {format_si_value(value, 'power')}")
                    elif key == "resistance":
                        result_lines.append(f"Resistance: {format_si_value(value, 'resistance')}")
                    elif key == "capability":
                        result_lines.append(f"Capability: {format_si_value(value, 'capacity')}")
                    elif key == "time":
                        result_lines.append(f"Time: {format_si_value(value, 'time')}")
                
                return "\n".join(result_lines)
            else:
                return "Measurement failed"
        except Exception as e:
            return f"Error: {str(e)}"

    def start_continuous_logging(self, interval, duration):
        """Start continuous measurement logging"""
        if not self.data_logger:
            return "Error: Data logger not initialized"

        try:
            duration_val = duration if duration > 0 else None
            success = self.data_logger.start_measurement_logging(interval, duration_val)
            
            if success:
                duration_str = f"{duration}s" if duration_val else "indefinite"
                return f"Continuous logging started: interval={interval}s, duration={duration_str}"
            else:
                return "Failed to start logging"
        except Exception as e:
            return f"Error: {str(e)}"

    def stop_continuous_logging(self):
        """Stop continuous measurement logging"""
        if not self.data_logger:
            return "Error: Data logger not initialized"

        try:
            success = self.data_logger.stop_measurement_logging()
            if success:
                return "Continuous logging stopped"
            else:
                return "Failed to stop logging"
        except Exception as e:
            return f"Error: {str(e)}"

    # ========================================================================
    # TRIGGER SYSTEM
    # ========================================================================

    def configure_trigger(self, source, timer_period):
        """Configure trigger system"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "Error: Not connected"

        try:
            results = []
            
            with self.io_lock:
                # Set trigger source
                if self.electronic_load.set_trigger_source(source):
                    results.append(f"Trigger source: {source}")
                
                # Set timer period if TIMer source selected
                if source == "TIMer" and timer_period > 0:
                    if self.electronic_load.set_trigger_timer(timer_period):
                        results.append(f"Timer period: {timer_period}s")
            
            return "\n".join(results) if results else "Trigger configuration failed"
        except Exception as e:
            return f"Error: {str(e)}"

    def force_trigger(self):
        """Force a trigger event"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                success = self.electronic_load.force_trigger()
            
            if success:
                return "Trigger forced successfully"
            else:
                return "Failed to force trigger"
        except Exception as e:
            return f"Error: {str(e)}"

    # ========================================================================
    # MEMORY OPERATIONS
    # ========================================================================

    def save_setup(self, location):
        """Save current setup to memory"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                success = self.electronic_load.save_setup(location)
            
            if success:
                return f"Setup saved to location: {location}"
            else:
                return "Failed to save setup"
        except Exception as e:
            return f"Error: {str(e)}"

    def recall_setup(self, location):
        """Recall setup from memory"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                success = self.electronic_load.recall_setup(location)
            
            if success:
                return f"Setup recalled from location: {location}"
            else:
                return "Failed to recall setup"
        except Exception as e:
            return f"Error: {str(e)}"

    # ========================================================================
    # SYSTEM FUNCTIONS
    # ========================================================================

    def reset_instrument(self):
        """Reset instrument to default state"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                success = self.electronic_load.reset()
            
            if success:
                return "Instrument reset to default state"
            else:
                return "Reset failed"
        except Exception as e:
            return f"Error: {str(e)}"

    def run_self_test(self):
        """Execute instrument self-test"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                result = self.electronic_load.self_test()
            
            if result is not None:
                status = "PASSED" if result == 0 else "FAILED"
                return f"Self-test result: {status} (code: {result})"
            else:
                return "Self-test failed to execute"
        except Exception as e:
            return f"Error: {str(e)}"

    def get_status_summary(self):
        """Get comprehensive instrument status"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                status = self.electronic_load.get_status_summary()
            
            if status:
                lines = []
                
                # Instrument info
                if 'instrument' in status:
                    info = status['instrument']
                    lines.append(f"Instrument: {info.get('model', 'Unknown')}")
                    lines.append(f"Serial: {info.get('serial_number', 'Unknown')}")
                    lines.append(f"Firmware: {info.get('firmware_version', 'Unknown')}")
                
                # Operation status
                lines.append(f"Input: {'ON' if status.get('input_enabled', False) else 'OFF'}")
                lines.append(f"Mode: {status.get('operation_mode', 'Unknown')}")
                
                # Current settings
                for setting in ['current_level', 'voltage_level', 'resistance_level', 'power_level']:
                    if setting in status:
                        value = status[setting]
                        unit = setting.split('_')[0]
                        lines.append(f"{unit.title()}: {format_si_value(value, unit)}")
                
                # Measurements
                if 'measurements' in status:
                    lines.append("\nMeasurements:")
                    for key, value in status['measurements'].items():
                        lines.append(f"  {key.title()}: {format_si_value(value, key)}")
                
                # Errors
                if 'errors' in status:
                    lines.append(f"\nErrors: {len(status['errors'])} found")
                    for error in status['errors'][:3]:  # Show first 3 errors
                        lines.append(f"  {error}")
                
                return "\n".join(lines)
            else:
                return "Status query failed"
        except Exception as e:
            return f"Error: {str(e)}"

    def clear_protection(self):
        """Clear protection latches"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                success = self.electronic_load.clear_protection()
            
            if success:
                return "Protection latches cleared"
            else:
                return "Failed to clear protection"
        except Exception as e:
            return f"Error: {str(e)}"

    # ========================================================================
    # FILE OPERATIONS
    # ========================================================================

    def export_measurements(self):
        """Export last measurements to CSV"""
        if not self.last_measurements:
            return "Error: No measurements available", None

        if not self.data_logger:
            return "Error: Data logger not initialized", None

        try:
            filepath = self.data_logger.export_single_measurement(self.last_measurements)
            if filepath:
                return f"Measurements exported to: {Path(filepath).name}", filepath
            else:
                return "Export failed", None
        except Exception as e:
            return f"Error: {str(e)}", None

    def generate_plot(self):
        """Generate measurement plot"""
        if not self.last_measurements:
            return "Error: No measurements available"

        if not self.data_logger:
            return "Error: Data logger not initialized"

        try:
            filepath = self.data_logger.generate_measurement_plot(self.last_measurements)
            if filepath:
                return f"Plot generated: {Path(filepath).name}"
            else:
                return "Plot generation failed"
        except Exception as e:
            return f"Error: {str(e)}"

    def safe_shutdown(self):
        """Execute safe shutdown sequence"""
        if not self.electronic_load or not self.electronic_load.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                success = self.electronic_load.safe_shutdown()
            
            if success:
                return "Safe shutdown completed"
            else:
                return "Shutdown sequence failed"
        except Exception as e:
            return f"Error: {str(e)}"

    # ========================================================================
    # GRADIO INTERFACE CREATION
    # ========================================================================

    def create_interface(self):
        """Build comprehensive Gradio web interface with full-page layout"""
        css = """
        .gradio-container {
        max-width: 100% !important;
        padding: 20px !important;
        margin: 0 !important;
        min-height: 100vh;
        }
        .container {
        max-width: 100% !important;
        padding: 0 10px !important;
        margin: 0 !important;
        }
        #component-0 {
        min-height: 100vh;
        }
        .tab {
        padding: 0 10px;
        min-height: calc(100vh - 120px);
        }
        .panel {
        margin: 5px 0;
        }
        """

        with gr.Blocks(
            title="DIGANTARA Electronic Load Control",
            css=css,
            theme=gr.themes.Soft(
                primary_hue="orange",
                spacing_size="sm",
                radius_size="sm",
                text_size="sm"
            )
        ) as interface:

            gr.Markdown("# DIGANTARA Electronic Load Control")
            gr.Markdown("**Developed by: Anirudh Iyengar** | Digantara Research and Technologies Pvt. Ltd.")
            gr.Markdown("**Professional Keithley 2380 electronic load automation interface with comprehensive control features**")

            # ================================================================
            # CONNECTION TAB
            # ================================================================

            with gr.Tab("Connection"):
                gr.Markdown("### Instrument Connection")

                # Auto-detection section
                with gr.Row():
                    scan_btn = gr.Button("Scan for Instruments", variant="secondary", size="sm")

                instrument_dropdown = gr.Dropdown(
                    label="Detected Instruments (Electronic Load)",
                    choices=[],
                    interactive=True,
                    info="Select from auto-detected instruments or enter manually below"
                )

                with gr.Row():
                    visa_address = gr.Textbox(
                        label="VISA Address (Manual Entry)",
                        value="USB0::0x05E6::0x2380::802436052807770001::INSTR",
                        scale=3
                    )
                    connect_btn = gr.Button("Connect", variant="primary", scale=1)
                    disconnect_btn = gr.Button("Disconnect", variant="stop", scale=1)
                    test_btn = gr.Button("Test", scale=1)

                connection_status = gr.Textbox(label="Status", value="Disconnected", interactive=False)
                instrument_info = gr.Textbox(label="Instrument Information", interactive=False, lines=3)

                # Auto-detection event handlers
                def scan_for_load_instruments():
                    """Scan for Electronic Load instruments and return choices for dropdown"""
                    if scan_and_identify_instruments is None:
                        return gr.Dropdown(choices=[], value=None), "Disconnected", "Auto-detection not available. Please enter VISA address manually."

                    try:
                        instruments = scan_and_identify_instruments(timeout_ms=5000)
                        # Filter for electronic load instruments only
                        load_instruments = [instr for instr in instruments if instr['instrument_type'] == 'load']

                        if not load_instruments:
                            return gr.Dropdown(choices=[], value=None), "Disconnected", "No Electronic Load instruments detected. Check connections."

                        # Create choices as tuples (display_name, visa_address)
                        choices = [(instr['display_name'], instr['visa_address']) for instr in load_instruments]

                        return gr.Dropdown(choices=choices, value=None), "Disconnected", f"Found {len(load_instruments)} Electronic Load instrument(s)"
                    except Exception as e:
                        return gr.Dropdown(choices=[], value=None), "Disconnected", f"Scan failed: {str(e)}"

                def update_visa_from_dropdown(selected_visa):
                    """Update the VISA address textbox when instrument is selected from dropdown"""
                    if selected_visa:
                        return selected_visa
                    return ""

                scan_btn.click(
                    fn=scan_for_load_instruments,
                    inputs=[],
                    outputs=[instrument_dropdown, connection_status, instrument_info]
                )

                instrument_dropdown.change(
                    fn=update_visa_from_dropdown,
                    inputs=[instrument_dropdown],
                    outputs=[visa_address]
                )

                connect_btn.click(
                    fn=self.connect_electronic_load,
                    inputs=[visa_address],
                    outputs=[instrument_info, connection_status]
                )

                disconnect_btn.click(
                    fn=self.disconnect_electronic_load,
                    inputs=[],
                    outputs=[instrument_info, connection_status]
                )

                test_btn.click(
                    fn=self.test_connection,
                    inputs=[],
                    outputs=[instrument_info]
                )

            # ================================================================
            # BASIC OPERATIONS TAB
            # ================================================================

            with gr.Tab("Basic Operations"):
                gr.Markdown("### Operation Mode Control")
                
                with gr.Row():
                    operation_mode = gr.Dropdown(
                        label="Operation Mode",
                        choices=self.operation_modes,
                        value="CURRent"
                    )
                    set_mode_btn = gr.Button("Set Mode", variant="primary")
                
                mode_status = gr.Textbox(label="Mode Status", interactive=False)
                
                set_mode_btn.click(
                    fn=self.set_operation_mode,
                    inputs=[operation_mode],
                    outputs=[mode_status]
                )

                gr.Markdown("### Input Control")
                gr.Markdown("Enable or disable the electronic load input (ON/OFF control)")

                with gr.Row():
                    enable_input_btn = gr.Button("Enable Input (ON)", variant="primary", scale=1)
                    disable_input_btn = gr.Button("Disable Input (OFF)", variant="stop", scale=1)

                input_status = gr.Textbox(label="Input Status", interactive=False)

                enable_input_btn.click(
                    fn=lambda: self.enable_disable_input(True),
                    inputs=[],
                    outputs=[input_status]
                )

                disable_input_btn.click(
                    fn=lambda: self.enable_disable_input(False),
                    inputs=[],
                    outputs=[input_status]
                )

                gr.Markdown("### Transient Control")
                gr.Markdown("Disable transient mode (needed before changing operation modes)")

                with gr.Row():
                    disable_transient_btn = gr.Button("Disable Transient Mode", variant="secondary", scale=1)

                transient_status = gr.Textbox(label="Transient Status", interactive=False)

                disable_transient_btn.click(
                    fn=self.disable_transient_quick,
                    inputs=[],
                    outputs=[transient_status]
                )

                gr.Markdown("---")
                gr.Markdown("### Quick Setup - Constant Current (CC)")
                
                with gr.Row():
                    cc_current = gr.Number(label="Current (A)", value=1.0)
                    cc_enable = gr.Checkbox(label="Enable Input", value=False)
                    cc_setup_btn = gr.Button("Quick CC Setup", variant="primary")
                
                cc_status = gr.Textbox(label="CC Status", interactive=False)
                
                cc_setup_btn.click(
                    fn=self.quick_setup_cc,
                    inputs=[cc_current, cc_enable],
                    outputs=[cc_status]
                )

                gr.Markdown("### Quick Setup - Constant Voltage (CV)")
                
                with gr.Row():
                    cv_voltage = gr.Number(label="Voltage (V)", value=12.0)
                    cv_enable = gr.Checkbox(label="Enable Input", value=False)
                    cv_setup_btn = gr.Button("Quick CV Setup", variant="primary")
                
                cv_status = gr.Textbox(label="CV Status", interactive=False)
                
                cv_setup_btn.click(
                    fn=self.quick_setup_cv,
                    inputs=[cv_voltage, cv_enable],
                    outputs=[cv_status]
                )

                gr.Markdown("### Quick Setup - Constant Resistance (CR)")
                
                with gr.Row():
                    cr_resistance = gr.Number(label="Resistance (Ω)", value=10.0)
                    cr_enable = gr.Checkbox(label="Enable Input", value=False)
                    cr_setup_btn = gr.Button("Quick CR Setup", variant="primary")
                
                cr_status = gr.Textbox(label="CR Status", interactive=False)
                
                cr_setup_btn.click(
                    fn=self.quick_setup_cr,
                    inputs=[cr_resistance, cr_enable],
                    outputs=[cr_status]
                )

                gr.Markdown("### Quick Setup - Constant Power (CP)")
                
                with gr.Row():
                    cp_power = gr.Number(label="Power (W)", value=50.0)
                    cp_enable = gr.Checkbox(label="Enable Input", value=False)
                    cp_setup_btn = gr.Button("Quick CP Setup", variant="primary")
                
                cp_status = gr.Textbox(label="CP Status", interactive=False)
                
                cp_setup_btn.click(
                    fn=self.quick_setup_cp,
                    inputs=[cp_power, cp_enable],
                    outputs=[cp_status]
                )

            # ================================================================
            # DETAILED CONFIGURATION TAB
            # ================================================================

            with gr.Tab("Detailed Configuration"):
                gr.Markdown("### Current Mode Settings")
                gr.Markdown("**Slew Rate** controls how fast current ramps (A/ms). Example: 0.1 A/ms means 1A takes 10ms to ramp.")

                with gr.Row():
                    curr_level = gr.Number(label="Level (A)", value=1.0)
                    curr_slew = gr.Number(label="Slew Rate (A/ms)", value=0, info="0 = instant, no ramp")
                    curr_prot_enable = gr.Checkbox(label="Protection Enable", value=False)
                    curr_prot_level = gr.Number(label="Protection Level (A)", value=0)
                
                curr_config_btn = gr.Button("Configure Current Settings", variant="primary")
                curr_config_status = gr.Textbox(label="Current Configuration Status", interactive=False, lines=3)
                
                curr_config_btn.click(
                    fn=self.configure_current_settings,
                    inputs=[curr_level, curr_slew, curr_prot_enable, curr_prot_level],
                    outputs=[curr_config_status]
                )

                gr.Markdown("### Voltage Mode Settings")
                
                with gr.Row():
                    volt_level = gr.Number(label="Level (V)", value=12.0)
                    volt_von = gr.Number(label="Von Level (V)", value=0, info="0 = no change")
                    volt_auto_range = gr.Checkbox(label="Auto Range", value=True)
                
                volt_config_btn = gr.Button("Configure Voltage Settings", variant="primary")
                volt_config_status = gr.Textbox(label="Voltage Configuration Status", interactive=False, lines=3)
                
                volt_config_btn.click(
                    fn=self.configure_voltage_settings,
                    inputs=[volt_level, volt_von, volt_auto_range],
                    outputs=[volt_config_status]
                )

                gr.Markdown("### Resistance Mode Settings")
                
                with gr.Row():
                    res_level = gr.Number(label="Level (Ω)", value=10.0)
                    res_range = gr.Number(label="Range (Ω)", value=0, info="0 = no change")
                
                res_config_btn = gr.Button("Configure Resistance Settings", variant="primary")
                res_config_status = gr.Textbox(label="Resistance Configuration Status", interactive=False, lines=2)
                
                res_config_btn.click(
                    fn=self.configure_resistance_settings,
                    inputs=[res_level, res_range],
                    outputs=[res_config_status]
                )

                gr.Markdown("### Power Mode Settings")
                
                with gr.Row():
                    pow_level = gr.Number(label="Level (W)", value=50.0)
                    pow_range = gr.Number(label="Range (W)", value=0, info="0 = no change")
                    pow_prot = gr.Number(label="Protection Level (W)", value=0, info="0 = no change")
                
                pow_config_btn = gr.Button("Configure Power Settings", variant="primary")
                pow_config_status = gr.Textbox(label="Power Configuration Status", interactive=False, lines=3)
                
                pow_config_btn.click(
                    fn=self.configure_power_settings,
                    inputs=[pow_level, pow_range, pow_prot],
                    outputs=[pow_config_status]
                )

            # ================================================================
            # TRANSIENT OPERATIONS TAB
            # ================================================================

            with gr.Tab("Transient Operations"):
                gr.Markdown("### Transient Configuration")
                gr.Markdown("Configure load transient operations for dynamic load testing")
                
                with gr.Row():
                    trans_enable = gr.Checkbox(label="Enable Transient", value=False)
                    trans_mode = gr.Dropdown(
                        label="Mode",
                        choices=self.transient_modes,
                        value="CONTinuous"
                    )
                    trans_type = gr.Dropdown(
                        label="Operation Type",
                        choices=["Current", "Voltage", "Resistance", "Power"],
                        value="Current"
                    )
                
                with gr.Row():
                    trans_a_level = gr.Number(label="Level A", value=1.0)
                    trans_b_level = gr.Number(label="Level B", value=2.0)
                    trans_a_width = gr.Number(label="Width A (s)", value=0.001)
                    trans_b_width = gr.Number(label="Width B (s)", value=0.001)
                
                trans_config_btn = gr.Button("Configure Transient", variant="primary")
                trans_status = gr.Textbox(label="Transient Status", interactive=False, lines=3)
                
                trans_config_btn.click(
                    fn=self.configure_transient,
                    inputs=[trans_enable, trans_mode, trans_type, trans_a_level, trans_b_level, trans_a_width, trans_b_width],
                    outputs=[trans_status]
                )

            # ================================================================
            # MEASUREMENTS & DATA TAB
            # ================================================================

            with gr.Tab("Measurements & Data"):
                gr.Markdown("### Single Measurement")
                
                single_measure_btn = gr.Button("Perform Measurement", variant="primary")
                measurement_results = gr.Textbox(label="Measurement Results", interactive=False, lines=8)
                
                single_measure_btn.click(
                    fn=self.perform_single_measurement,
                    inputs=[],
                    outputs=[measurement_results]
                )

                gr.Markdown("### Continuous Logging")
                
                with gr.Row():
                    log_interval = gr.Number(label="Interval (s)", value=1.0, minimum=0.1)
                    log_duration = gr.Number(label="Duration (s)", value=60, minimum=0, info="0 = indefinite")
                
                with gr.Row():
                    start_logging_btn = gr.Button("Start Logging", variant="primary")
                    stop_logging_btn = gr.Button("Stop Logging", variant="stop")
                
                logging_status = gr.Textbox(label="Logging Status", interactive=False)
                
                start_logging_btn.click(
                    fn=self.start_continuous_logging,
                    inputs=[log_interval, log_duration],
                    outputs=[logging_status]
                )
                
                stop_logging_btn.click(
                    fn=self.stop_continuous_logging,
                    inputs=[],
                    outputs=[logging_status]
                )

                gr.Markdown("### Data Export")
                gr.Markdown("Export measurements and generate plots from last measurement")
                
                with gr.Row():
                    export_csv_btn = gr.Button("Export CSV", variant="secondary")
                    generate_plot_btn = gr.Button("Generate Plot", variant="secondary")
                
                export_status = gr.Textbox(label="Export Status", interactive=False)
                
                # Download section
                gr.Markdown("### Download Files")
                csv_download = gr.File(label="Exported CSV File", interactive=False)
                
                export_csv_btn.click(
                    fn=self.export_measurements,
                    inputs=[],
                    outputs=[export_status, csv_download]
                )
                
                generate_plot_btn.click(
                    fn=self.generate_plot,
                    inputs=[],
                    outputs=[export_status]
                )

            # ================================================================
            # TRIGGER SYSTEM TAB
            # ================================================================

            with gr.Tab("Trigger System"):
                gr.Markdown("### Trigger Configuration")
                
                with gr.Row():
                    trigger_source = gr.Dropdown(
                        label="Trigger Source",
                        choices=self.trigger_sources,
                        value="BUS"
                    )
                    trigger_timer = gr.Number(label="Timer Period (s)", value=1.0, minimum=0.01, maximum=9999.99)
                
                trigger_config_btn = gr.Button("Configure Trigger", variant="primary")
                trigger_status = gr.Textbox(label="Trigger Status", interactive=False, lines=2)
                
                trigger_config_btn.click(
                    fn=self.configure_trigger,
                    inputs=[trigger_source, trigger_timer],
                    outputs=[trigger_status]
                )

                gr.Markdown("### Manual Trigger")
                
                force_trigger_btn = gr.Button("Force Trigger", variant="secondary")
                trigger_force_status = gr.Textbox(label="Force Trigger Status", interactive=False)
                
                force_trigger_btn.click(
                    fn=self.force_trigger,
                    inputs=[],
                    outputs=[trigger_force_status]
                )

            # ================================================================
            # MEMORY & SYSTEM TAB
            # ================================================================

            with gr.Tab("Memory & System"):
                gr.Markdown("### Memory Operations")
                
                with gr.Row():
                    memory_location = gr.Slider(label="Memory Location", minimum=0, maximum=100, value=1, step=1)
                
                with gr.Row():
                    save_setup_btn = gr.Button("Save Setup", variant="primary")
                    recall_setup_btn = gr.Button("Recall Setup", variant="secondary")
                
                memory_status = gr.Textbox(label="Memory Status", interactive=False)
                
                save_setup_btn.click(
                    fn=self.save_setup,
                    inputs=[memory_location],
                    outputs=[memory_status]
                )
                
                recall_setup_btn.click(
                    fn=self.recall_setup,
                    inputs=[memory_location],
                    outputs=[memory_status]
                )

                gr.Markdown("### System Functions")
                
                with gr.Row():
                    reset_btn = gr.Button("Reset Instrument", variant="stop")
                    self_test_btn = gr.Button("Self Test", variant="secondary")
                    status_btn = gr.Button("Get Status", variant="secondary")
                    clear_prot_btn = gr.Button("Clear Protection", variant="secondary")
                
                system_status = gr.Textbox(label="System Status", interactive=False, lines=10)
                
                reset_btn.click(
                    fn=self.reset_instrument,
                    inputs=[],
                    outputs=[system_status]
                )
                
                self_test_btn.click(
                    fn=self.run_self_test,
                    inputs=[],
                    outputs=[system_status]
                )
                
                status_btn.click(
                    fn=self.get_status_summary,
                    inputs=[],
                    outputs=[system_status]
                )
                
                clear_prot_btn.click(
                    fn=self.clear_protection,
                    inputs=[],
                    outputs=[system_status]
                )

                gr.Markdown("### Safety")
                
                safe_shutdown_btn = gr.Button("Safe Shutdown", variant="stop", scale=2)
                shutdown_status = gr.Textbox(label="Shutdown Status", interactive=False)
                
                safe_shutdown_btn.click(
                    fn=self.safe_shutdown,
                    inputs=[],
                    outputs=[shutdown_status]
                )

            # ================================================================
            # FILE OPERATIONS TAB
            # ================================================================

            with gr.Tab("File Operations & Settings"):
                with gr.Column(variant="panel"):
                    gr.Markdown("### File Save Locations (Server-Side)")
                    gr.Markdown("Files are saved on the server in the following directories. Use the download buttons to get files after generation.")

                    # Display-only path information
                    with gr.Group():
                        gr.Textbox(
                            label="Data Directory (CSV files)",
                            value=self.save_locations['data'],
                            interactive=False
                        )
                        gr.Textbox(
                            label="Graphs Directory (PNG files)",
                            value=self.save_locations['graphs'],
                            interactive=False
                        )
                        gr.Textbox(
                            label="Logs Directory (Log files)",
                            value=self.save_locations['logs'],
                            interactive=False
                        )

            gr.Markdown("---")
            gr.Markdown("**DIGANTARA Electronic Load Control** | Professional Grade Electronic Load Automation | All SCPI Commands Verified")

        return interface

    def launch(self, share=False, server_port=7865, auto_open=True, max_attempts=10):
        """Launch Gradio interface with port fallback and full-page layout"""
        self._gradio_interface = self.create_interface()

        for attempt in range(max_attempts):
            current_port = server_port + attempt

            try:
                print(f"Attempting to start electronic load GUI on port {current_port}...")
                self._gradio_interface.launch(
                    server_name="0.0.0.0",
                    share=share,
                    server_port=current_port,
                    prevent_thread_lock=False,
                    show_error=True,
                    inbrowser=True,
                    quiet=False
                )

                print("\n" + "=" * 80)
                hostname = socket.gethostname()
                print(f"Electronic Load GUI is running on port {current_port}")
                print(f"Network access from other PCs: http://{hostname}:{current_port}")
                print("To stop the application, press Ctrl+C in this terminal.")
                print("=" * 80)
                return

            except Exception as e:
                if "address already in use" in str(e).lower() or "port in use" in str(e).lower():
                    print(f"Port {current_port} is in use, trying next port...")
                    if attempt == max_attempts - 1:
                        print(f"\nError: Could not find an available port after {max_attempts} attempts.")
                        print("Please close any other instances or specify a different starting port.")
                        self.cleanup()
                        return
                else:
                    print(f"\nLaunch error: {e}")
                    self.cleanup()
                    return

        print("\nFailed to start the server after multiple attempts.")
        self.cleanup()

def main():
    """Application entry point"""
    print("Keithley 2380 Electronic Load Automation - Professional Gradio Interface")
    print("Comprehensive electronic load control system with all operation modes")
    print("=" * 80)
    print("Starting web interface...")

    app = None
    try:
        start_port = 7865
        max_attempts = 10
        print(f"Looking for an available port starting from {start_port}...")

        for port in range(start_port, start_port + max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('', port))
                    s.close()

                hostname = socket.gethostname()
                print(f"\nFound available port: {port}")
                print("The browser will open automatically when ready.")
                print(f"Network access from other PCs: http://{hostname}:{port}")
                print("")
                print("IMPORTANT: To stop the application, press Ctrl+C in this terminal.")
                print("Closing the browser tab will NOT stop the server.")
                print("=" * 80)

                app = GradioElectronicLoadGUI()
                app.launch(share=False, server_port=port, auto_open=True)
                break

            except OSError as e:
                if "address already in use" in str(e).lower():
                    print(f"Port {port} is in use, trying next port...")
                    if port == start_port + max_attempts - 1:
                        print(f"\nError: Could not find an available port after {max_attempts} attempts.")
                        print("Please close any applications using ports {}-{}" \
                              .format(start_port, start_port + max_attempts - 1))
                        return
                else:
                    print(f"Error checking port {port}: {e}")
                    return

    except KeyboardInterrupt:
        print("\nApplication closed by user.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if app:
            app.cleanup()
        print("\nApplication shutdown complete.")
        print("=" * 80)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nApplication terminated by user.")
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        print("Forcing application exit...")
        os._exit(0)
