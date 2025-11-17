#!/usr/bin/env python3
"""
╔════════════════════════════════════════════════════════════════════════════════╗
║    UNIFIED INSTRUMENT CONTROL SYSTEM - PROFESSIONAL GRADIO INTERFACE           ║
║    Comprehensive control for lab instruments with integrated tabbed interface   ║
║                                                                                ║
║  Purpose: Complete lab automation with unified control of:                     ║
║           - Keithley DMM6500 Digital Multimeter                               ║
║           - Keithley 2230-30-1 Power Supply                                   ║
║           - Keysight DSOX6004A Oscilloscope                                   ║
║                                                                                ║
║  Core Features:                                                                ║
║    • Multi-threaded responsive web UI using Gradio framework                  ║
║    • Integrated tabbed interface for all three instruments                    ║
║    • Complete measurement capabilities for digital multimeter                 ║
║    • Three-channel power supply control with waveform generation             ║
║    • Advanced oscilloscope trigger, measurement and waveform acquisition     ║
║    • Data export for all instruments (CSV, Excel, etc.)                       ║
║    • Graph/plot generation for visualizing measurements                       ║
║    • Thread-safe operations with comprehensive error handling                ║
║                                                                                ║
║  System Requirements:                                                          ║
║    • Python 3.7+                                                              ║
║    • PyVISA library for instrument communication                              ║
║    • Keysight/National Instruments VISA drivers installed                     ║
║    • Matplotlib for graphing capabilities                                     ║
║    • Gradio for web interface                                                 ║
║                                                                                ║
║  Author: DIGANTARA Lab Automation Team                                        ║
║  Version: 1.0.0 | Status: Production Ready                                    ║
╚════════════════════════════════════════════════════════════════════════════════╝
"""

# ============================================================================
# SECTION 1: IMPORTING REQUIRED LIBRARIES
# ============================================================================
import sys
import logging
import threading
import queue
import time
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple, Union
import signal
import atexit
import os
import socket
import gradio as gr
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import io
import base64
import math
import csv
from enum import Enum
import json

# ============================================================================
# SECTION 2: SETTING UP FILE PATHS AND IMPORTING INSTRUMENT CONTROL MODULES
# ============================================================================
# Find the directory where this script is located and go up to find instrument_control
script_dir = Path(__file__).resolve().parent.parent.parent

# Add this directory to Python's search path so it can find our modules
if str(script_dir) not in sys.path:
    sys.path.append(str(script_dir))

# ============================================================================
# Import the instrument control classes
# ============================================================================
try:
    # Import DMM modules
    from instrument_control.keithley_dmm import (
        KeithleyDMM6500, MeasurementFunction, KeithleyDMM6500Error
    )
    
    # Import Power Supply modules
    from instrument_control.keithley_power_supply import (
        KeithleyPowerSupply, KeithleyPowerSupplyError, OutputState
    )
    
    # Import Oscilloscope modules
    from instrument_control.keysight_oscilloscope import (
        KeysightDSOX6004A, KeysightDSOX6004AError
    )
    from instrument_control.scpi_wrapper import SCPIWrapper
    
except ImportError as e:
    print(f"ERROR: Cannot import instrument_control modules: {e}")
    print(f"Current Python path: {sys.path}")
    print(f"Looking for instrument_control in: {script_dir}")
    print("Please ensure the instrument_control package is in your Python path")
    sys.exit(1)


# ============================================================================
# SECTION 3: DMM CONTROLLER CLASS 
# ============================================================================
class DMM_GUI_Controller:
    """Main controller class for the DMM Gradio interface."""
    
    def __init__(self):
        """Initialize the GUI controller."""
        self.dmm: Optional[KeithleyDMM6500] = None
        self.is_connected = False
        self.measurement_thread: Optional[threading.Thread] = None
        self.continuous_measurement = False
        self.measurement_data = []
        self.max_data_points = 1000

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('DMM_GUI')

        # File save locations
        self.save_locations = {
            'data': str(Path.cwd() / "dmm_data"),
            'graphs': str(Path.cwd() / "dmm_graphs")
        }

        # Default settings
        self.default_settings = {
            'visa_address': 'USB0::0x05E6::0x6500::04561287::INSTR',
            'timeout_ms': 30000,
            'measurement_function': 'DC_VOLTAGE',
            'measurement_range': 10.0,
            'resolution': 1e-6,
            'nplc': 1.0,
            'auto_zero': True,
            'measurement_interval': 1.0
        }
    
    def connect_instrument(self, visa_address: str, timeout_ms: int) -> Tuple[str, bool]:
        """
        Connect to the DMM instrument.
        
        Returns:
            Tuple of (status_message, connection_success)
        """
        try:
            if self.is_connected:
                return "Already connected to instrument", True
            
            self.dmm = KeithleyDMM6500(visa_address, timeout_ms)
            
            if self.dmm.connect():
                self.is_connected = True
                info = self.dmm.get_instrument_info()
                if info:
                    msg = f"Connected: {info['manufacturer']} {info['model']} (S/N: {info['serial_number']})"
                else:
                    msg = "Connected to DMM successfully"
                self.logger.info(msg)
                return msg, True
            else:
                return "Failed to connect to instrument", False
                
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            return f"Connection error: {str(e)}", False
    
    def disconnect_instrument(self) -> str:
        """Disconnect from the DMM instrument."""
        try:
            if self.continuous_measurement:
                self.stop_continuous_measurement()
            
            if self.dmm and self.is_connected:
                self.dmm.disconnect()
                self.is_connected = False
                return "Disconnected from instrument"
            else:
                return "No instrument connected"
                
        except Exception as e:
            self.logger.error(f"Disconnection error: {e}")
            return f"Disconnection error: {str(e)}"
    
    def single_measurement(self, function: str, range_val: float, resolution: float, 
                         nplc: float, auto_zero: bool) -> Tuple[str, str]:
        """
        Perform a single measurement.
        
        Returns:
            Tuple of (measurement_result, status_message)
        """
        if not self.is_connected or not self.dmm:
            return "N/A", "Not connected to instrument"
        
        try:
            # Map function string to enum
            func_map = {
                'DC_VOLTAGE': MeasurementFunction.DC_VOLTAGE,
                'AC_VOLTAGE': MeasurementFunction.AC_VOLTAGE,
                'DC_CURRENT': MeasurementFunction.DC_CURRENT,
                'AC_CURRENT': MeasurementFunction.AC_CURRENT,
                'RESISTANCE_2W': MeasurementFunction.RESISTANCE_2W,
                'RESISTANCE_4W': MeasurementFunction.RESISTANCE_4W,
                'CAPACITANCE': MeasurementFunction.CAPACITANCE,
                'FREQUENCY': MeasurementFunction.FREQUENCY
            }
            
            measurement_func = func_map.get(function)
            if not measurement_func:
                return "N/A", f"Unknown measurement function: {function}"
            
            # Perform measurement based on function type
            result = None
            if function == 'DC_VOLTAGE':
                result = self.dmm.measure_dc_voltage(range_val, resolution, nplc, auto_zero)
            elif function == 'AC_VOLTAGE':
                result = self.dmm.measure_ac_voltage(range_val, resolution, nplc)
            elif function == 'DC_CURRENT':
                result = self.dmm.measure_dc_current(range_val, resolution, nplc, auto_zero)
            elif function == 'AC_CURRENT':
                result = self.dmm.measure_ac_current(range_val, resolution, nplc)
            elif function == 'RESISTANCE_2W':
                result = self.dmm.measure_resistance_2w(range_val, resolution, nplc)
            elif function == 'RESISTANCE_4W':
                result = self.dmm.measure_resistance_4w(range_val, resolution, nplc)
            elif function == 'CAPACITANCE':
                result = self.dmm.measure_capacitance(range_val, resolution, nplc)
            elif function == 'FREQUENCY':
                result = self.dmm.measure_frequency(range_val, resolution, nplc)

            if result is not None:
                # Add to measurement data
                timestamp = datetime.now()
                self.measurement_data.append({
                    'timestamp': timestamp,
                    'function': function,
                    'value': result,
                    'range': range_val,
                    'resolution': resolution
                })
                
                # Limit data points
                if len(self.measurement_data) > self.max_data_points:
                    self.measurement_data = self.measurement_data[-self.max_data_points:]
                
                # Format result based on function
                unit_map = {
                    'DC_VOLTAGE': 'V', 'AC_VOLTAGE': 'V',
                    'DC_CURRENT': 'A', 'AC_CURRENT': 'A',
                    'RESISTANCE_2W': 'Ω', 'RESISTANCE_4W': 'Ω',
                    'CAPACITANCE': 'F', 'FREQUENCY': 'Hz'
                }
                unit = unit_map.get(function, '')

                # Format with proper SI prefixes (no scientific notation)
                formatted_result = self._format_with_si_prefix(result, unit)

                return formatted_result, "Measurement successful"
            else:
                return "N/A", "Measurement failed"
                
        except Exception as e:
            self.logger.error(f"Measurement error: {e}")
            return "N/A", f"Measurement error: {str(e)}"
    
    def start_continuous_measurement(self, function: str, range_val: float, resolution: float, 
                                   nplc: float, auto_zero: bool, interval: float) -> str:
        """Start continuous measurements in a separate thread."""
        if not self.is_connected:
            return "Not connected to instrument"
        
        if self.continuous_measurement:
            return "Continuous measurement already running"
        
        self.continuous_measurement = True
        self.measurement_thread = threading.Thread(
            target=self._continuous_measurement_worker,
            args=(function, range_val, resolution, nplc, auto_zero, interval),
            daemon=True
        )
        self.measurement_thread.start()
        return "Continuous measurement started"
    
    def stop_continuous_measurement(self) -> str:
        """Stop continuous measurements."""
        self.continuous_measurement = False
        if self.measurement_thread and self.measurement_thread.is_alive():
            self.measurement_thread.join(timeout=2)
        return "Continuous measurement stopped"
    
    def _continuous_measurement_worker(self, function: str, range_val: float, resolution: float, 
                                     nplc: float, auto_zero: bool, interval: float):
        """Worker thread for continuous measurements."""
        while self.continuous_measurement and self.is_connected:
            try:
                self.single_measurement(function, range_val, resolution, nplc, auto_zero)
                time.sleep(interval)
            except Exception as e:
                self.logger.error(f"Continuous measurement error: {e}")
                break
    
    def get_statistics(self, last_n_points: int = 100) -> Tuple[str, str, str, str, str]:
        """
        Calculate statistics from recent measurements.
        
        Returns:
            Tuple of (count, mean, std_dev, min_val, max_val)
        """
        if not self.measurement_data:
            return "0", "N/A", "N/A", "N/A", "N/A"
        
        # Get recent data points
        recent_data = self.measurement_data[-last_n_points:] if len(self.measurement_data) > last_n_points else self.measurement_data
        values = [point['value'] for point in recent_data]
        
        if not values:
            return "0", "N/A", "N/A", "N/A", "N/A"
        
        try:
            count = len(values)
            mean = np.mean(values)
            std_dev = np.std(values, ddof=1) if count > 1 else 0
            min_val = np.min(values)
            max_val = np.max(values)

            # Get the unit for formatting
            function = recent_data[0]['function'] if recent_data else 'DC_VOLTAGE'
            unit = self._get_unit(function)

            # Format with SI prefixes
            return (
                str(count),
                self._format_with_si_prefix(mean, unit),
                self._format_with_si_prefix(std_dev, unit),
                self._format_with_si_prefix(min_val, unit),
                self._format_with_si_prefix(max_val, unit)
            )
        except Exception as e:
            self.logger.error(f"Statistics calculation error: {e}")
            return "Error", "N/A", "N/A", "N/A", "N/A"
    
    def create_trend_plot(self, last_n_points: int = 100) -> Optional[plt.Figure]:
        """Create a trend plot of recent measurements."""
        if not self.measurement_data:
            return None
        
        try:
            # Get recent data points
            recent_data = self.measurement_data[-last_n_points:] if len(self.measurement_data) > last_n_points else self.measurement_data
            
            if len(recent_data) < 2:
                return None
            
            timestamps = [point['timestamp'] for point in recent_data]
            values = [point['value'] for point in recent_data]
            function = recent_data[0]['function']
            
            # Create plot
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.plot(timestamps, values, 'b-', linewidth=1, marker='o', markersize=2)
            ax.set_xlabel('Time')
            ax.set_ylabel(f'Measurement Value ({self._get_unit(function)})')
            ax.set_title(f'{function.replace("_", " ").title()} Trend')
            ax.grid(True, alpha=0.3)
            
            # Format x-axis
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=6))
            plt.xticks(rotation=45)
            
            plt.tight_layout()
            return fig
        except Exception as e:
            self.logger.error(f"Plot creation error: {e}")
            return None
    
    def _get_unit(self, function: str) -> str:
        """Get the unit for a measurement function."""
        unit_map = {
            'DC_VOLTAGE': 'V', 'AC_VOLTAGE': 'V',
            'DC_CURRENT': 'A', 'AC_CURRENT': 'A',
            'RESISTANCE_2W': 'Ω', 'RESISTANCE_4W': 'Ω',
            'CAPACITANCE': 'F', 'FREQUENCY': 'Hz'
        }
        return unit_map.get(function, '')

    def _format_with_si_prefix(self, value: float, base_unit: str) -> str:
        """
        Format a value with appropriate SI prefix (no scientific notation).

        Args:
            value: The numerical value to format
            base_unit: The base unit (V, A, Ω, F, Hz)

        Returns:
            Formatted string with SI prefix (e.g., "1.234 mV", "5.67 kΩ")
        """
        # SI prefixes from largest to smallest
        prefixes = [
            (1e12, 'T'),   # Tera
            (1e9, 'G'),    # Giga
            (1e6, 'M'),    # Mega
            (1e3, 'k'),    # kilo
            (1, ''),       # base unit
            (1e-3, 'm'),   # milli
            (1e-6, 'µ'),   # micro (using proper µ symbol)
            (1e-9, 'n'),   # nano
            (1e-12, 'p'),  # pico
            (1e-15, 'f'),  # femto
        ]

        abs_value = abs(value)

        # Handle zero
        if abs_value == 0:
            return f"0.000 {base_unit}"

        # Find the appropriate prefix
        for scale, prefix in prefixes:
            if abs_value >= scale:
                scaled_value = value / scale
                # Use appropriate decimal places based on magnitude
                if abs(scaled_value) >= 100:
                    formatted = f"{scaled_value:.2f}"
                elif abs(scaled_value) >= 10:
                    formatted = f"{scaled_value:.3f}"
                else:
                    formatted = f"{scaled_value:.4f}"

                return f"{formatted} {prefix}{base_unit}"

        # If value is extremely small, use femto
        scaled_value = value / 1e-15
        return f"{scaled_value:.4f} f{base_unit}"

    def export_data(self, save_path: str, format_type: str = "CSV") -> str:
        """Export measurement data to file at user-specified location.

        Args:
            save_path: Directory path where file should be saved
            format_type: Export format (CSV, JSON, or Excel)

        Returns:
            Status message
        """
        if not self.measurement_data:
            return "No data to export"

        if not save_path or save_path.strip() == "":
            return "Please select a save location using the Browse button"

        try:
            # Ensure the save directory exists
            save_dir = Path(save_path)
            if not save_dir.exists():
                return f"Error: Directory does not exist: {save_path}"

            if not save_dir.is_dir():
                return f"Error: Path is not a directory: {save_path}"

            df = pd.DataFrame(self.measurement_data)
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

            if format_type == "CSV":
                filename = f"dmm_data_{timestamp_str}.csv"
                filepath = save_dir / filename
                df.to_csv(filepath, index=False)
                return f"✓ Data exported successfully to:\n{filepath}"
            elif format_type == "JSON":
                filename = f"dmm_data_{timestamp_str}.json"
                filepath = save_dir / filename
                df.to_json(filepath, orient='records', date_format='iso')
                return f"✓ Data exported successfully to:\n{filepath}"
            elif format_type == "Excel":
                filename = f"dmm_data_{timestamp_str}.xlsx"
                filepath = save_dir / filename
                df.to_excel(filepath, index=False)
                return f"✓ Data exported successfully to:\n{filepath}"
        except Exception as e:
            self.logger.error(f"Data export error: {e}")
            return f"Export failed: {str(e)}"

    def save_trend_plot(self, last_n_points: int = 100) -> Tuple[Optional[str], str]:
        """Save trend plot to file for browser download.

        Returns:
            Tuple of (filepath, status_message)
        """
        if not self.measurement_data:
            return None, "No data to plot"

        try:
            # Create temporary directory for exports
            import tempfile
            temp_dir = Path(tempfile.gettempdir()) / "dmm_exports"
            temp_dir.mkdir(parents=True, exist_ok=True)

            # Get recent data points
            recent_data = self.measurement_data[-last_n_points:] if len(self.measurement_data) > last_n_points else self.measurement_data

            if len(recent_data) < 2:
                return None, "Insufficient data points for plot (need at least 2)"

            timestamps = [point['timestamp'] for point in recent_data]
            values = [point['value'] for point in recent_data]
            function = recent_data[0]['function']

            # Create plot
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.plot(timestamps, values, 'b-', linewidth=1, marker='o', markersize=2)
            ax.set_xlabel('Time')
            ax.set_ylabel(f'Measurement Value ({self._get_unit(function)})')
            ax.set_title(f'{function.replace("_", " ").title()} Trend')
            ax.grid(True, alpha=0.3)

            # Format x-axis
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=6))
            plt.xticks(rotation=45)

            plt.tight_layout()

            # Save plot
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dmm_trend_{timestamp_str}.png"
            filepath = temp_dir / filename
            plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
            plt.close(fig)

            return str(filepath), "Plot saved successfully. Click download button below to save."
        except Exception as e:
            self.logger.error(f"Plot save error: {e}")
            return None, f"Plot save failed: {str(e)}"
    
    def clear_data(self) -> str:
        """Clear all measurement data."""
        self.measurement_data.clear()
        return "Measurement data cleared"
    
    def get_instrument_status(self) -> Tuple[str, str, str, str]:
        """
        Get instrument status information.
        
        Returns:
            Tuple of (connection_status, instrument_info, errors, system_time)
        """
        if not self.is_connected or not self.dmm:
            return "Disconnected", "N/A", "N/A", "N/A"
        
        try:
            # Connection status
            status = "Connected" if self.is_connected else "Disconnected"
            
            # Instrument info
            info = self.dmm.get_instrument_info()
            if info:
                instrument_info = f"{info['manufacturer']} {info['model']} (S/N: {info['serial_number']})"
                errors = info.get('current_errors', 'None')
            else:
                instrument_info = "Unknown"
                errors = "Unable to query"
            
            # System time
            system_time = self.dmm.get_system_date_time() or "Unknown"
            
            return status, instrument_info, errors, system_time
        except Exception as e:
            self.logger.error(f"Status query error: {e}")
            return "Error", "N/A", f"Error: {str(e)}", "N/A"


# ============================================================================
# SECTION 4: POWER SUPPLY CONTROLLER CLASS
# ============================================================================

class PowerSupplyAutomationGradio:
    """
    Main application class for power supply automation with web interface.

    This class manages connection to the Keithley power supply hardware,
    the web interface, channel configuration, automated voltage ramping,
    and data collection.
    """

    def __init__(self):
        """Initialize the application when it starts."""

        # Power supply connection
        self.power_supply = None

        # Voltage ramping controls
        self.ramping_active = False
        self.ramping_thread = None
        self.ramping_profile = []
        self.ramping_data = []

        # Dictionary containing all settings for voltage ramping
        self.ramping_params = {
            'waveform': 'Sine',
            'target_voltage': 3.0,
            'cycles': 3,
            'points_per_cycle': 50,
            'cycle_duration': 8.0,
            'psu_settle': 0.05,
            'nplc': 1.0,
            'active_channel': 1
        }

        # Data collection and storage
        self.measurement_data = {}
        self.status_queue = queue.Queue()
        self.measurement_active = False

        # Connection status
        self.is_connected = False

        # Set up logging
        self.setup_logging()

        # Channel state tracking
        self.channel_states = {
            i: {"enabled": False, "voltage": 0.0, "current": 0.0, "power": 0.0}
            for i in range(1, 4)
        }

        # Activity log
        self.activity_log = "Application started\n"

        # File save locations
        self.save_locations = {
            'data': str(Path.cwd() / "psu_data")
        }

    def setup_logging(self):
        """Configure logging for system diagnostics."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger("PowerSupplyAutomationGradio")

    # Nested class: Waveform Generator
    class _WaveformGenerator:
        """
        Creates patterns of voltage that change over time.
        Supports Sine, Square, Triangle, Ramp Up, and Ramp Down waveforms.
        """

        TYPES = ["Sine", "Square", "Triangle", "Ramp Up", "Ramp Down"]

        def __init__(self, waveform_type: str = "Sine", target_voltage: float = 3.0,
                     cycles: int = 3, points_per_cycle: int = 50, cycle_duration: float = 8.0):
            """Initialize waveform generator with specified parameters."""
            self.waveform_type = waveform_type if waveform_type in self.TYPES else "Sine"
            self.target_voltage = max(0.0, min(float(target_voltage), 5.0))
            self.cycles = max(1, int(cycles))
            self.points_per_cycle = max(1, int(points_per_cycle))
            self.cycle_duration = float(cycle_duration)

        def generate(self):
            """
            Generate waveform profile.
            Returns a list of tuples, where each tuple is (time_in_seconds, voltage_in_volts)
            """
            profile = []

            for cycle in range(self.cycles):
                for point in range(self.points_per_cycle):
                    pos = point / max(1, (self.points_per_cycle - 1)) if self.points_per_cycle > 1 else 0.0
                    t = cycle * self.cycle_duration + pos * self.cycle_duration

                    if self.waveform_type == 'Sine':
                        v = math.sin(pos * math.pi) * self.target_voltage
                    elif self.waveform_type == 'Square':
                        v = self.target_voltage if pos < 0.5 else 0.0
                    elif self.waveform_type == 'Triangle':
                        if pos < 0.5:
                            v = (pos * 2.0) * self.target_voltage
                        else:
                            v = (2.0 - pos * 2.0) * self.target_voltage
                    elif self.waveform_type == 'Ramp Up':
                        v = pos * self.target_voltage
                    elif self.waveform_type == 'Ramp Down':
                        v = (1.0 - pos) * self.target_voltage
                    else:
                        v = 0.0

                    v = max(0.0, min(v, 5.0))
                    profile.append((round(t, 6), round(v, 6)))

            return profile

    # Nested class: Ramp Data Manager
    class _RampDataManager:
        """
        Collects, stores, and exports data during voltage ramping operations.
        """

        def __init__(self):
            """Initialize data manager and create storage folders."""
            self.voltage_data = []
            self.data_dir = os.path.join(os.getcwd(), 'voltage_ramp_data')
            self.graphs_dir = os.path.join(os.getcwd(), 'voltage_ramp_graphs')

            try:
                os.makedirs(self.data_dir, exist_ok=True)
                os.makedirs(self.graphs_dir, exist_ok=True)
            except Exception:
                pass
        
        def add_point(self, ts, set_v, meas_v, cycle_no, point_idx):
            """Add one measurement data point to the collection."""
            self.voltage_data.append({
                'timestamp': ts,
                'set_voltage': set_v,
                'measured_voltage': meas_v,
                'cycle_number': cycle_no,
                'point_in_cycle': point_idx
            })

        def clear(self):
            """Clear all collected data points."""
            self.voltage_data.clear()
        
        def export_csv(self, folder=None):
            """Export ramping data to CSV file"""
            if not self.voltage_data:
                raise ValueError('No ramping data')
            
            folder = folder or '.'
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            fn = os.path.join(folder, f'psu_ramping_{ts}.csv')
            
            with open(fn, 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(['timestamp', 'set_voltage', 'measured_voltage', 'cycle', 'point'])
                for d in self.voltage_data:
                    w.writerow([
                        d['timestamp'].isoformat(),
                        d['set_voltage'],
                        d['measured_voltage'],
                        d['cycle_number'],
                        d['point_in_cycle']
                    ])
            
            return fn
        
        def generate_graph(self, folder=None, title: Optional[str] = None) -> str:
            """Generate matplotlib graph of set vs measured voltage"""
            if not self.voltage_data:
                raise ValueError('No ramping data')
            
            folder = folder or self.graphs_dir
            
            try:
                os.makedirs(folder, exist_ok=True)
            except Exception:
                pass
            
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            fn = os.path.join(folder, f'voltage_ramp_{ts}.png')
            
            times = []
            set_v = []
            meas_v = []
            
            t0 = self.voltage_data[0]['timestamp'] if self.voltage_data else datetime.now()
            
            for d in self.voltage_data:
                times.append((d['timestamp'] - t0).total_seconds())
                set_v.append(d['set_voltage'])
                meas_v.append(d['measured_voltage'])
            
            try:
                import matplotlib
                matplotlib.use('Agg')
                import matplotlib.pyplot as plt
                
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.plot(times, set_v, label='Set Voltage', color='tab:blue')
                ax.plot(times, meas_v, label='Measured Voltage', color='tab:red')
                ax.set_xlabel('Time (s)')
                ax.set_ylabel('Voltage (V)')
                ax.set_title(title or 'Voltage Ramping')
                ax.grid(True, ls='--', alpha=0.4)
                ax.legend()
                plt.tight_layout()
                plt.savefig(fn, dpi=200)
                plt.close(fig)
                
            except Exception:
                raise
            
            return fn

    # Connection management methods
    def connect_power_supply(self, visa_address: str) -> str:
        """Establish communication with the Keithley power supply via USB."""

        def connect_thread():
            """Background connection task to keep UI responsive."""
            try:
                self.log_message("Attempting to connect to Keithley power supply...", "INFO")

                if not visa_address.strip():
                    raise ValueError("VISA address cannot be empty")

                self.power_supply = KeithleyPowerSupply(visa_address)

                if self.power_supply.connect():
                    self.log_message("Connection established successfully!", "SUCCESS")
                    self.status_queue.put(("connected", None))
                    self.is_connected = True
                else:
                    raise Exception("Connection failed - check VISA address and instrument")

            except Exception as e:
                self.status_queue.put(("error", f"Connection failed: {str(e)}"))
                self.log_message(f"Connection failed: {str(e)}", "ERROR")

        threading.Thread(target=connect_thread, daemon=True).start()
        return "Connecting... please wait"

    def disconnect_power_supply(self) -> str:
        """Close VISA connection to power supply"""
        try:
            if self.power_supply:
                self.power_supply.disconnect()
                self.power_supply = None
            
            self.is_connected = False
            self.measurement_active = False
            
            for channel in self.channel_states:
                self.channel_states[channel]["enabled"] = False
                self.channel_states[channel]["voltage"] = 0.0
                self.channel_states[channel]["current"] = 0.0
                self.channel_states[channel]["power"] = 0.0
            
            self.log_message("Disconnected from power supply", "SUCCESS")
            return "Disconnected"
        
        except Exception as e:
            self.log_message(f"Error during disconnection: {e}", "ERROR")
            return f"Error: {e}"

    # Instrument information and testing
    def get_instrument_info(self) -> str:
        """Query instrument identification and capabilities information"""
        def info_thread():
            try:
                self.log_message("Getting instrument information...", "INFO")
                
                if not self.power_supply or not self.power_supply.is_connected:
                    raise RuntimeError("Power supply not connected")
                
                info = self.power_supply.get_instrument_info()
                
                if info:
                    self.status_queue.put(("info_retrieved", info))
                else:
                    self.status_queue.put(("error", "Failed to retrieve instrument information"))
            
            except Exception as e:
                self.status_queue.put(("error", f"Info retrieval error: {str(e)}"))
        
        if self.is_connected and self.power_supply:
            threading.Thread(target=info_thread, daemon=True).start()
            return "Retrieving info..."
        else:
            return "Error: Power supply not connected"

    def test_connection(self) -> str:
        """Test VISA communication link"""
        try:
            if self.power_supply and self.power_supply.is_connected:
                self.log_message("Connection test: PASSED", "SUCCESS")
                return "✓ Connection test PASSED"
            else:
                self.log_message("Connection test: FAILED", "ERROR")
                return "✗ Connection test FAILED"
        
        except Exception as e:
            self.log_message(f"Connection test error: {e}", "ERROR")
            return f"Error: {e}"

    # Channel configuration and control
    def configure_channel(self, channel: int, voltage: float, current_limit: float, ovp_level: float) -> str:
        """Set up a power supply channel with desired parameters."""
        def config_thread():
            try:
                self.log_message(f"Configuring channel {channel} - V: {voltage:.3f}V, I: {current_limit:.3f}A, OVP: {ovp_level:.1f}V", "INFO")
                
                if not self.power_supply or not self.power_supply.is_connected:
                    raise RuntimeError("Power supply not connected")
                
                success = self.power_supply.configure_channel(
                    channel=channel,
                    voltage=voltage,
                    current_limit=current_limit,
                    ovp_level=ovp_level,
                    enable_output=False
                )
                
                if success:
                    self.status_queue.put(("channel_configured", f"Channel {channel} configured successfully"))
                else:
                    self.status_queue.put(("error", f"Failed to configure channel {channel}"))
            
            except Exception as e:
                self.status_queue.put(("error", f"Channel {channel} configuration error: {str(e)}"))
        
        if self.is_connected and self.power_supply:
            threading.Thread(target=config_thread, daemon=True).start()
            return f"Configuring channel {channel}..."
        else:
            return "Error: Power supply not connected"

    def enable_channel_output(self, channel: int) -> str:
        """Enable output on specified channel"""
        def enable_thread():
            try:
                self.log_message(f"Enabling output on channel {channel}...", "INFO")
                
                if not self.power_supply or not self.power_supply.is_connected:
                    raise RuntimeError("Power supply not connected")
                
                success = self.power_supply.enable_channel_output(channel)
                
                if success:
                    self.channel_states[channel]["enabled"] = True
                    self.status_queue.put(("channel_enabled", channel))
                else:
                    self.status_queue.put(("error", f"Failed to enable channel {channel} output"))
            
            except Exception as e:
                self.status_queue.put(("error", f"Channel {channel} enable error: {str(e)}"))
        
        if self.is_connected and self.power_supply:
            threading.Thread(target=enable_thread, daemon=True).start()
            return f"Enabling channel {channel}..."
        else:
            return "Error: Power supply not connected"

    def disable_channel_output(self, channel: int) -> str:
        """Disable output on specified channel"""
        def disable_thread():
            try:
                self.log_message(f"Disabling output on channel {channel}...", "INFO")
                
                if not self.power_supply or not self.power_supply.is_connected:
                    raise RuntimeError("Power supply not connected")
                
                success = self.power_supply.disable_channel_output(channel)
                
                if success:
                    self.channel_states[channel]["enabled"] = False
                    self.status_queue.put(("channel_disabled", channel))
                else:
                    self.status_queue.put(("error", f"Failed to disable channel {channel} output"))
            
            except Exception as e:
                self.status_queue.put(("error", f"Channel {channel} disable error: {str(e)}"))
        
        if self.is_connected and self.power_supply:
            threading.Thread(target=disable_thread, daemon=True).start()
            return f"Disabling channel {channel}..."
        else:
            return "Error: Power supply not connected"

    def measure_channel_output(self, channel: int) -> Tuple[str, str, str]:
        """Read current voltage and current from specified channel"""
        try:
            if not self.power_supply or not self.power_supply.is_connected:
                raise RuntimeError("Power supply not connected")

            measurement = self.power_supply.measure_channel_output(channel)

            if measurement and isinstance(measurement, tuple) and len(measurement) == 2:
                voltage = float(measurement[0])
                current = float(measurement[1])
                power = voltage * current

                self.channel_states[channel]["voltage"] = voltage
                self.channel_states[channel]["current"] = current
                self.channel_states[channel]["power"] = power

                self.log_message(f"Channel {channel}: {voltage:.3f}V, {current:.3f}A, {power:.3f}W", "SUCCESS")

                return f"{voltage:.3f} V", f"{current:.3f} A", f"{power:.3f} W"

            else:
                self.log_message(f"Failed to measure channel {channel} output", "ERROR")
                return "Error", "Error", "Error"

        except Exception as e:
            self.log_message(f"Channel {channel} measurement error: {str(e)}", "ERROR")
            return "Error", "Error", "Error"

    # Global operations and safety
    def measure_all_channels(self) -> Tuple[str, str, str, str, str, str, str, str, str]:
        """
        Measure voltage and current from all 3 channels in sequence.
        Returns a tuple of 9 strings for all channel measurements.
        """
        if not (self.is_connected and self.power_supply and self.power_supply.is_connected):
            error_tuple = ("Error",) * 9
            return error_tuple

        try:
            self.log_message("Starting sequential measurement of all channels...", "INFO")

            results = []

            for channel in range(1, 4):
                try:
                    if not self.power_supply or not self.power_supply.is_connected:
                        raise RuntimeError("Power supply not connected")

                    measurement = self.power_supply.measure_channel_output(channel)

                    if measurement and isinstance(measurement, tuple) and len(measurement) == 2:
                        voltage = float(measurement[0])
                        current = float(measurement[1])
                        power = voltage * current

                        self.channel_states[channel]["voltage"] = voltage
                        self.channel_states[channel]["current"] = current
                        self.channel_states[channel]["power"] = power

                        self.log_message(f"Channel {channel}: {voltage:.3f}V, {current:.3f}A, {power:.3f}W", "SUCCESS")

                        results.extend([
                            f"{voltage:.3f} V",
                            f"{current:.3f} A",
                            f"{power:.3f} W"
                        ])

                    else:
                        self.log_message(f"Failed to measure channel {channel}", "ERROR")
                        results.extend(["Error", "Error", "Error"])

                    # Add delay between measurements (except after the last channel)
                    if channel < 3:
                        time.sleep(0.8)  # Wait 0.8 seconds before next measurement

                except Exception as e:
                    self.log_message(f"Error measuring channel {channel}: {e}", "ERROR")
                    results.extend(["Error", "Error", "Error"])

            self.log_message("Sequential measurement completed", "SUCCESS")
            return tuple(results)

        except Exception as e:
            self.log_message(f"Error in sequential measurement: {e}", "ERROR")
            error_tuple = ("Error",) * 9
            return error_tuple

    def disable_all_outputs(self) -> str:
        """Disable output on all three channels (safety shutdown)"""
        def disable_all_thread():
            try:
                self.log_message("Emergency shutdown - disabling all outputs...", "ERROR")
                
                if not self.power_supply or not self.power_supply.is_connected:
                    raise RuntimeError("Power supply not connected")
                
                success = self.power_supply.disable_all_outputs()
                
                if success:
                    for ch in range(1, 4):
                        self.channel_states[ch]["enabled"] = False
                    self.status_queue.put(("all_disabled", "All outputs disabled successfully"))
                else:
                    self.status_queue.put(("error", "Failed to disable all outputs"))
            
            except Exception as e:
                self.status_queue.put(("error", f"Disable all error: {str(e)}"))
        
        if self.is_connected and self.power_supply:
            threading.Thread(target=disable_all_thread, daemon=True).start()
            return "Disabling all outputs..."
        else:
            return "Error: Power supply not connected"

    def emergency_stop(self) -> str:
        """
        Immediately disables all outputs for safety.
        Use this for dangerous or unexpected behavior.
        """
        self.log_message("EMERGENCY STOP ACTIVATED!", "ERROR")
        return self.disable_all_outputs()

    # Data logging and export
    def log_message(self, message: str, level: str = "INFO"):
        """Add timestamped message to activity log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}\n"
        self.activity_log += log_entry
        self.logger.log(
            getattr(logging, level, logging.INFO),
            message
        )

    def export_measurement_data(self, save_path: str) -> str:
        """Export collected measurements to CSV file at user-specified location

        Args:
            save_path: Directory path where file should be saved

        Returns:
            Status message
        """
        try:
            if not self.measurement_data:
                return "No measurement data to export"

            if not save_path or save_path.strip() == "":
                return "Please select a save location using the Browse button"

            # Ensure the save directory exists
            save_dir = Path(save_path)
            if not save_dir.exists():
                return f"Error: Directory does not exist: {save_path}"

            if not save_dir.is_dir():
                return f"Error: Path is not a directory: {save_path}"

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"power_supply_data_{timestamp}.csv"
            filepath = save_dir / filename

            with open(filepath, "w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Timestamp", "Channel", "Voltage (V)", "Current (A)", "Power (W)"])

                for channel, measurements in self.measurement_data.items():
                    for measurement in measurements:
                        writer.writerow([
                            measurement["timestamp"].isoformat(),
                            channel,
                            f"{measurement['voltage']:.6f}",
                            f"{measurement['current']:.6f}",
                            f"{measurement['power']:.6f}"
                        ])

            self.log_message(f"Data exported to: {filepath}", "SUCCESS")
            return f"✓ Data exported successfully to:\n{filepath}"

        except Exception as e:
            self.log_message(f"Export error: {e}", "ERROR")
            return f"Export error: {e}"

    def clear_measurement_data(self) -> str:
        """Clear all collected measurement data"""
        self.measurement_data.clear()
        self.log_message("Measurement data cleared", "INFO")
        return "Measurement data cleared"

    def toggle_auto_measure(self, enabled: bool) -> str:
        """Enable or disable automatic periodic measurement collection"""
        self.measurement_active = enabled
        if enabled:
            self.log_message("Auto-measurement enabled", "SUCCESS")
            return "Auto-measurement enabled"
        else:
            self.log_message("Auto-measurement disabled", "INFO")
            return "Auto-measurement disabled"

    def execute_waveform_ramping(self):
        """Execute the generated waveform profile on the active channel"""
        if not self.ramping_profile:
            self.log_message("No waveform profile generated", "ERROR")
            return

        if not self.power_supply or not self.is_connected:
            self.log_message("Power supply not connected", "ERROR")
            return

        channel = self.ramping_params['active_channel']
        psu_settle = self.ramping_params.get('psu_settle', 0.05)

        self.log_message(f"Starting waveform execution on Channel {channel}", "INFO")
        self.log_message(f"Profile: {len(self.ramping_profile)} points, {self.ramping_params['cycles']} cycles", "INFO")

        # Clear previous ramping data
        self.ramping_data = []

        try:
            # Enable channel output before starting
            self.power_supply.set_output_state(channel, OutputState.ON)
            time.sleep(0.1)

            cycle_num = 0
            points_per_cycle = self.ramping_params['points_per_cycle']

            for idx, (time_setpoint, voltage) in enumerate(self.ramping_profile):
                if not self.ramping_active:
                    self.log_message("Waveform execution stopped by user", "WARNING")
                    break

                # Calculate current cycle number
                cycle_num = idx // points_per_cycle
                point_in_cycle = idx % points_per_cycle

                # Set voltage on channel
                self.power_supply.set_voltage(channel, voltage)

                # Wait for settling
                time.sleep(psu_settle)

                # Measure actual voltage and current
                try:
                    measured_v = self.power_supply.measure_voltage(channel)
                    measured_i = self.power_supply.measure_current(channel)
                except Exception as meas_err:
                    self.logger.warning(f"Measurement error at point {idx}: {meas_err}")
                    measured_v = voltage  # Use setpoint as fallback
                    measured_i = 0.0

                # Store data point
                data_point = {
                    'timestamp': datetime.now(),
                    'set_voltage': voltage,
                    'measured_voltage': measured_v,
                    'measured_current': measured_i,
                    'cycle_number': cycle_num,
                    'point_in_cycle': point_in_cycle,
                    'point_index': idx
                }
                self.ramping_data.append(data_point)

                # Log progress every 10% of total points
                if idx % max(1, len(self.ramping_profile) // 10) == 0:
                    progress = (idx / len(self.ramping_profile)) * 100
                    self.log_message(f"Waveform progress: {progress:.1f}% (Cycle {cycle_num + 1}/{self.ramping_params['cycles']})", "INFO")

            # Waveform complete - disable output for safety
            self.power_supply.set_voltage(channel, 0.0)
            time.sleep(0.1)
            self.power_supply.set_output_state(channel, OutputState.OFF)

            if self.ramping_active:
                self.log_message(f"Waveform execution COMPLETE. {len(self.ramping_data)} points collected.", "SUCCESS")

            self.ramping_active = False

        except Exception as e:
            self.ramping_active = False
            self.log_message(f"Waveform execution error: {e}", "ERROR")
            # Attempt to disable output for safety
            try:
                self.power_supply.set_voltage(channel, 0.0)
                self.power_supply.set_output_state(channel, OutputState.OFF)
            except:
                pass

    def create_gradio_interface(self):
        """Create the web interface for power supply control."""
        
        # This method is now called from our unified interface
        # Rather than creating and returning a Gradio interface,
        # we'll just return the components needed for the unified interface
        return None


# ============================================================================
# SECTION 5: OSCILLOSCOPE CONTROLLER CLASS AND UTILITIES
# ============================================================================

def parse_timebase_string(value: str) -> float:
    """Parse timebase string with unit suffixes to seconds"""
    value = value.strip().lower()
    if "ns" in value:
        return float(value.replace("ns", "").strip()) / 1_000_000_000
    elif "µs" in value or "us" in value:
        return float(value.replace("µs", "").replace("us", "").strip()) / 1_000_000
    elif "ms" in value:
        return float(value.replace("ms", "").strip()) / 1000
    elif "s" in value:
        return float(value.replace("s", "").strip())
    else:
        return float(value)

TRIGGER_SLOPE_MAP = {
    "Rising": "POS",
    "Falling": "NEG",
    "Either": "EITH"
}

def format_si_value(value: float, kind: str) -> str:
    """Format numeric values with SI prefixes for human readability"""
    v = abs(value)
    if kind == "freq":
        if v >= 1e9:
            return f"{value/1e9:.3f} GHz"
        if v >= 1e6:
            return f"{value/1e6:.3f} MHz"
        if v >= 1e3:
            return f"{value/1e3:.3f} kHz"
        return f"{value:.3f} Hz"
    if kind == "time":
        if v >= 1:
            return f"{value:.3f} s"
        if v >= 1e-3:
            return f"{value*1e3:.3f} ms"
        if v >= 1e-6:
            return f"{value*1e6:.3f} µs"
        if v >= 1e-9:
            return f"{value*1e9:.3f} ns"
        return f"{value*1e12:.3f} ps"
    if kind == "volt":
        if v >= 1e3:
            return f"{value/1e3:.3f} kV"
        if v >= 1:
            return f"{value:.3f} V"
        if v >= 1e-3:
            return f"{value*1e3:.3f} mV"
        return f"{value*1e6:.3f} µV"
    if kind == "percent":
        return f"{value:.2f} %"
    return f"{value}"

def format_measurement_value(meas_type: str, value: Optional[float]) -> str:
    """Format measurement values with appropriate units based on type"""
    if value is None:
        return "N/A"

    if meas_type == "FREQ":
        return format_si_value(value, "freq")
    if meas_type in ["PERiod", "RISE", "FALL", "PWIDth", "NWIDth"]:
        return format_si_value(value, "time")
    if meas_type in ["VAMP", "VTOP", "VBASe", "VAVG", "VRMS", "VMAX", "VMIN", "VPP",]:
        return format_si_value(value, "volt")
    if meas_type in ["DUTYcycle", "NDUTy", "OVERshoot"]:
        return format_si_value(value, "percent")
    return f"{value}"

# Data acquisition class for oscilloscope
class OscilloscopeDataAcquisition:
    """
    Data acquisition handler with thread-safe waveform capture and file I/O.
    Implements high-level waveform acquisition, CSV export, and plot generation
    with comprehensive error handling and progress tracking.
    """
    def __init__(self, oscilloscope_instance, io_lock: Optional[threading.RLock] = None):
        self.scope = oscilloscope_instance
        self._logger = logging.getLogger(f'{self.__class__.__name__}')
        self.default_data_dir = Path.cwd() / "data"
        self.default_graph_dir = Path.cwd() / "graphs"
        self.default_screenshot_dir = Path.cwd() / "screenshots"
        self.io_lock = io_lock

    def acquire_waveform_data(self, channel: int, max_points: int = 62500) -> Optional[Dict[str, Any]]:
        """
        Acquire waveform data from specified channel with automatic format conversion.
        Thread-safe acquisition using oscilloscope's built-in waveform transfer.
        """
        if not self.scope.is_connected:
            self._logger.error("Cannot acquire data: oscilloscope not connected")
            return None

        try:
            lock = self.io_lock
            if lock:
                with lock:
                    waveform_data = self._acquire_waveform_scpi(channel, max_points)
            else:
                waveform_data = self._acquire_waveform_scpi(channel, max_points)

            if waveform_data:
                self._logger.info(f"Acquired {len(waveform_data['voltage'])} points from channel {channel}")
                return waveform_data
        except Exception as e:
            self._logger.error(f"Waveform acquisition failed: {e}")
            return None

    def _acquire_waveform_scpi(self, channel: int, max_points: int) -> Optional[Dict[str, Any]]:
        """Internal SCPI-based waveform acquisition with preamble parsing"""
        try:
            self.scope._scpi_wrapper.write(f":WAVeform:SOURce CHANnel{channel}")
            self.scope._scpi_wrapper.write(":WAVeform:FORMat BYTE")
            self.scope._scpi_wrapper.write(":WAVeform:POINts:MODE RAW")
            self.scope._scpi_wrapper.write(f":WAVeform:POINts {max_points}")
            preamble = self.scope._scpi_wrapper.query(":WAVeform:PREamble?")
            preamble_parts = preamble.split(',')
            y_increment = float(preamble_parts[7])
            y_origin = float(preamble_parts[8])
            y_reference = float(preamble_parts[9])
            x_increment = float(preamble_parts[4])
            x_origin = float(preamble_parts[5])
            raw_data = self.scope._scpi_wrapper.query_binary_values(":WAVeform:DATA?", datatype='B')
            voltage_data = [(value - y_reference) * y_increment + y_origin for value in raw_data]
            time_data = [x_origin + (i * x_increment) for i in range(len(voltage_data))]

            return {
                'channel': channel,
                'time': time_data,
                'voltage': voltage_data,
                'sample_rate': 1.0 / x_increment,
                'time_increment': x_increment,
                'voltage_increment': y_increment,
                'points_count': len(voltage_data),
                'acquisition_time': datetime.now().isoformat(),
                'is_math': False
            }
        except Exception as e:
            self._logger.error(f"SCPI acquisition failed: {e}")
            return None

    def acquire_math_function_data(self, function_num: int, max_points: int = 62500) -> Optional[Dict[str, Any]]:
        """
        Acquire waveform data from specified math function with automatic format conversion.
        Thread-safe acquisition using oscilloscope's built-in waveform transfer.
        """
        if not self.scope.is_connected:
            self._logger.error("Cannot acquire data: oscilloscope not connected")
            return None

        try:
            lock = self.io_lock
            if lock:
                with lock:
                    waveform_data = self._acquire_math_waveform_scpi(function_num, max_points)
            else:
                waveform_data = self._acquire_math_waveform_scpi(function_num, max_points)

            if waveform_data:
                self._logger.info(f"Acquired {len(waveform_data['voltage'])} points from math function {function_num}")
                return waveform_data
        except Exception as e:
            self._logger.error(f"Math waveform acquisition failed: {e}")
            return None

    def _acquire_math_waveform_scpi(self, function_num: int, max_points: int) -> Optional[Dict[str, Any]]:
        """Internal SCPI-based math function waveform acquisition with preamble parsing"""
        try:
            # ✓ Manual pg 1201: :WAVeform:SOURce FUNCtion<m>
            self.scope._scpi_wrapper.write(f":WAVeform:SOURce FUNCtion{function_num}")
            self.scope._scpi_wrapper.write(":WAVeform:FORMat BYTE")
            self.scope._scpi_wrapper.write(":WAVeform:POINts:MODE RAW")
            self.scope._scpi_wrapper.write(f":WAVeform:POINts {max_points}")
            preamble = self.scope._scpi_wrapper.query(":WAVeform:PREamble?")
            preamble_parts = preamble.split(',')
            y_increment = float(preamble_parts[7])
            y_origin = float(preamble_parts[8])
            y_reference = float(preamble_parts[9])
            x_increment = float(preamble_parts[4])
            x_origin = float(preamble_parts[5])
            raw_data = self.scope._scpi_wrapper.query_binary_values(":WAVeform:DATA?", datatype='B')
            voltage_data = [(value - y_reference) * y_increment + y_origin for value in raw_data]
            time_data = [x_origin + (i * x_increment) for i in range(len(voltage_data))]

            return {
                'channel': function_num,
                'time': time_data,
                'voltage': voltage_data,
                'sample_rate': 1.0 / x_increment,
                'time_increment': x_increment,
                'voltage_increment': y_increment,
                'points_count': len(voltage_data),
                'acquisition_time': datetime.now().isoformat(),
                'is_math': True
            }
        except Exception as e:
            self._logger.error(f"Math SCPI acquisition failed: {e}")
            return None

    def export_to_csv(self, waveform_data: Dict[str, Any], custom_path: Optional[str] = None,
                      filename: Optional[str] = None) -> Optional[str]:
        """Export waveform data to CSV with comprehensive metadata"""
        if not waveform_data:
            self._logger.error("No waveform data to export")
            return None

        try:
            # Use provided path or default data directory
            if custom_path is None:
                save_dir = self.default_data_dir
            else:
                save_dir = Path(custom_path)
            save_dir.mkdir(parents=True, exist_ok=True)

            if filename is None:
                source_label = "MATH" if waveform_data['is_math'] else "CH"
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                filename = f"waveform_{source_label}{waveform_data['channel']}_{timestamp}.csv"

            if not filename.endswith('.csv'):
                filename += '.csv'

            filepath = save_dir / filename

            df = pd.DataFrame({
                'Time (s)': waveform_data['time'],
                'Voltage (V)': waveform_data['voltage']
            })

            with open(filepath, 'w') as f:
                source_label = "Math Function" if waveform_data['is_math'] else "Channel"
                f.write(f"# Oscilloscope Waveform Data\n")
                f.write(f"# {source_label}: {waveform_data['channel']}\n")
                f.write(f"# Acquisition Time: {waveform_data['acquisition_time']}\n")
                f.write(f"# Sample Rate: {waveform_data['sample_rate']:.2e} Hz\n")
                f.write(f"# Points Count: {waveform_data['points_count']}\n")
                f.write(f"# Time Increment: {waveform_data['time_increment']:.2e} s\n")
                f.write(f"# Voltage Increment: {waveform_data['voltage_increment']:.2e} V\n")
                f.write("\n")
                df.to_csv(filepath, mode='a', index=False)

            self._logger.info(f"CSV exported: {filepath}")
            return str(filepath)
        except Exception as e:
            self._logger.error(f"CSV export failed: {e}")
            return None

    def generate_waveform_plot(self, waveform_data: Dict[str, Any], custom_path: Optional[str] = None,
                               filename: Optional[str] = None, plot_title: Optional[str] = None) -> Optional[str]:
        """Generate professional waveform plot with measurements overlay"""
        measurements = {}
        try:
            if waveform_data['is_math']:
                # For math functions, use measure_math_single
                function_num = waveform_data['channel']
                if self.io_lock:
                    with self.io_lock:
                        measurements_list = [
                            "FREQ", "PERiod", "VPP", "VAMP", "VTOP", "VBASe",
                            "VAVG", "VRMS", "VMAX", "VMIN", "RISE", "FALL"
                        ]
                        for meas in measurements_list:
                            try:
                                val = self.scope.measure_math_single(function_num, meas)
                                if val is not None:
                                    measurements[meas] = val
                            except:
                                pass
                else:
                    measurements_list = [
                        "FREQ", "PERiod", "VPP", "VAMP", "VTOP", "VBASe",
                        "VAVG", "VRMS", "VMAX", "VMIN", "RISE", "FALL"
                    ]
                    for meas in measurements_list:
                        try:
                            val = self.scope.measure_math_single(function_num, meas)
                            if val is not None:
                                measurements[meas] = val
                        except:
                            pass
            else:
                # For regular channels, use measure_single
                channel = waveform_data['channel']
                if self.io_lock:
                    with self.io_lock:
                        measurements = self.scope.get_all_measurements(channel) or {}
                else:
                    measurements = self.scope.get_all_measurements(channel) or {}
        except Exception as e:
            self._logger.warning(f"Failed to get measurements: {e}")
            measurements = {}

        if not waveform_data:
            self._logger.error("No waveform data to plot")
            return None

        try:
            save_dir = Path(custom_path) if custom_path else self.default_graph_dir
            save_dir.mkdir(parents=True, exist_ok=True)

            if filename is None:
                source_label = "MATH" if waveform_data['is_math'] else "CH"
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                filename = f"waveform_plot_{source_label}{waveform_data['channel']}_{timestamp}.png"

            if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                filename += '.png'

            filepath = save_dir / filename

            fig, ax = plt.subplots(figsize=(12, 8))
            time_data = waveform_data['time']
            voltage_data = waveform_data['voltage']

            if len(time_data) > 100000:
                step = len(time_data) // 100000
                time_data = time_data[::step]
                voltage_data = voltage_data[::step]

            ax.plot(time_data, voltage_data, 'b-', linewidth=1.0, rasterized=True)

            if plot_title is None:
                source_label = "Math Function" if waveform_data['is_math'] else "Channel"
                plot_title = f"Oscilloscope Waveform - {source_label} {waveform_data['channel']}"

            ax.set_title(plot_title, fontsize=14, fontweight='bold')
            ax.set_xlabel('Time (s)', fontsize=12)
            ax.set_ylabel('Voltage (V)', fontsize=12)
            ax.grid(True, alpha=0.3)

            measurements_text = "MEASUREMENTS:\n"
            measurements_text += "─" * 25 + "\n"

            key_measurements = [
                ('Freq', 'FREQ'), ('Period', 'PERiod'), ('VPP', 'VPP'),
                ('VAVG', 'VAVG'), ('VRMS', 'VRMS'), ('VMAX', 'VMAX'),
                ('VMIN', 'VMIN'), ('DUTYcycle', 'DUTYcycle')
            ]

            for display_name, meas_key in key_measurements:
                value = measurements.get(meas_key)
                formatted_value = format_measurement_value(meas_key, value)
                measurements_text += f"{display_name}: {formatted_value}\n"

            ax.text(0.02, 0.98, measurements_text,
                    transform=ax.transAxes,
                    fontsize=9,
                    verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.85),
                    family='monospace')

            plt.tight_layout()
            plt.savefig(filepath, dpi=600, bbox_inches='tight', facecolor='white')
            plt.close(fig)

            self._logger.info(f"Plot saved: {filepath}")
            return str(filepath)
        except Exception as e:
            self._logger.error(f"Plot generation failed: {e}")
            return None


# Main oscilloscope controller class
class GradioOscilloscopeGUI:
    """
    Professional oscilloscope control interface with comprehensive feature set.
    Implements connection management, channel configuration, trigger modes,
    math functions, marker operations, and complete data acquisition workflow.
    """

    def __init__(self):
        self.oscilloscope = None
        self.data_acquisition = None
        self.last_acquired_data = None
        self.io_lock = threading.RLock()
        self._shutdown_flag = threading.Event()
        self._gradio_interface = None
        
        self.save_locations = {
            'data': str(Path.cwd() / "data"),
            'graphs': str(Path.cwd() / "graphs"),
            'screenshots': str(Path.cwd() / "screenshots")
        }
        
        self.setup_logging()
        self.setup_cleanup_handlers()
        
        self.timebase_scales: List[Union[str, int, float, Tuple[str, Union[str, int, float]]]] = [
            ("1 ns", 1e-9), ("2 ns", 2e-9), ("5 ns", 5e-9),
            ("10 ns", 10e-9), ("20 ns", 20e-9), ("50 ns", 50e-9),
            ("100 ns", 100e-9), ("200 ns", 200e-9), ("500 ns", 500e-9),
            ("1 µs", 1e-6), ("2 µs", 2e-6), ("5 µs", 5e-6),
            ("10 µs", 10e-6), ("20 µs", 20e-6), ("50 µs", 50e-6),
            ("100 µs", 100e-6), ("200 µs", 200e-6), ("500 µs", 500e-6),
            ("1 ms", 1e-3), ("2 ms", 2e-3), ("5 ms", 5e-3),
            ("10 ms", 10e-3), ("20 ms", 20e-3), ("50 ms", 50e-3),
            ("100 ms", 100e-3), ("200 ms", 200e-3), ("500 ms", 500e-3),
            ("1 s", 1.0), ("2 s", 2.0), ("5 s", 5.0),
            ("10 s", 10.0), ("20 s", 20.0), ("50 s", 50.0)
        ]
        
        self.measurement_types = [
            "FREQ", "PERiod", "VPP", "VAMP", "OVERshoot", "VTOP",
            "VBASe", "VAVG", "VRMS", "VMAX", "VMIN", "RISE", "FALL",
            "DUTYcycle", "NDUTy", "PWIDth", "NWIDth"
        ]

    def setup_logging(self):
        """Configure logging for system diagnostics"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('GradioOscilloscopeAutomation')

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
        """Cleanup resources and disconnect oscilloscope"""
        try:
            self._shutdown_flag.set()
            if self.oscilloscope and hasattr(self.oscilloscope, 'is_connected'):
                if self.oscilloscope.is_connected:
                    print("Disconnecting oscilloscope...")
                    self.oscilloscope.disconnect()
            self.oscilloscope = None
            self.data_acquisition = None
            plt.close('all')
            print("Cleanup completed.")
        except Exception as e:
            print(f"Cleanup error: {e}")

    # Connection management
    def connect_oscilloscope(self, visa_address: str):
        """Establish VISA connection and query instrument identification"""
        try:
            if not visa_address:
                return "Error: VISA address is empty", "Disconnected"

            self.oscilloscope = KeysightDSOX6004A(visa_address)

            if self.oscilloscope.connect():
                self.data_acquisition = OscilloscopeDataAcquisition(self.oscilloscope, io_lock=self.io_lock)

                info = self.oscilloscope.get_instrument_info()
                if info:
                    info_text = f"Connected: {info['manufacturer']} {info['model']} | S/N: {info['serial_number']} | FW: {info['firmware_version']}"
                    return info_text, "Connected"
                else:
                    return "Connected (no info available)", "Connected"

            else:
                return "Connection failed", "Disconnected"
        except Exception as e:
            return f"Error: {str(e)}", "Disconnected"

    def disconnect_oscilloscope(self):
        """Close connection to oscilloscope"""
        try:
            if self.oscilloscope:
                self.oscilloscope.disconnect()
            self.oscilloscope = None
            self.data_acquisition = None
            self.last_acquired_data = None
            self.logger.info("Disconnected successfully")
            return "Disconnected successfully", "Disconnected"
        except Exception as e:
            self.logger.error(f"Disconnect error: {e}")
            return f"Disconnect error: {str(e)}", "Disconnected"

    def test_connection(self):
        """Verify oscilloscope connectivity"""
        if self.oscilloscope and self.oscilloscope.is_connected:
            return "✓ Connection test: PASSED"
        else:
            return "✗ Connection test: FAILED - Not connected"

    # Channel configuration
    def configure_channel(self, ch1, ch2, ch3, ch4, v_scale, v_offset, coupling, probe):
        """Configure vertical parameters for selected channels"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        channel_states = {1: ch1, 2: ch2, 3: ch3, 4: ch4}

        try:
            success_count = 0
            disabled_count = 0

            for channel, enabled in channel_states.items():
                with self.io_lock:
                    if enabled:
                        success = self.oscilloscope.configure_channel(
                            channel=channel,
                            vertical_scale=v_scale,
                            vertical_offset=v_offset,
                            coupling=coupling,
                            probe_attenuation=probe
                        )
                        if success:
                            success_count += 1
                    else:
                        try:
                            with self.io_lock:
                                self.oscilloscope._scpi_wrapper.write(f":CHANnel{channel}:DISPlay OFF")
                                disabled_count += 1
                        except Exception as e:
                            self.logger.warning(f"Failed to disable channel {channel}: {e}")

            return f"Configured: {success_count} enabled, {disabled_count} disabled"
        except Exception as e:
            return f"Configuration error: {str(e)}"

    # Timebase & trigger configuration
    def configure_timebase(self, time_scale_input):
        """Set horizontal timebase parameters"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            if isinstance(time_scale_input, (int, float)):
                time_scale = float(time_scale_input)
                display_scale = format_si_value(time_scale, 'time')
            else:
                time_scale = parse_timebase_string(time_scale_input)
                display_scale = time_scale_input

            with self.io_lock:
                success = self.oscilloscope.configure_timebase(time_scale)

            if success:
                return f"Timebase: {display_scale} ({time_scale}s/div)"
            else:
                return "Timebase configuration failed"
        except Exception as e:
            return f"Error: {str(e)}"

    def configure_trigger(self, trigger_source, trigger_level, trigger_slope):
        """Configure edge trigger with specified parameters"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            channel = int(trigger_source.replace("CH", ""))
            slope = TRIGGER_SLOPE_MAP.get(trigger_slope, "POS")

            with self.io_lock:
                success = self.oscilloscope.configure_trigger(channel, trigger_level, slope)

            if success:
                return f"Trigger: {trigger_source} @ {trigger_level}V, {trigger_slope}"
            else:
                return "Trigger configuration failed"
        except Exception as e:
            return f"Error: {str(e)}"

    # Measurements - channel and math functions
    def get_all_measurements(self, source_str):
        """Get all available measurements for the specified source (CH1-CH4 or MATH1-MATH4)"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            source_upper = source_str.upper()
            # Parse source string (e.g., "CH1" or "MATH1")
            if source_upper.startswith("CH"):
                channel = int(source_upper[2:])
                with self.io_lock:
                    results = self.oscilloscope.get_all_measurements(channel)
                if results:
                    formatted_results = []
                    for meas_type, value in results.items():
                        formatted_results.append(f"{meas_type}: {format_measurement_value(meas_type, value)}")
                    return "\n".join(formatted_results)
                else:
                    return f"No measurements available for {source_str}"
            elif source_upper.startswith("MATH"):
                func_num = int(source_upper[4:])
                if not (1 <= func_num <= 4):
                    return "Math function number must be between 1 and 4"
                
                # Get all available measurements for the math function
                results = {}
                for meas_type in self.measurement_types:
                    try:
                        with self.io_lock:
                            value = self.oscilloscope.measure_math_single(func_num, meas_type)
                        if value is not None:
                            results[meas_type] = value
                    except Exception:
                        continue
                
                if results:
                    formatted_results = [f"Measurements for {source_upper}:"]
                    for meas_type, value in results.items():
                        formatted_results.append(f"{meas_type}: {format_measurement_value(meas_type, value)}")
                    return "\n".join(formatted_results)
                else:
                    return f"No measurements available for {source_str}"
            else:
                return f"Unsupported source: {source_str}. Use CH1-CH4 or MATH1-MATH4"
        except Exception as e:
            return f"Error getting measurements: {str(e)}"

    def perform_measurement(self, source_str, measurement_type):
        """Perform single measurement on specified channel or math function"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            # Parse source string (e.g., "CH1" or "MATH1")
            if source_str.upper().startswith("CH"):
                channel = int(source_str[2:])
                with self.io_lock:
                    result = self.oscilloscope.measure_single(channel, measurement_type)
                if result is not None:
                    return f"{source_str.upper()} {measurement_type}: {format_measurement_value(measurement_type, result)}"
                else:
                    return f"Failed to measure {measurement_type} on {source_str}"
            elif source_str.upper().startswith("MATH"):
                func_num = int(source_str[4:])
                with self.io_lock:
                    result = self.oscilloscope.measure_math_single(func_num, measurement_type)
                if result is not None:
                    return f"MATH{func_num} {measurement_type}: {format_measurement_value(measurement_type, result)}"
                else:
                    return f"Failed to measure {measurement_type} on {source_str}"
            else:
                return f"Invalid source: {source_str}"
        except Exception as e:
            return f"Error: {str(e)}"

    # Advanced trigger modes
    def set_glitch_trigger(self, source_channel, glitch_level, glitch_polarity, glitch_width):
        """Configure glitch (spike) trigger mode"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            channel = int(source_channel.replace("CH", ""))
            width_seconds = glitch_width * 1e-9

            with self.io_lock:
                success = self.oscilloscope.set_glitch_trigger(
                    channel=channel,
                    level=glitch_level,
                    polarity=glitch_polarity,
                    width=width_seconds
                )

            if success:
                return f"Glitch trigger: {source_channel}, Level={glitch_level}V, Width={glitch_width}ns, Polarity={glitch_polarity}"
            else:
                return "Glitch trigger configuration failed"
        except Exception as e:
            return f"Error: {str(e)}"

    def set_pulse_trigger(self, source_channel, pulse_level, pulse_width, pulse_polarity):
        """Configure pulse width trigger mode"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            channel = int(source_channel.replace("CH", ""))
            width_seconds = pulse_width * 1e-9

            with self.io_lock:
                success = self.oscilloscope.set_pulse_trigger(
                    channel=channel,
                    level=pulse_level,
                    width=width_seconds,
                    polarity=pulse_polarity
                )

            if success:
                return f"Pulse trigger: {source_channel}, Level={pulse_level}V, Width={pulse_width}ns, Polarity={pulse_polarity}"
            else:
                return "Pulse trigger configuration failed"
        except Exception as e:
            return f"Error: {str(e)}"

    def set_trigger_sweep_mode(self, sweep_mode):
        """Set trigger sweep behavior"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                success = self.oscilloscope.set_trigger_sweep(sweep_mode)

            if success:
                return f"Trigger sweep mode: {sweep_mode}"
            else:
                return "Failed to set trigger sweep mode"
        except Exception as e:
            return f"Error: {str(e)}"

    def set_trigger_holdoff(self, holdoff_nanoseconds):
        """Set trigger holdoff time"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            holdoff_seconds = holdoff_nanoseconds * 1e-9

            with self.io_lock:
                success = self.oscilloscope.set_trigger_holdoff(holdoff_seconds)

            if success:
                return f"Trigger holdoff: {holdoff_nanoseconds}ns"
            else:
                return "Failed to set trigger holdoff"
        except Exception as e:
            return f"Error: {str(e)}"

    # Acquisition control
    def set_acquisition_mode(self, mode_type):
        """Set oscilloscope acquisition mode"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                success = self.oscilloscope.set_acquire_mode(mode_type)

            if success:
                return f"Acquisition mode: {mode_type}"
            else:
                return "Failed to set acquisition mode"
        except Exception as e:
            return f"Error: {str(e)}"

    def set_acquisition_type(self, acq_type):
        """Set oscilloscope acquisition type"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                success = self.oscilloscope.set_acquire_type(acq_type)

            if success:
                return f"Acquisition type: {acq_type}"
            else:
                return "Failed to set acquisition type"
        except Exception as e:
            return f"Error: {str(e)}"

    def set_acquisition_count(self, average_count):
        """Set number of acquisitions to average"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            if not (2 <= average_count <= 65536):
                return f"Error: Count must be 2-65536, got {average_count}"

            with self.io_lock:
                success = self.oscilloscope.set_acquire_count(average_count)

            if success:
                return f"Acquisition count: {average_count} averages"
            else:
                return "Failed to set acquisition count"
        except Exception as e:
            return f"Error: {str(e)}"

    def query_acquisition_info(self):
        """Query and display current acquisition parameters"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            info_lines = []

            with self.io_lock:
                mode = self.oscilloscope.get_acquire_mode()
                acq_type = self.oscilloscope.get_acquire_type()
                count = self.oscilloscope.get_acquire_count()
                sample_rate = self.oscilloscope.get_sample_rate()
                points = self.oscilloscope.get_acquire_points()

            if mode:
                info_lines.append(f"Mode: {mode}")
            if acq_type:
                info_lines.append(f"Type: {acq_type}")
            if count:
                info_lines.append(f"Count: {count}")
            if sample_rate:
                info_lines.append(f"Sample Rate: {format_si_value(sample_rate, 'freq')}")
            if points:
                info_lines.append(f"Acquired Points: {points}")

            return "\n".join(info_lines) if info_lines else "No acquisition info available"
        except Exception as e:
            return f"Error: {str(e)}"

    # Marker/cursor operations
    def set_marker_positions(self, marker_num, x_position, y_position):
        """Set marker (cursor) X and Y positions"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            if marker_num not in [1, 2]:
                return "Error: Marker must be 1 or 2"

            with self.io_lock:
                x_success = self.oscilloscope.set_marker_x_position(marker_num, x_position)
                y_success = self.oscilloscope.set_marker_y_position(marker_num, y_position)

            if x_success and y_success:
                x_fmt = format_si_value(x_position, "time")
                y_fmt = format_si_value(y_position, "volt")
                return f"Marker {marker_num}: X={x_fmt}, Y={y_fmt}"
            else:
                return "Failed to set marker positions"
        except Exception as e:
            return f"Error: {str(e)}"

    def get_marker_deltas(self):
        """Query time and voltage differences between markers"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                x_delta = self.oscilloscope.get_marker_x_delta()
                y_delta = self.oscilloscope.get_marker_y_delta()

            result_lines = []

            if x_delta is not None:
                x_fmt = format_si_value(x_delta, "time")
                if x_delta > 0:
                    freq = 1.0 / x_delta
                    freq_fmt = format_si_value(freq, "freq")
                    result_lines.append(f"X Delta (Time): {x_fmt}")
                    result_lines.append(f"Derived Frequency: {freq_fmt}")
                else:
                    result_lines.append(f"X Delta (Time): {x_fmt}")

            if y_delta is not None:
                y_fmt = format_si_value(y_delta, "volt")
                result_lines.append(f"Y Delta (Voltage): {y_fmt}")

            return "\n".join(result_lines) if result_lines else "No marker data available"
        except Exception as e:
            return f"Error: {str(e)}"

    def set_marker_mode(self, marker_mode):
        """Set marker/cursor operational mode"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                success = self.oscilloscope.set_marker_mode(marker_mode)

            if success:
                return f"Marker mode: {marker_mode}"
            else:
                return "Failed to set marker mode"
        except Exception as e:
            return f"Error: {str(e)}"

    # Math functions
    def configure_math_operation(self, func_num, operation, source1_ch, source2_ch=None):
        """Configure math function for waveform processing"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            if func_num not in [1, 2, 3, 4]:
                return "Error: Function number must be 1-4"

            with self.io_lock:
                success = self.oscilloscope.set_math_function(
                    function_num=func_num,
                    operation=operation,
                    source1=source1_ch,
                    source2=source2_ch
                )

            if success:
                return f"Math function {func_num}: {operation} configured"
            else:
                return f"Failed to configure math function {func_num}"
        except Exception as e:
            return f"Error: {str(e)}"

    def toggle_math_display(self, func_num, show):
        """Show or hide math function on display"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            if func_num not in [1, 2, 3, 4]:
                return "Error: Function number must be 1-4"

            with self.io_lock:
                success = self.oscilloscope.set_math_display(func_num, show)

            if success:
                state = "shown" if show else "hidden"
                return f"Math function {func_num}: {state}"
            else:
                return f"Failed to toggle math function {func_num}"
        except Exception as e:
            return f"Error: {str(e)}"

    def set_math_scale(self, func_num, scale_value):
        """Set vertical scale for math function result"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            if func_num not in [1, 2, 3, 4]:
                return "Error: Function number must be 1-4"

            with self.io_lock:
                # The oscilloscope's set_math_scale will handle the *10 conversion
                success = self.oscilloscope.set_math_scale(func_num, scale_value)

            if success:
                return f"Math function {func_num} scale: {scale_value} V/div"
            else:
                return f"Failed to set math function {func_num} scale"
        except Exception as e:
            return f"Error: {str(e)}"

    # Setup management
    def save_instrument_setup(self, setup_name):
        """Save complete instrument configuration to internal memory"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            if not setup_name.endswith('.stp'):
                setup_name += '.stp'

            with self.io_lock:
                success = self.oscilloscope.save_setup(setup_name)

            if success:
                return f"Setup saved: {setup_name}"
            else:
                return "Failed to save setup"
        except Exception as e:
            return f"Error: {str(e)}"

    def recall_instrument_setup(self, setup_name):
        """Restore previously saved instrument configuration"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            if not setup_name.endswith('.stp'):
                setup_name += '.stp'

            with self.io_lock:
                success = self.oscilloscope.recall_setup(setup_name)

            if success:
                return f"Setup recalled: {setup_name}"
            else:
                return "Failed to recall setup"
        except Exception as e:
            return f"Error: {str(e)}"

    def save_waveform_to_memory(self, channel, waveform_name):
        """Save waveform data to internal oscilloscope memory"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            if channel not in [1, 2, 3, 4]:
                return "Error: Channel must be 1-4"

            with self.io_lock:
                success = self.oscilloscope.save_waveform(channel, waveform_name)

            if success:
                return f"Waveform saved: CH{channel} -> {waveform_name}"
            else:
                return "Failed to save waveform"
        except Exception as e:
            return f"Error: {str(e)}"

    def recall_waveform_from_memory(self, waveform_name):
        """Restore waveform from internal oscilloscope memory"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                success = self.oscilloscope.recall_waveform(waveform_name)

            if success:
                return f"Waveform recalled: {waveform_name}"
            else:
                return "Failed to recall waveform"
        except Exception as e:
            return f"Error: {str(e)}"

    # Function generators
    def configure_wgen(self, generator, enable, waveform, frequency, amplitude, offset):
        """Configure function generator with specified parameters"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                success = self.oscilloscope.configure_function_generator(
                    generator=generator,
                    waveform=waveform,
                    frequency=frequency,
                    amplitude=amplitude,
                    offset=offset,
                    enable=enable
                )

            if success:
                return f"WGEN{generator}: {waveform}, {frequency}Hz, {amplitude}Vpp"
            else:
                return f"WGEN{generator} configuration failed"
        except Exception as e:
            return f"Error: {str(e)}"

    def get_wgen_configuration(self, generator):
        """Query and display function generator current configuration"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                config = self.oscilloscope.get_function_generator_config(generator)

            if config:
                lines = [
                    f"WGEN{generator} Configuration:",
                    f" Function: {config['function']}",
                    f" Frequency: {format_si_value(config['frequency'], 'freq')}",
                    f" Amplitude: {format_si_value(config['amplitude'], 'volt')}",
                    f" Offset: {format_si_value(config['offset'], 'volt')}",
                    f" Output: {config['output']}"
                ]
                return "\n".join(lines)
            else:
                return "Failed to query WGEN configuration"
        except Exception as e:
            return f"Error: {str(e)}"

    # Data acquisition
    def capture_screenshot(self):
        """Capture and save display screenshot to the configured save location"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            # Ensure the save directory exists
            screenshot_dir = Path(self.save_locations['screenshots'])
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate a timestamp and filename
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"scope_screenshot_{timestamp}.png"
            
            # Create the full path for the screenshot
            screenshot_path = screenshot_dir / filename
            
            # Get the screenshot data directly
            if not hasattr(self.oscilloscope, '_scpi_wrapper'):
                return "Error: Oscilloscope SCPI interface not available"
                
            # Get the screenshot data
            try:
                image_data = self.oscilloscope._scpi_wrapper.query_binary_values(
                    ":DISPlay:DATA? PNG",
                    datatype='B'
                )
                
                if image_data:
                    # Save the screenshot to the desired location
                    with open(screenshot_path, 'wb') as f:
                        f.write(bytes(image_data))
                    return f"Screenshot saved: {screenshot_path}"
                else:
                    return "Screenshot capture failed: No data received"
                    
            except Exception as e:
                return f"Error capturing screenshot: {str(e)}"

        except Exception as e:
            return f"Error: {str(e)}"

    def acquire_data(self, ch1, ch2, ch3, ch4, math1, math2, math3, math4):
        """Acquire waveform data from selected channels and math functions"""
        if not self.data_acquisition:
            return "Error: Not initialized. Connect first."

        selected_channels = []
        if ch1:
            selected_channels.append(('CH', 1))
        if ch2:
            selected_channels.append(('CH', 2))
        if ch3:
            selected_channels.append(('CH', 3))
        if ch4:
            selected_channels.append(('CH', 4))
        if math1:
            selected_channels.append(('MATH', 1))
        if math2:
            selected_channels.append(('MATH', 2))
        if math3:
            selected_channels.append(('MATH', 3))
        if math4:
            selected_channels.append(('MATH', 4))

        if not selected_channels:
            return "Error: No channels/math functions selected"

        try:
            all_channel_data = {}
            for source_type, number in selected_channels:
                if source_type == 'CH':
                    data = self.data_acquisition.acquire_waveform_data(number)
                    if data:
                        all_channel_data[f'CH{number}'] = data
                else:  # MATH
                    data = self.data_acquisition.acquire_math_function_data(number)
                    if data:
                        all_channel_data[f'MATH{number}'] = data

            if all_channel_data:
                self.last_acquired_data = all_channel_data
                total_points = sum(ch_data['points_count'] for ch_data in all_channel_data.values())
                return f"Acquired: {len(all_channel_data)} sources, {total_points} total points"
            else:
                return "Acquisition failed"
        except Exception as e:
            return f"Error: {str(e)}"

    def export_csv(self, save_path: str):
        """Export acquired waveform data to CSV files at user-specified location

        Args:
            save_path: Directory path where files should be saved

        Returns:
            Status message
        """
        if not self.last_acquired_data:
            return "Error: No data available"
        if not self.data_acquisition:
            return "Error: Not initialized"

        if not save_path or save_path.strip() == "":
            return "Please select a save location using the Browse button"

        # Verify path exists and is a directory
        save_dir = Path(save_path)
        if not save_dir.exists():
            return f"Error: Directory does not exist: {save_path}"
        if not save_dir.is_dir():
            return f"Error: Path is not a directory: {save_path}"

        try:
            exported_files = []
            if isinstance(self.last_acquired_data, dict):
                for source_key, data in self.last_acquired_data.items():
                    filename = self.data_acquisition.export_to_csv(data, custom_path=save_path)
                    if filename:
                        exported_files.append(Path(filename).name)

            if exported_files:
                return f"✓ Exported {len(exported_files)} file(s) successfully to:\n{save_path}\n\nFiles: {', '.join(exported_files)}"
            else:
                return "Export failed"
        except Exception as e:
            return f"Error: {str(e)}"

    def generate_plot(self, plot_title):
        """Generate waveform plot with measurements"""
        if not self.last_acquired_data:
            return "Error: No data available"
        if not self.data_acquisition:
            return "Error: Not initialized"

        try:
            custom_title = plot_title.strip() or None
            plot_files = []
            if isinstance(self.last_acquired_data, dict):
                for source_key, data in self.last_acquired_data.items():
                    if custom_title:
                        source_label = "Math" if data['is_math'] else "Channel"
                        channel_title = f"{custom_title} - {source_label} {data['channel']}"
                    else:
                        channel_title = None

                    filename = self.data_acquisition.generate_waveform_plot(
                        data, custom_path=self.save_locations['graphs'], plot_title=channel_title)
                    if filename:
                        plot_files.append(Path(filename).name)

            if plot_files:
                return f"Generated: {', '.join(plot_files)}"
            else:
                return "Failed"
        except Exception as e:
            return f"Error: {str(e)}"

    def perform_autoscale(self):
        """Execute automatic vertical and horizontal scaling"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"

        try:
            with self.io_lock:
                success = self.oscilloscope.autoscale()

            if success:
                return "Autoscale completed"
            else:
                return "Autoscale failed"
        except Exception as e:
            return f"Error: {str(e)}"

    def run_full_automation(self, ch1, ch2, ch3, ch4, math1, math2, math3, math4, plot_title):
        """Execute complete acquisition, export, and analysis workflow"""
        if not self.oscilloscope or not self.oscilloscope.is_connected:
            return "Error: Not connected"
        if not self.data_acquisition:
            return "Error: Not initialized"

        selected_channels = []
        if ch1:
            selected_channels.append(('CH', 1))
        if ch2:
            selected_channels.append(('CH', 2))
        if ch3:
            selected_channels.append(('CH', 3))
        if ch4:
            selected_channels.append(('CH', 4))
        if math1:
            selected_channels.append(('MATH', 1))
        if math2:
            selected_channels.append(('MATH', 2))
        if math3:
            selected_channels.append(('MATH', 3))
        if math4:
            selected_channels.append(('MATH', 4))

        if not selected_channels:
            return "Error: No channels/math functions selected"

        try:
            results = []
            results.append("Step 1/4: Screenshot...")
            with self.io_lock:
                screenshot_dir = Path(self.save_locations['screenshots'])
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                filename = f"scope_screenshot_{timestamp}.png"
                screenshot_file = self.oscilloscope.capture_screenshot(
                    filename=filename,
                    image_format="PNG"
                )

            if screenshot_file:
                results.append(f"✓ Screenshot saved")

            results.append("Step 2/4: Acquiring data...")
            all_channel_data = {}
            for source_type, number in selected_channels:
                if source_type == 'CH':
                    data = self.data_acquisition.acquire_waveform_data(number)
                    if data:
                        all_channel_data[f'CH{number}'] = data
                        results.append(f" CH{number}: {data['points_count']} points")
                else:  # MATH
                    data = self.data_acquisition.acquire_math_function_data(number)
                    if data:
                        all_channel_data[f'MATH{number}'] = data
                        results.append(f" MATH{number}: {data['points_count']} points")

            if not all_channel_data:
                return "Error: Data acquisition failed"

            results.append("Step 3/4: Exporting CSV...")
            csv_files = []
            for source_key, data in all_channel_data.items():
                csv_file = self.data_acquisition.export_to_csv(data, custom_path=self.save_locations['data'])
                if csv_file:
                    csv_files.append(Path(csv_file).name)

            if csv_files:
                results.append(f" ✓ {len(csv_files)} files exported")

            results.append("Step 4/4: Generating plots...")
            custom_title = plot_title.strip() or None
            plot_files = []
            for source_key, data in all_channel_data.items():
                if custom_title:
                    source_label = "Math" if data['is_math'] else "Channel"
                    channel_title = f"{custom_title} - {source_label} {data['channel']}"
                else:
                    channel_title = None

                plot_file = self.data_acquisition.generate_waveform_plot(
                    data, custom_path=self.save_locations['graphs'], plot_title=channel_title)
                if plot_file:
                    plot_files.append(Path(plot_file).name)

            if plot_files:
                results.append(f" ✓ {len(plot_files)} plots generated")

            self.last_acquired_data = all_channel_data
            results.append("\n✓ Full automation completed!")
            return "\n".join(results)
        except Exception as e:
            return f"Automation error: {str(e)}"

    def browse_folder(self, current_path, folder_type="folder"):
        """Open file dialog for folder selection"""
        try:
            root = tk.Tk()
            root.withdraw()
            root.lift()
            root.attributes('-topmost', True)
            initial_dir = current_path if Path(current_path).exists() else str(Path.cwd())
            selected_path = filedialog.askdirectory(
                title=f"Select {folder_type} Directory",
                initialdir=initial_dir
            )
            root.destroy()
            if selected_path:
                return selected_path
            else:
                return current_path
        except Exception as e:
            print(f"Browse error: {e}")
            return current_path

    def create_interface(self):
        """
        Create the Gradio interface for oscilloscope control.
        This method is now handled by the unified interface.
        """
        # This method is now called from our unified interface
        # Rather than creating and returning a Gradio interface,
        # we'll just return None to indicate this is handled elsewhere
        return None


# ============================================================================
# SECTION 6: UNIFIED CONTROLLER CLASS
# ============================================================================
class UnifiedInstrumentControl:
    """
    Unified interface for controlling multiple lab instruments.
    
    This class integrates multiple instrument controllers into a single
    Gradio interface with tabs for each instrument:
    1. Keithley DMM6500 Digital Multimeter
    2. Keithley 2230 Power Supply
    3. Keysight DSOX6004A Oscilloscope
    
    All features from the original interfaces are preserved, while providing
    a clean, unified experience for the user.
    """
    
    def __init__(self):
        """Initialize the unified controller."""
        self.setup_logging()
        
        # Initialize controllers for each instrument
        self.dmm_controller = DMM_GUI_Controller()
        self.psu_controller = PowerSupplyAutomationGradio()
        self.oscilloscope_controller = GradioOscilloscopeGUI()
        
        self._css = """
        .tab-nav {
            border-bottom: 2px solid #9c9cff;
            margin-bottom: 12px;
        }
        
        .tab-selected {
            background-color: #e0e0ff;
            font-weight: 600;
        }
        """
        
    def setup_logging(self):
        """Configure logging for the application."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('UnifiedInstrumentControl')
        
    def create_interface(self):
        """Create the unified Gradio interface with tabs for each instrument."""
        with gr.Blocks(title="DIGANTARA Unified Instrument Control", 
                      theme=gr.themes.Soft(primary_hue="indigo"), 
                      css=self._css) as interface:
            gr.Markdown("# DIGANTARA Unified Lab Instrument Control")
            gr.Markdown("Professional control interface for multiple lab instruments")
            
            with gr.Tabs():
                # DMM Tab
                with gr.Tab("Digital Multimeter (DMM6500)"):
                    self.create_dmm_interface()
                
                # Power Supply Tab
                with gr.Tab("Power Supply (2230)"):
                    self.create_psu_interface()
                
                # Oscilloscope Tab
                with gr.Tab("Oscilloscope (DSOX6004A)"):
                    self.create_oscilloscope_interface()
            
            gr.Markdown("---")
            gr.Markdown("**DIGANTARA Lab Automation System** | All instruments controlled from single interface")
            
        return interface
    
    def create_dmm_interface(self):
        """Create the Digital Multimeter interface tab"""
        # Connection Tab
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Instrument Connection")
                dmm_visa_address = gr.Textbox(
                    label="VISA Address",
                    value=self.dmm_controller.default_settings['visa_address'],
                    placeholder="USB0::0x05E6::0x6500::04561287::INSTR"
                )
                dmm_timeout_ms = gr.Number(
                    label="Timeout (ms)",
                    value=self.dmm_controller.default_settings['timeout_ms'],
                    minimum=1000,
                    maximum=60000
                )
                
                with gr.Row():
                    dmm_connect_btn = gr.Button("Connect", variant="primary")
                    dmm_disconnect_btn = gr.Button("Disconnect", variant="secondary")
                
                dmm_connection_status = gr.Textbox(
                    label="Connection Status",
                    interactive=False
                )
            
            with gr.Column(scale=1):
                gr.Markdown("### Instrument Status")
                dmm_status_connection = gr.Textbox(label="Connection", interactive=False)
                dmm_status_instrument = gr.Textbox(label="Instrument", interactive=False)
                dmm_status_errors = gr.Textbox(label="Errors", interactive=False)
                dmm_status_time = gr.Textbox(label="System Time", interactive=False)
                dmm_refresh_status_btn = gr.Button("Refresh Status")

        # Measurement Configuration
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Measurement Configuration")
                dmm_measurement_function = gr.Dropdown(
                    label="Measurement Function",
                    choices=[
                        "DC_VOLTAGE", "AC_VOLTAGE",
                        "DC_CURRENT", "AC_CURRENT",
                        "RESISTANCE_2W", "RESISTANCE_4W",
                        "CAPACITANCE", "FREQUENCY"
                    ],
                    value="DC_VOLTAGE"
                )
                
                dmm_measurement_range = gr.Number(
                    label="Range",
                    value=10.0,
                    minimum=0.001,
                    maximum=1000.0
                )
                
                dmm_resolution = gr.Number(
                    label="Resolution",
                    value=1e-6,
                    minimum=1e-9,
                    maximum=1e-3,
                    step=1e-9
                )
                
                dmm_nplc = gr.Dropdown(
                    label="NPLC (Integration Time)",
                    choices=[0.01, 0.02, 0.06, 0.2, 1.0, 2.0, 10.0],
                    value=1.0
                )
                
                dmm_auto_zero = gr.Checkbox(
                    label="Auto Zero",
                    value=True
                )
                
                with gr.Row():
                    dmm_single_measure_btn = gr.Button("Single Measurement", variant="primary")
                    dmm_clear_data_btn = gr.Button("Clear Data", variant="secondary")
            
            with gr.Column(scale=1):
                gr.Markdown("### Measurement Results")
                dmm_current_measurement = gr.Textbox(
                    label="Current Reading",
                    interactive=False,
                    lines=2
                )
                
                dmm_measurement_status = gr.Textbox(
                    label="Status",
                    interactive=False
                )
                
                gr.Markdown("### Continuous Measurements")
                dmm_measurement_interval = gr.Number(
                    label="Interval (seconds)",
                    value=1.0,
                    minimum=0.1,
                    maximum=60.0
                )
                
                with gr.Row():
                    dmm_start_continuous_btn = gr.Button("Start Continuous", variant="primary")
                    dmm_stop_continuous_btn = gr.Button("Stop Continuous", variant="secondary")
                
                dmm_continuous_status = gr.Textbox(
                    label="Continuous Status",
                    interactive=False
                )

        # Statistics Tab
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Statistical Analysis")
                dmm_stats_points = gr.Number(
                    label="Number of Points",
                    value=100,
                    minimum=1,
                    maximum=1000
                )
                
                dmm_calculate_stats_btn = gr.Button("Calculate Statistics", variant="primary")
                
                dmm_stats_count = gr.Textbox(label="Count", interactive=False)
                dmm_stats_mean = gr.Textbox(label="Mean", interactive=False)
                dmm_stats_std = gr.Textbox(label="Standard Deviation", interactive=False)
                dmm_stats_min = gr.Textbox(label="Minimum", interactive=False)
                dmm_stats_max = gr.Textbox(label="Maximum", interactive=False)
            
            with gr.Column(scale=2):
                gr.Markdown("### Trend Plot")
                dmm_plot_points = gr.Number(
                    label="Points to Plot",
                    value=100,
                    minimum=10,
                    maximum=1000
                )
                dmm_update_plot_btn = gr.Button("Update Plot", variant="primary")
                dmm_trend_plot = gr.Plot()

        # Data Export Tab
        with gr.Row():
            with gr.Column():
                gr.Markdown("### Export Measurement Data")

                with gr.Row():
                    dmm_export_path = gr.Textbox(
                        label="Save Location",
                        placeholder="Click Browse to select folder...",
                        interactive=True,
                        scale=3
                    )
                    dmm_export_browse_btn = gr.Button("Browse", variant="secondary", scale=1)

                dmm_export_format = gr.Dropdown(
                    label="Export Format",
                    choices=["CSV", "JSON", "Excel"],
                    value="CSV"
                )

                dmm_export_btn = gr.Button("Export Data", variant="primary")
                dmm_export_status = gr.Textbox(
                    label="Export Status",
                    interactive=False
                )

                gr.Markdown("### Data Preview")
                dmm_data_preview = gr.Dataframe(
                    headers=["Timestamp", "Function", "Value", "Range", "Resolution"],
                    interactive=False
                )

                dmm_refresh_preview_btn = gr.Button("Refresh Preview")
        
        # Event handlers
        dmm_connect_btn.click(
            self.dmm_controller.connect_instrument,
            inputs=[dmm_visa_address, dmm_timeout_ms],
            outputs=[dmm_connection_status, gr.State()]
        )
        
        dmm_disconnect_btn.click(
            self.dmm_controller.disconnect_instrument,
            outputs=[dmm_connection_status]
        )
        
        dmm_refresh_status_btn.click(
            self.dmm_controller.get_instrument_status,
            outputs=[dmm_status_connection, dmm_status_instrument, dmm_status_errors, dmm_status_time]
        )
        
        dmm_single_measure_btn.click(
            self.dmm_controller.single_measurement,
            inputs=[dmm_measurement_function, dmm_measurement_range, dmm_resolution, dmm_nplc, dmm_auto_zero],
            outputs=[dmm_current_measurement, dmm_measurement_status]
        )
        
        dmm_start_continuous_btn.click(
            self.dmm_controller.start_continuous_measurement,
            inputs=[dmm_measurement_function, dmm_measurement_range, dmm_resolution, dmm_nplc, dmm_auto_zero, dmm_measurement_interval],
            outputs=[dmm_continuous_status]
        )
        
        dmm_stop_continuous_btn.click(
            self.dmm_controller.stop_continuous_measurement,
            outputs=[dmm_continuous_status]
        )
        
        dmm_calculate_stats_btn.click(
            self.dmm_controller.get_statistics,
            inputs=[dmm_stats_points],
            outputs=[dmm_stats_count, dmm_stats_mean, dmm_stats_std, dmm_stats_min, dmm_stats_max]
        )
        
        dmm_update_plot_btn.click(
            lambda points: self.dmm_controller.create_trend_plot(points),
            inputs=[dmm_plot_points],
            outputs=[dmm_trend_plot]
        )

        # Browse button for DMM export
        def dmm_browse_folder():
            """Open folder browser dialog for DMM export"""
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            folder_path = filedialog.askdirectory(title="Select Save Location for DMM Data")
            root.destroy()
            return folder_path if folder_path else ""

        dmm_export_browse_btn.click(
            fn=dmm_browse_folder,
            outputs=[dmm_export_path]
        )

        dmm_export_btn.click(
            self.dmm_controller.export_data,
            inputs=[dmm_export_path, dmm_export_format],
            outputs=[dmm_export_status]
        )
        
        dmm_clear_data_btn.click(
            self.dmm_controller.clear_data,
            outputs=[dmm_measurement_status]
        )
        
        def update_data_preview():
            if self.dmm_controller.measurement_data:
                recent_data = self.dmm_controller.measurement_data[-20:]  # Show last 20 points
                df_data = []
                for point in recent_data:
                    df_data.append([
                        point['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                        point['function'],
                        f"{point['value']:.6e}",
                        point['range'],
                        f"{point['resolution']:.2e}"
                    ])
                return df_data
            return []
        
        dmm_refresh_preview_btn.click(
            update_data_preview,
            outputs=[dmm_data_preview]
        )
    
    def create_psu_interface(self):
        """Create the Power Supply interface tab"""
        gr.Markdown("### Connection Settings")
        with gr.Group():
            with gr.Row():
                psu_visa_addr = gr.Textbox(
                    label="VISA Address",
                    value="USB0::0x05E6::0x2230::805224014806770001::INSTR",
                    lines=1
                )
            
            with gr.Row():
                psu_conn_btn = gr.Button("Connect", variant="primary", size="lg")
                psu_disc_btn = gr.Button("Disconnect", variant="stop", size="lg")
                psu_test_btn = gr.Button("Test Connection", variant="secondary", size="lg")
                psu_emerg_btn = gr.Button("EMERGENCY STOP", variant="stop", size="lg")
            
            with gr.Row():
                psu_conn_status = gr.Textbox(label="Status", value="Disconnected", interactive=False)
            
            psu_info = gr.Textbox(label="Instrument Info", lines=2, interactive=False)
        
        # Channel Controls
        gr.Markdown("### Channel Controls")
        with gr.Group():
            psu_channel_outputs = {}

            # Channel specifications: (max_voltage, max_current, default_ovp)
            channel_specs = {
                1: (30, 3.0, 30),  # Channel 1: 0-30V, 0-3A
                2: (30, 3.0, 30),  # Channel 2: 0-30V, 0-3A
                3: (5, 3.0, 6)     # Channel 3: 0-5V, 0-3A (limited voltage)
            }

            with gr.Tabs():
                for ch in range(1, 4):
                    max_volt, max_curr, default_ovp = channel_specs[ch]

                    with gr.TabItem(label=f"Channel {ch}"):
                        with gr.Row():
                            psu_volt_slider = gr.Slider(0, max_volt, value=0, label="Voltage (V)", step=0.1)
                            psu_curr_limit = gr.Slider(0.001, max_curr, value=0.1, label="Current Limit (A)", step=0.001)
                            psu_ovp_level = gr.Slider(1, max_volt + 5, value=default_ovp, label="OVP (V)", step=0.5)

                        with gr.Row():
                            psu_conf_btn = gr.Button(f"Configure Ch{ch}", variant="secondary")
                            psu_enable_btn = gr.Button(f"Enable Output", variant="primary")
                            psu_disable_btn = gr.Button(f"Disable Output", variant="stop")
                            psu_meas_btn = gr.Button(f"Measure", variant="secondary")

                        with gr.Row():
                            psu_volt_display = gr.Textbox(label="Measured Voltage", value="0.000 V", interactive=False)
                            psu_curr_display = gr.Textbox(label="Measured Current", value="0.000 A", interactive=False)
                            psu_power_display = gr.Textbox(label="Measured Power", value="0.000 W", interactive=False)

                        psu_ch_status = gr.Textbox(label="Status", value="OFF", interactive=False)

                        psu_channel_outputs[ch] = {
                            "voltage": psu_volt_slider,
                            "current_limit": psu_curr_limit,
                            "ovp_level": psu_ovp_level,
                            "configure_btn": psu_conf_btn,
                            "enable_btn": psu_enable_btn,
                            "disable_btn": psu_disable_btn,
                            "measure_btn": psu_meas_btn,
                            "volt_display": psu_volt_display,
                            "curr_display": psu_curr_display,
                            "power_display": psu_power_display,
                            "status": psu_ch_status
                        }

                        psu_conf_btn.click(
                            fn=lambda v, cl, ov, ch=ch: self.psu_controller.configure_channel(ch, v, cl, ov),
                            inputs=[psu_volt_slider, psu_curr_limit, psu_ovp_level]
                        )

                        psu_enable_btn.click(
                            fn=lambda ch=ch: self.psu_controller.enable_channel_output(ch)
                        )

                        psu_disable_btn.click(
                            fn=lambda ch=ch: self.psu_controller.disable_channel_output(ch)
                        )

                        psu_meas_btn.click(
                            fn=lambda ch=ch: self.psu_controller.measure_channel_output(ch),
                            outputs=[psu_volt_display, psu_curr_display, psu_power_display]
                        )
        
        # Global Operations
        gr.Markdown("### Global Operations")
        with gr.Group():
            with gr.Row():
                psu_get_info_btn = gr.Button("Get Instrument Info", variant="secondary")
                psu_measure_all_btn = gr.Button("Measure All Channels", variant="primary")
                psu_disable_all_btn = gr.Button("Disable All Outputs", variant="stop")
            
            psu_get_info_btn.click(fn=self.psu_controller.get_instrument_info)
            psu_measure_all_btn.click(
                fn=self.psu_controller.measure_all_channels,
                outputs=[
                    psu_channel_outputs[1]["volt_display"],
                    psu_channel_outputs[1]["curr_display"],
                    psu_channel_outputs[1]["power_display"],
                    psu_channel_outputs[2]["volt_display"],
                    psu_channel_outputs[2]["curr_display"],
                    psu_channel_outputs[2]["power_display"],
                    psu_channel_outputs[3]["volt_display"],
                    psu_channel_outputs[3]["curr_display"],
                    psu_channel_outputs[3]["power_display"]
                ]
            )
            psu_disable_all_btn.click(fn=self.psu_controller.disable_all_outputs)
        
        # Data Logging
        gr.Markdown("### Data Logging & Export")
        with gr.Group():
            with gr.Row():
                psu_auto_measure_cb = gr.Checkbox(label="Enable Auto-Measurement", value=False)
                psu_measure_interval = gr.Slider(0.5, 60, value=2.0, label="Interval (seconds)", step=0.5)

            with gr.Row():
                psu_export_path = gr.Textbox(
                    label="Save Location",
                    placeholder="Click Browse to select folder...",
                    interactive=True,
                    scale=3
                )
                psu_export_browse_btn = gr.Button("Browse", variant="secondary", scale=1)

            with gr.Row():
                psu_export_btn = gr.Button("Export to CSV", variant="primary")
                psu_clear_btn = gr.Button("Clear Data", variant="secondary")

            psu_export_status = gr.Textbox(
                label="Export Status",
                interactive=False
            )

            # Browse button handler
            def psu_browse_folder():
                """Open folder browser dialog for PSU export"""
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                folder_path = filedialog.askdirectory(title="Select Save Location for PSU Data")
                root.destroy()
                return folder_path if folder_path else ""

            psu_auto_measure_cb.change(fn=self.psu_controller.toggle_auto_measure, inputs=psu_auto_measure_cb)

            psu_export_browse_btn.click(
                fn=psu_browse_folder,
                outputs=[psu_export_path]
            )

            psu_export_btn.click(
                fn=self.psu_controller.export_measurement_data,
                inputs=[psu_export_path],
                outputs=[psu_export_status]
            )
            psu_clear_btn.click(fn=self.psu_controller.clear_measurement_data)

        # Voltage Waveform Generation
        gr.Markdown("### Voltage Waveform Generation")
        with gr.Group():
            gr.Markdown("Generate dynamic voltage patterns on selected channel (Sine, Square, Triangle, Ramp)")

            with gr.Row():
                psu_waveform_channel = gr.Dropdown(
                    label="Target Channel",
                    choices=[1, 2, 3],
                    value=1
                )
                psu_waveform_type = gr.Dropdown(
                    label="Waveform Type",
                    choices=["Sine", "Square", "Triangle", "Ramp Up", "Ramp Down"],
                    value="Sine"
                )

            with gr.Row():
                psu_target_voltage = gr.Slider(
                    label="Target Voltage (V)",
                    minimum=0,
                    maximum=30,
                    value=3.0,
                    step=0.1
                )
                psu_cycles = gr.Number(
                    label="Number of Cycles",
                    value=3,
                    minimum=1,
                    maximum=100,
                    precision=0
                )

            with gr.Row():
                psu_points_per_cycle = gr.Number(
                    label="Points per Cycle",
                    value=50,
                    minimum=10,
                    maximum=200,
                    precision=0
                )
                psu_cycle_duration = gr.Number(
                    label="Cycle Duration (s)",
                    value=8.0,
                    minimum=0.1,
                    maximum=60.0
                )

            with gr.Row():
                psu_preview_waveform_btn = gr.Button("Preview Waveform", variant="secondary", size="lg")
                psu_start_waveform_btn = gr.Button("Start Waveform", variant="primary", size="lg")
                psu_stop_waveform_btn = gr.Button("Stop Waveform", variant="stop", size="lg")

            psu_waveform_status = gr.Textbox(
                label="Waveform Status",
                value="Ready - Configure parameters and click Preview or Start",
                interactive=False,
                lines=2
            )

            psu_waveform_plot = gr.Plot(label="Waveform Preview / Real-time Data")

            # Waveform event handlers
            def preview_waveform(waveform_type, target_v, cycles, points, duration):
                """Generate preview plot of waveform"""
                try:
                    import matplotlib.pyplot as plt

                    generator = self.psu_controller._WaveformGenerator(
                        waveform_type=waveform_type,
                        target_voltage=target_v,
                        cycles=int(cycles),
                        points_per_cycle=int(points),
                        cycle_duration=duration
                    )
                    profile = generator.generate()

                    times = [p[0] for p in profile]
                    voltages = [p[1] for p in profile]

                    fig, ax = plt.subplots(figsize=(12, 6))
                    ax.plot(times, voltages, 'b-', linewidth=2, label='Voltage Profile')
                    ax.set_xlabel('Time (s)', fontsize=12, fontweight='bold')
                    ax.set_ylabel('Voltage (V)', fontsize=12, fontweight='bold')
                    ax.set_title(f'{waveform_type} Waveform - {int(cycles)} Cycles ({len(profile)} points)',
                                fontsize=14, fontweight='bold')
                    ax.grid(True, alpha=0.3, linestyle='--')
                    ax.set_ylim([min(0, min(voltages) - 0.5), max(voltages) + 0.5])
                    ax.legend(loc='upper right')
                    plt.tight_layout()

                    return fig

                except Exception as e:
                    return None

            def start_waveform_generation(channel, waveform_type, target_v, cycles, points, duration):
                """Start waveform generation on selected channel"""
                try:
                    if not self.psu_controller.is_connected:
                        return "ERROR: Power supply not connected. Please connect first."

                    # Validate channel voltage limit
                    if channel == 3 and target_v > 5:
                        return "ERROR: Channel 3 limited to 5V maximum. Please reduce target voltage."

                    # Update ramping parameters
                    self.psu_controller.ramping_params.update({
                        'waveform': waveform_type,
                        'target_voltage': target_v,
                        'cycles': int(cycles),
                        'points_per_cycle': int(points),
                        'cycle_duration': duration,
                        'active_channel': channel
                    })

                    # Generate waveform profile
                    generator = self.psu_controller._WaveformGenerator(
                        waveform_type=waveform_type,
                        target_voltage=target_v,
                        cycles=int(cycles),
                        points_per_cycle=int(points),
                        cycle_duration=duration
                    )
                    self.psu_controller.ramping_profile = generator.generate()

                    # Start waveform execution in background thread
                    if self.psu_controller.ramping_thread and self.psu_controller.ramping_thread.is_alive():
                        return "ERROR: Waveform already running. Stop current waveform first."

                    self.psu_controller.ramping_active = True
                    self.psu_controller.ramping_thread = threading.Thread(
                        target=self.psu_controller.execute_waveform_ramping,
                        daemon=True
                    )
                    self.psu_controller.ramping_thread.start()

                    return f"Waveform STARTED on Channel {channel}: {waveform_type}, {len(self.psu_controller.ramping_profile)} points, {int(cycles)} cycles"

                except Exception as e:
                    return f"ERROR: {str(e)}"

            def stop_waveform_generation():
                """Stop active waveform generation"""
                try:
                    self.psu_controller.ramping_active = False
                    if self.psu_controller.ramping_thread:
                        self.psu_controller.ramping_thread.join(timeout=2.0)
                    return "Waveform generation STOPPED. Channel output disabled for safety."
                except Exception as e:
                    return f"ERROR stopping waveform: {str(e)}"

            psu_preview_waveform_btn.click(
                fn=preview_waveform,
                inputs=[
                    psu_waveform_type,
                    psu_target_voltage,
                    psu_cycles,
                    psu_points_per_cycle,
                    psu_cycle_duration
                ],
                outputs=[psu_waveform_plot]
            )

            psu_start_waveform_btn.click(
                fn=start_waveform_generation,
                inputs=[
                    psu_waveform_channel,
                    psu_waveform_type,
                    psu_target_voltage,
                    psu_cycles,
                    psu_points_per_cycle,
                    psu_cycle_duration
                ],
                outputs=[psu_waveform_status]
            )

            psu_stop_waveform_btn.click(
                fn=stop_waveform_generation,
                outputs=[psu_waveform_status]
            )

        # Status & Activity Log
        gr.Markdown("### Status & Activity Log")
        with gr.Group():
            psu_activity_log_display = gr.Textbox(
                label="Activity Log",
                value=self.psu_controller.activity_log,
                lines=15,
                interactive=False,
                max_lines=500
            )
        
        # Connection handlers
        def psu_handle_connect(visa_addr_val):
            """Handle connection button click"""
            self.psu_controller.connect_power_supply(visa_addr_val)
            # Wait for connection to complete (max 5 seconds)
            max_wait = 5.0
            waited = 0.0
            wait_step = 0.1
            while waited < max_wait:
                time.sleep(wait_step)
                waited += wait_step
                if self.psu_controller.is_connected:
                    break
            status = "Connected" if self.psu_controller.is_connected else "Disconnected"
            return status, self.psu_controller.activity_log
        
        def psu_handle_disconnect():
            """Handle disconnect button click"""
            self.psu_controller.disconnect_power_supply()
            return "Disconnected", self.psu_controller.activity_log
        
        def psu_handle_test():
            """Handle test connection button click"""
            result = self.psu_controller.test_connection()
            return result, self.psu_controller.activity_log
        
        def psu_handle_emergency():
            """Handle emergency stop button click"""
            result = self.psu_controller.emergency_stop()
            return result, self.psu_controller.activity_log
        
        # Register connection handlers
        psu_conn_btn.click(
            fn=psu_handle_connect,
            inputs=psu_visa_addr,
            outputs=[psu_conn_status, psu_activity_log_display]
        )
        
        psu_disc_btn.click(
            fn=psu_handle_disconnect,
            outputs=[psu_conn_status, psu_activity_log_display]
        )
        
        psu_test_btn.click(
            fn=psu_handle_test,
            outputs=[psu_conn_status, psu_activity_log_display]
        )
        
        psu_emerg_btn.click(
            fn=psu_handle_emergency,
            outputs=[psu_conn_status, psu_activity_log_display]
        )
    
    def create_oscilloscope_interface(self):
        """Create the Oscilloscope interface tab"""
        with gr.Tab("Connection"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Instrument Connection")
                    osc_visa_address = gr.Textbox(
                        label="VISA Address",
                        value="USB0::0x0957::0x1780::MY65220169::INSTR",
                        scale=3
                    )
                    osc_connect_btn = gr.Button("Connect", variant="primary", scale=1)
                    osc_disconnect_btn = gr.Button("Disconnect", variant="stop", scale=1)
                    osc_test_btn = gr.Button("Test", scale=1)
                
                    osc_connection_status = gr.Textbox(label="Status", value="Disconnected", interactive=False)
                    osc_instrument_info = gr.Textbox(label="Instrument Information", interactive=False)

        with gr.Tab("Channel Configuration"):
            gr.Markdown("### Channel Selection and Configuration")
            with gr.Row():
                osc_ch1_select = gr.Checkbox(label="Ch1", value=True)
                osc_ch2_select = gr.Checkbox(label="Ch2", value=False)
                osc_ch3_select = gr.Checkbox(label="Ch3", value=False)
                osc_ch4_select = gr.Checkbox(label="Ch4", value=False)
            
            with gr.Row():
                osc_v_scale = gr.Number(label="V/div", value=1.0)
                osc_v_offset = gr.Number(label="Offset (V)", value=0.0)
                osc_coupling = gr.Dropdown(
                    label="Coupling",
                    choices=["AC", "DC"],
                    value="DC"
                )
                osc_probe = gr.Dropdown(
                    label="Probe",
                    choices=[("1x", 1.0), ("10x", 10.0), ("100x", 100.0)],
                    value=1.0
                )
            
            osc_config_channel_btn = gr.Button("Configure Channels", variant="primary")
            osc_channel_status = gr.Textbox(label="Status", interactive=False)
            
            with gr.Row():
                osc_autoscale_btn = gr.Button("Autoscale", variant="primary")
                osc_system_status = gr.Textbox(label="Status", interactive=False, lines=4)

        with gr.Tab("Timebase & Trigger"):
            gr.Markdown("### Horizontal Timebase Configuration")
            with gr.Row():
                osc_time_scale = gr.Dropdown(
                    label="Time/div",
                    choices=self.oscilloscope_controller.timebase_scales,
                    value=10e-3
                )
                osc_timebase_btn = gr.Button("Apply Timebase", variant="primary")
            
            osc_timebase_status = gr.Textbox(label="Status", interactive=False)
            
            gr.Markdown("### Edge Trigger Configuration")
            with gr.Row():
                osc_trigger_source = gr.Dropdown(
                    label="Source",
                    choices=["CH1", "CH2", "CH3", "CH4"],
                    value="CH1"
                )
                osc_trigger_level = gr.Number(label="Level (V)", value=0.0)
                osc_trigger_slope = gr.Dropdown(
                    label="Slope",
                    choices=["Rising", "Falling", "Either"],
                    value="Rising"
                )
            
            osc_trigger_btn = gr.Button("Apply Trigger", variant="primary")
            osc_trigger_status = gr.Textbox(label="Status", interactive=False)

            gr.Markdown("---")
            gr.Markdown("### Trigger Sweep & Holdoff")
            with gr.Row():
                osc_sweep_mode = gr.Dropdown(
                    label="Sweep Mode",
                    choices=["AUTO", "NORMal", "TRIG"],
                    value="AUTO"
                )
                osc_sweep_btn = gr.Button("Apply Sweep", variant="primary")

            osc_sweep_status = gr.Textbox(label="Sweep Status", interactive=False)

            with gr.Row():
                osc_holdoff_time = gr.Number(label="Holdoff Time (ns)", value=100.0)
                osc_holdoff_btn = gr.Button("Apply Holdoff", variant="primary")

            osc_holdoff_status = gr.Textbox(label="Holdoff Status", interactive=False)

        # Acquisition Control Tab
        with gr.Tab("Acquisition Control"):
            gr.Markdown("### Acquisition Mode Configuration")
            with gr.Row():
                osc_acq_mode = gr.Dropdown(
                    label="Acquisition Mode",
                    choices=["RTIMe", "ETIMe", "SEGMented"],
                    value="RTIMe"
                )
                osc_acq_mode_btn = gr.Button("Apply Mode", variant="primary")

            osc_acq_mode_status = gr.Textbox(label="Status", interactive=False)

            gr.Markdown("### Acquisition Type Configuration")
            with gr.Row():
                osc_acq_type = gr.Dropdown(
                    label="Acquisition Type",
                    choices=["NORMal", "AVERage", "HRESolution", "PEAK"],
                    value="NORMal"
                )
                osc_acq_type_btn = gr.Button("Apply Type", variant="primary")

            osc_acq_type_status = gr.Textbox(label="Status", interactive=False)

            gr.Markdown("### Averaging Configuration")
            with gr.Row():
                osc_avg_count = gr.Slider(
                    label="Averaging Count",
                    minimum=2,
                    maximum=65536,
                    value=16,
                    step=1
                )
                osc_avg_btn = gr.Button("Apply Averaging", variant="primary")

            osc_avg_status = gr.Textbox(label="Status", interactive=False)

            gr.Markdown("### Acquisition Information")
            osc_info_btn = gr.Button("Query Acquisition Info", variant="secondary")
            osc_acq_info_display = gr.Textbox(label="Acquisition Info", interactive=False, lines=6)

        # Markers & Cursors Tab
        with gr.Tab("Markers & Cursors"):
            gr.Markdown("### Marker/Cursor Mode Configuration")
            with gr.Row():
                osc_marker_mode = gr.Dropdown(
                    label="Marker Mode",
                    choices=["OFF", "MEASurement", "MANual", "WAVeform"],
                    value="OFF"
                )
                osc_marker_mode_btn = gr.Button("Set Mode", variant="primary")

            osc_marker_mode_status = gr.Textbox(label="Status", interactive=False)

            gr.Markdown("### Marker Position Configuration")
            with gr.Row():
                osc_marker_num = gr.Dropdown(
                    label="Marker Number",
                    choices=[1, 2],
                    value=1
                )
                osc_marker_x = gr.Number(label="X Position (s)", value=0.0)
                osc_marker_y = gr.Number(label="Y Position (V)", value=0.0)

            osc_marker_set_btn = gr.Button("Set Marker Position", variant="primary")
            osc_marker_status = gr.Textbox(label="Status", interactive=False)

            gr.Markdown("### Marker Delta Measurements")
            osc_delta_btn = gr.Button("Get Delta Values", variant="primary")
            osc_delta_result = gr.Textbox(label="Delta Results", interactive=False, lines=4)

        # Math Functions Tab
        with gr.Tab("Math Functions"):
            gr.Markdown("### Math Function Configuration")
            with gr.Row():
                osc_math_func = gr.Dropdown(
                    label="Function Number",
                    choices=[1, 2, 3, 4],
                    value=1
                )
                osc_math_op = gr.Dropdown(
                    label="Operation",
                    choices=["ADD", "SUBTract", "MULTiply", "DIVide", "FFT"],
                    value="ADD"
                )

            with gr.Row():
                osc_math_src1 = gr.Dropdown(
                    label="Source 1",
                    choices=[1, 2, 3, 4],
                    value=1
                )
                osc_math_src2 = gr.Dropdown(
                    label="Source 2 (not used for FFT)",
                    choices=[1, 2, 3, 4],
                    value=2
                )

            osc_math_config_btn = gr.Button("Configure Math Function", variant="primary")
            osc_math_config_status = gr.Textbox(label="Status", interactive=False)

            gr.Markdown("### Math Function Display & Scale")
            with gr.Row():
                osc_math_show = gr.Checkbox(label="Show on Display", value=True)
                osc_math_scale_val = gr.Number(label="Vertical Scale (V/div)", value=1.0)

            with gr.Row():
                osc_math_display_btn = gr.Button("Toggle Display", variant="primary")
                osc_math_scale_btn = gr.Button("Set Scale", variant="primary")

            osc_math_display_status = gr.Textbox(label="Display Status", interactive=False)
            osc_math_scale_status = gr.Textbox(label="Scale Status", interactive=False)

        # Setup Management Tab
        with gr.Tab("Setup Management"):
            gr.Markdown("### Save/Recall Instrument Setup")
            with gr.Row():
                osc_setup_save_name = gr.Textbox(
                    label="Setup Name",
                    placeholder="my_setup.stp"
                )
                osc_setup_save_btn = gr.Button("Save Setup", variant="primary")

            osc_setup_save_status = gr.Textbox(label="Save Status", interactive=False)

            with gr.Row():
                osc_setup_recall_name = gr.Textbox(
                    label="Setup Name",
                    placeholder="my_setup.stp"
                )
                osc_setup_recall_btn = gr.Button("Recall Setup", variant="primary")

            osc_setup_recall_status = gr.Textbox(label="Recall Status", interactive=False)

            gr.Markdown("### Save/Recall Waveform to Memory")
            with gr.Row():
                osc_wf_save_ch = gr.Dropdown(
                    label="Channel",
                    choices=[1, 2, 3, 4],
                    value=1
                )
                osc_wf_save_name = gr.Textbox(
                    label="Waveform Name",
                    placeholder="my_waveform"
                )
                osc_wf_save_btn = gr.Button("Save Waveform", variant="primary")

            osc_wf_save_status = gr.Textbox(label="Save Status", interactive=False)

            with gr.Row():
                osc_wf_recall_name = gr.Textbox(
                    label="Waveform Name",
                    placeholder="my_waveform"
                )
                osc_wf_recall_btn = gr.Button("Recall Waveform", variant="primary")

            osc_wf_recall_status = gr.Textbox(label="Recall Status", interactive=False)

        # Function Generators Tab
        with gr.Tab("Function Generators"):
            gr.Markdown("### WGEN1 Configuration")
            with gr.Row():
                osc_wgen1_enable = gr.Checkbox(label="Enable WGEN1", value=False)
                osc_wgen1_waveform = gr.Dropdown(
                    label="Waveform",
                    choices=["SIN", "SQU", "RAMP", "PULS", "DC", "NOIS", "ARB", "SINC", "EXPR", "EXPF", "CARD", "GAUS"],
                    value="SIN"
                )

            with gr.Row():
                osc_wgen1_freq = gr.Number(label="Frequency (Hz)", value=1000)
                osc_wgen1_amp = gr.Number(label="Amplitude (Vpp)", value=1.0)
                osc_wgen1_offset = gr.Number(label="Offset (V)", value=0.0)

            with gr.Row():
                osc_wgen1_btn = gr.Button("Apply WGEN1", variant="primary")
                osc_wgen1_info_btn = gr.Button("Query WGEN1", variant="secondary")

            osc_wgen1_status = gr.Textbox(label="WGEN1 Status", interactive=False)

            gr.Markdown("---")
            gr.Markdown("### WGEN2 Configuration")
            with gr.Row():
                osc_wgen2_enable = gr.Checkbox(label="Enable WGEN2", value=False)
                osc_wgen2_waveform = gr.Dropdown(
                    label="Waveform",
                    choices=["SIN", "SQU", "RAMP", "PULS", "DC", "NOIS", "ARB", "SINC", "EXPR", "EXPF", "CARD", "GAUS"],
                    value="SIN"
                )

            with gr.Row():
                osc_wgen2_freq = gr.Number(label="Frequency (Hz)", value=1000)
                osc_wgen2_amp = gr.Number(label="Amplitude (Vpp)", value=1.0)
                osc_wgen2_offset = gr.Number(label="Offset (V)", value=0.0)

            with gr.Row():
                osc_wgen2_btn = gr.Button("Apply WGEN2", variant="primary")
                osc_wgen2_info_btn = gr.Button("Query WGEN2", variant="secondary")

            osc_wgen2_status = gr.Textbox(label="WGEN2 Status", interactive=False)

        # Measurements Tab
        with gr.Tab("Measurements"):
            gr.Markdown("### Single Measurement")
            with gr.Row():
                source_choices = [
                    ("Channel 1", "CH1"),
                    ("Channel 2", "CH2"),
                    ("Channel 3", "CH3"),
                    ("Channel 4", "CH4"),
                    ("Math 1", "MATH1"),
                    ("Math 2", "MATH2"),
                    ("Math 3", "MATH3"),
                    ("Math 4", "MATH4")
                ]
                osc_meas_source = gr.Dropdown(
                    label="Source",
                    choices=source_choices,
                    value="CH1"
                )
                
                measurement_choices = [
                    ("Frequency", "FREQ"),
                    ("Period", "PERiod"),
                    ("Peak-to-Peak", "VPP"),
                    ("Amplitude", "VAMP"),
                    ("Overshoot", "OVERshoot"),
                    ("Top", "VTOP"),
                    ("Base", "VBASe"),
                    ("Average", "VAVG"),
                    ("RMS", "VRMS"),
                    ("Maximum", "VMAX"),
                    ("Minimum", "VMIN"),
                    ("Rise Time", "RISE"),
                    ("Fall Time", "FALL"),
                    ("Duty Cycle", "DUTYcycle"),
                    ("Negative Duty Cycle", "NDUTy")
                ]
                
                osc_measurement_type = gr.Dropdown(
                    label="Measurement Type",
                    choices=measurement_choices,
                    value="FREQ"
                )
                
                osc_measure_btn = gr.Button("Measure", variant="primary")
                osc_all_measurements_btn = gr.Button("Show All", variant="primary")
            
                osc_measurement_result = gr.Textbox(label="Measurement Result", interactive=False)
                osc_all_measurements_result = gr.Textbox(
                    label="All Measurements",
                    interactive=False,
                    lines=10,
                    max_lines=20,
                    show_copy_button=True
                )

        # Advanced Triggers Tab
        with gr.Tab("Advanced Triggers"):
            gr.Markdown("### Glitch (Spike) Trigger")
            gr.Markdown("Detects signal violations - pulses narrower than threshold")
            with gr.Row():
                osc_glitch_source = gr.Dropdown(
                    label="Source",
                    choices=["CH1", "CH2", "CH3", "CH4"],
                    value="CH1"
                )
                osc_glitch_level = gr.Number(label="Level (V)", value=0.0)
                osc_glitch_polarity = gr.Dropdown(
                    label="Polarity",
                    choices=["POSitive", "NEGative"],
                    value="POSitive"
                )
                osc_glitch_width = gr.Number(label="Width (ns)", value=1.0)
            
            osc_glitch_btn = gr.Button("Set Glitch Trigger", variant="primary")
            osc_glitch_status = gr.Textbox(label="Status", interactive=False)
            
            gr.Markdown("---")
            gr.Markdown("### Pulse Width Trigger")
            gr.Markdown("Triggers on pulses with width above or below threshold")
            with gr.Row():
                osc_pulse_source = gr.Dropdown(
                    label="Source",
                    choices=["CH1", "CH2", "CH3", "CH4"],
                    value="CH1"
                )
                osc_pulse_level = gr.Number(label="Level (V)", value=0.0)
                osc_pulse_width = gr.Number(label="Width (ns)", value=10.0)
                osc_pulse_polarity = gr.Dropdown(
                    label="Polarity",
                    choices=["POSitive", "NEGative"],
                    value="POSitive"
                )
            
            osc_pulse_btn = gr.Button("Set Pulse Trigger", variant="primary")
            osc_pulse_status = gr.Textbox(label="Status", interactive=False)
        
        # Operations & File Management Tab
        with gr.Tab("Operations & File Management"):
            with gr.Column(variant="panel"):
                gr.Markdown("### File Save Locations")
                
                with gr.Row():
                    osc_data_path = gr.Textbox(
                        label="Data Directory",
                        value=self.oscilloscope_controller.save_locations['data'],
                        scale=4
                    )
                    osc_data_browse_btn = gr.Button("Browse", scale=1)
                
                with gr.Row():
                    osc_graphs_path = gr.Textbox(
                        label="Graphs Directory",
                        value=self.oscilloscope_controller.save_locations['graphs'],
                        scale=4
                    )
                    osc_graphs_browse_btn = gr.Button("Browse", scale=1)
                
                with gr.Row():
                    osc_screenshots_path = gr.Textbox(
                        label="Screenshots Directory",
                        value=self.oscilloscope_controller.save_locations['screenshots'],
                        scale=4
                    )
                    osc_screenshots_browse_btn = gr.Button("Browse", scale=1)
                
                with gr.Row():
                    osc_update_paths_btn = gr.Button("Update Paths", variant="primary")
                    osc_path_status = gr.Textbox(label="Path Status", interactive=False, scale=4)
            
            # Data Acquisition and Export section
            gr.Markdown("### Data Acquisition and Export")

            with gr.Row():
                osc_op_ch1 = gr.Checkbox(label="Ch1", value=True)
                osc_op_ch2 = gr.Checkbox(label="Ch2", value=False)
                osc_op_ch3 = gr.Checkbox(label="Ch3", value=False)
                osc_op_ch4 = gr.Checkbox(label="Ch4", value=False)

            with gr.Row():
                osc_op_math1 = gr.Checkbox(label="Math1", value=False)
                osc_op_math2 = gr.Checkbox(label="Math2", value=False)
                osc_op_math3 = gr.Checkbox(label="Math3", value=False)
                osc_op_math4 = gr.Checkbox(label="Math4", value=False)

            with gr.Row():
                osc_export_path = gr.Textbox(
                    label="Export Save Location",
                    placeholder="Click Browse to select folder...",
                    interactive=True,
                    scale=3
                )
                osc_export_browse_btn = gr.Button("Browse", variant="secondary", scale=1)

            osc_plot_title_input = gr.Textbox(
                label="Plot Title (optional)",
                placeholder="Enter custom plot title"
            )

            with gr.Row():
                osc_screenshot_btn = gr.Button("Capture Screenshot", variant="secondary")
                osc_acquire_btn = gr.Button("Acquire Data", variant="primary")
                osc_export_btn = gr.Button("Export CSV", variant="secondary")
                osc_plot_btn = gr.Button("Generate Plot", variant="secondary")

            with gr.Row():
                osc_full_auto_btn = gr.Button("Full Automation", variant="primary", scale=2)

            osc_operation_status = gr.Textbox(label="Operation Status", interactive=False, lines=10)
        
        # Connect UI events to controller methods
        osc_connect_btn.click(
            fn=self.oscilloscope_controller.connect_oscilloscope,
            inputs=[osc_visa_address],
            outputs=[osc_instrument_info, osc_connection_status]
        )
        
        osc_disconnect_btn.click(
            fn=self.oscilloscope_controller.disconnect_oscilloscope,
            inputs=[],
            outputs=[osc_instrument_info, osc_connection_status]
        )
        
        osc_test_btn.click(
            fn=self.oscilloscope_controller.test_connection,
            inputs=[],
            outputs=[osc_instrument_info]
        )
        
        osc_config_channel_btn.click(
            fn=self.oscilloscope_controller.configure_channel,
            inputs=[osc_ch1_select, osc_ch2_select, osc_ch3_select, osc_ch4_select, osc_v_scale, osc_v_offset, osc_coupling, osc_probe],
            outputs=[osc_channel_status]
        )
        
        osc_autoscale_btn.click(
            fn=self.oscilloscope_controller.perform_autoscale,
            inputs=[],
            outputs=[osc_system_status]
        )
        
        osc_timebase_btn.click(
            fn=self.oscilloscope_controller.configure_timebase,
            inputs=[osc_time_scale],
            outputs=[osc_timebase_status]
        )
        
        osc_trigger_btn.click(
            fn=self.oscilloscope_controller.configure_trigger,
            inputs=[osc_trigger_source, osc_trigger_level, osc_trigger_slope],
            outputs=[osc_trigger_status]
        )
        
        osc_measure_btn.click(
            fn=self.oscilloscope_controller.perform_measurement,
            inputs=[osc_meas_source, osc_measurement_type],
            outputs=[osc_measurement_result]
        )
        
        osc_all_measurements_btn.click(
            fn=self.oscilloscope_controller.get_all_measurements,
            inputs=[osc_meas_source],
            outputs=[osc_all_measurements_result]
        )
        
        osc_glitch_btn.click(
            fn=self.oscilloscope_controller.set_glitch_trigger,
            inputs=[osc_glitch_source, osc_glitch_level, osc_glitch_polarity, osc_glitch_width],
            outputs=[osc_glitch_status]
        )
        
        osc_pulse_btn.click(
            fn=self.oscilloscope_controller.set_pulse_trigger,
            inputs=[osc_pulse_source, osc_pulse_level, osc_pulse_width, osc_pulse_polarity],
            outputs=[osc_pulse_status]
        )

        # Trigger sweep and holdoff handlers
        osc_sweep_btn.click(
            fn=self.oscilloscope_controller.set_trigger_sweep_mode,
            inputs=[osc_sweep_mode],
            outputs=[osc_sweep_status]
        )

        osc_holdoff_btn.click(
            fn=self.oscilloscope_controller.set_trigger_holdoff,
            inputs=[osc_holdoff_time],
            outputs=[osc_holdoff_status]
        )

        # Acquisition control handlers
        osc_acq_mode_btn.click(
            fn=self.oscilloscope_controller.set_acquisition_mode,
            inputs=[osc_acq_mode],
            outputs=[osc_acq_mode_status]
        )

        osc_acq_type_btn.click(
            fn=self.oscilloscope_controller.set_acquisition_type,
            inputs=[osc_acq_type],
            outputs=[osc_acq_type_status]
        )

        osc_avg_btn.click(
            fn=self.oscilloscope_controller.set_acquisition_count,
            inputs=[osc_avg_count],
            outputs=[osc_avg_status]
        )

        osc_info_btn.click(
            fn=self.oscilloscope_controller.query_acquisition_info,
            inputs=[],
            outputs=[osc_acq_info_display]
        )

        # Marker/cursor handlers
        osc_marker_mode_btn.click(
            fn=self.oscilloscope_controller.set_marker_mode,
            inputs=[osc_marker_mode],
            outputs=[osc_marker_mode_status]
        )

        osc_marker_set_btn.click(
            fn=self.oscilloscope_controller.set_marker_positions,
            inputs=[osc_marker_num, osc_marker_x, osc_marker_y],
            outputs=[osc_marker_status]
        )

        osc_delta_btn.click(
            fn=self.oscilloscope_controller.get_marker_deltas,
            inputs=[],
            outputs=[osc_delta_result]
        )

        # Math function handlers
        osc_math_config_btn.click(
            fn=self.oscilloscope_controller.configure_math_operation,
            inputs=[osc_math_func, osc_math_op, osc_math_src1, osc_math_src2],
            outputs=[osc_math_config_status]
        )

        osc_math_display_btn.click(
            fn=self.oscilloscope_controller.toggle_math_display,
            inputs=[osc_math_func, osc_math_show],
            outputs=[osc_math_display_status]
        )

        osc_math_scale_btn.click(
            fn=self.oscilloscope_controller.set_math_scale,
            inputs=[osc_math_func, osc_math_scale_val],
            outputs=[osc_math_scale_status]
        )

        # Setup management handlers
        osc_setup_save_btn.click(
            fn=self.oscilloscope_controller.save_instrument_setup,
            inputs=[osc_setup_save_name],
            outputs=[osc_setup_save_status]
        )

        osc_setup_recall_btn.click(
            fn=self.oscilloscope_controller.recall_instrument_setup,
            inputs=[osc_setup_recall_name],
            outputs=[osc_setup_recall_status]
        )

        osc_wf_save_btn.click(
            fn=self.oscilloscope_controller.save_waveform_to_memory,
            inputs=[osc_wf_save_ch, osc_wf_save_name],
            outputs=[osc_wf_save_status]
        )

        osc_wf_recall_btn.click(
            fn=self.oscilloscope_controller.recall_waveform_from_memory,
            inputs=[osc_wf_recall_name],
            outputs=[osc_wf_recall_status]
        )

        # Function generator handlers
        osc_wgen1_btn.click(
            fn=self.oscilloscope_controller.configure_wgen,
            inputs=[gr.State(1), osc_wgen1_enable, osc_wgen1_waveform, osc_wgen1_freq, osc_wgen1_amp, osc_wgen1_offset],
            outputs=[osc_wgen1_status]
        )

        osc_wgen1_info_btn.click(
            fn=self.oscilloscope_controller.get_wgen_configuration,
            inputs=[gr.State(1)],
            outputs=[osc_wgen1_status]
        )

        osc_wgen2_btn.click(
            fn=self.oscilloscope_controller.configure_wgen,
            inputs=[gr.State(2), osc_wgen2_enable, osc_wgen2_waveform, osc_wgen2_freq, osc_wgen2_amp, osc_wgen2_offset],
            outputs=[osc_wgen2_status]
        )

        osc_wgen2_info_btn.click(
            fn=self.oscilloscope_controller.get_wgen_configuration,
            inputs=[gr.State(2)],
            outputs=[osc_wgen2_status]
        )

        # Define path update functions
        def osc_update_paths(data, graphs, screenshots):
            self.oscilloscope_controller.save_locations['data'] = data
            self.oscilloscope_controller.save_locations['graphs'] = graphs
            self.oscilloscope_controller.save_locations['screenshots'] = screenshots
            return "Paths updated successfully"
        
        def osc_browse_data_folder(current_path):
            new_path = self.oscilloscope_controller.browse_folder(current_path, "Data")
            self.oscilloscope_controller.save_locations['data'] = new_path
            return new_path, f"Data directory updated to: {new_path}"
        
        def osc_browse_graphs_folder(current_path):
            new_path = self.oscilloscope_controller.browse_folder(current_path, "Graphs")
            self.oscilloscope_controller.save_locations['graphs'] = new_path
            return new_path, f"Graphs directory updated to: {new_path}"
        
        def osc_browse_screenshots_folder(current_path):
            new_path = self.oscilloscope_controller.browse_folder(current_path, "Screenshots")
            self.oscilloscope_controller.save_locations['screenshots'] = new_path
            return new_path, f"Screenshots directory updated to: {new_path}"
        
        # Connect the buttons to their functions
        osc_update_paths_btn.click(
            fn=osc_update_paths,
            inputs=[osc_data_path, osc_graphs_path, osc_screenshots_path],
            outputs=[osc_path_status]
        )
        
        osc_data_browse_btn.click(
            fn=osc_browse_data_folder,
            inputs=[osc_data_path],
            outputs=[osc_data_path, osc_path_status]
        )
        
        osc_graphs_browse_btn.click(
            fn=osc_browse_graphs_folder,
            inputs=[osc_graphs_path],
            outputs=[osc_graphs_path, osc_path_status]
        )
        
        osc_screenshots_browse_btn.click(
            fn=osc_browse_screenshots_folder,
            inputs=[osc_screenshots_path],
            outputs=[osc_screenshots_path, osc_path_status]
        )
        
        osc_screenshot_btn.click(
            fn=self.oscilloscope_controller.capture_screenshot,
            inputs=[],
            outputs=[osc_operation_status]
        )
        
        osc_acquire_btn.click(
            fn=self.oscilloscope_controller.acquire_data,
            inputs=[osc_op_ch1, osc_op_ch2, osc_op_ch3, osc_op_ch4, osc_op_math1, osc_op_math2, osc_op_math3, osc_op_math4],
            outputs=[osc_operation_status]
        )

        # Browse button for oscilloscope export
        def osc_browse_folder():
            """Open folder browser dialog for oscilloscope export"""
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            folder_path = filedialog.askdirectory(title="Select Save Location for Oscilloscope Data")
            root.destroy()
            return folder_path if folder_path else ""

        osc_export_browse_btn.click(
            fn=osc_browse_folder,
            outputs=[osc_export_path]
        )

        osc_export_btn.click(
            fn=self.oscilloscope_controller.export_csv,
            inputs=[osc_export_path],
            outputs=[osc_operation_status]
        )
        
        osc_plot_btn.click(
            fn=self.oscilloscope_controller.generate_plot,
            inputs=[osc_plot_title_input],
            outputs=[osc_operation_status]
        )
        
        osc_full_auto_btn.click(
            fn=self.oscilloscope_controller.run_full_automation,
            inputs=[osc_op_ch1, osc_op_ch2, osc_op_ch3, osc_op_ch4, osc_op_math1, osc_op_math2, osc_op_math3, osc_op_math4, osc_plot_title_input],
            outputs=[osc_operation_status]
        )

    def launch(self, share=False, server_port=7860, auto_open=True):
        """Launch the unified interface."""
        interface = self.create_interface()
        interface.launch(
            share=share,
            server_port=server_port,
            inbrowser=auto_open,
            show_error=True
        )


def main():
    """Application entry point."""
    print("DIGANTARA Unified Instrument Control")
    print("=" * 80)
    print("Starting web interface...")
    
    try:
        # Find an available port starting from 7860
        start_port = 7860
        max_attempts = 10
        
        for port in range(start_port, start_port + max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('', port))
                    s.close()
                
                print(f"Found available port: {port}")
                print("The browser will open automatically when ready.")
                print("IMPORTANT: To stop the application, press Ctrl+C in this terminal.")
                
                app = UnifiedInstrumentControl()
                app.launch(share=False, server_port=port, auto_open=True)
                break
                
            except OSError:
                if port == start_port + max_attempts - 1:
                    print(f"Error: Could not find an available port after {max_attempts} attempts.")
                    print("Please close any applications using ports {}-{}".format(start_port, start_port + max_attempts - 1))
                    return
                    
    except KeyboardInterrupt:
        print("\nApplication closed by user.")
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("\nApplication shutdown complete.")


if __name__ == "__main__":
    main()