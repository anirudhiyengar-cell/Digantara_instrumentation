#!/usr/bin/env python3
"""
Keysight DMM Automation GUI

A simple Gradio-based web interface for controlling Keysight DM34461A
digital multimeters. This application provides an intuitive interface for precision
measurements, data logging, statistical analysis, and instrument configuration.

Features:
- Real-time measurements with live updates
- Statistical analysis and trending
- Data export capabilities with browse folder selection
- Waveform/trend plot saving
- Instrument status monitoring
- Error logging and diagnostics

Author: Anirudh Iyengar
Version: 1.0.0
"""

# =============================================================================
# FILE SAVE LOCATION CONFIGURATION - EDIT THESE PATHS
# =============================================================================
# INSTRUCTIONS: Enter the FULL file paths where you want to save files.
# - Use raw strings (prefix with r) for Windows paths
# - Example: r"C:\Users\YourName\Documents\DMM_Data"
# - Make sure you have write permissions to these directories
# - Directories will be created automatically if they don't exist
# =============================================================================

DMM_DATA_PATH = r"C:\Users\AnirudhIyengar\Downloads\test\Data"
DMM_PLOT_PATH = r"C:\Users\AnirudhIyengar\Downloads\test\Graphs"

# =============================================================================
# END OF CONFIGURATION - DO NOT EDIT BELOW THIS LINE
# =============================================================================

import gradio as gr
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import logging
import threading
import time
from datetime import datetime
from typing import Optional, Tuple
from pathlib import Path
import socket
import sys

# Add parent directory to path to import from instrument_control
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

try:
    from instrument_control.keysight_dmm import KeysightDM34461A, KeysightDM34461AError
except ImportError as e:
    print(f"ERROR: Failed to import DMM control library: {e}")
    print("Make sure the instrument_control package is in the Python path")
    sys.exit(1)


class DMM_GUI_Controller:
    """Main controller class for the DMM Gradio interface."""

    # Valid ranges for Keysight DM34461A (from programming manual)
    MEASUREMENT_RANGES = {
        'DC_VOLTAGE': [
            ("Auto", 0),
            ("100 mV", 0.1),
            ("1 V", 1),
            ("10 V", 10),
            ("100 V", 100),
            ("1000 V", 1000)
        ],
        'AC_VOLTAGE': [
            ("Auto", 0),
            ("100 mV", 0.1),
            ("1 V", 1),
            ("10 V", 10),
            ("100 V", 100),
            ("750 V", 750)
        ],
        'DC_CURRENT': [
            ("Auto", 0),
            ("100 µA", 0.0001),
            ("1 mA", 0.001),
            ("10 mA", 0.01),
            ("100 mA", 0.1),
            ("1 A", 1),
            ("3 A", 3),
            ("10 A", 10)
        ],
        'AC_CURRENT': [
            ("Auto", 0),
            ("100 µA", 0.0001),
            ("1 mA", 0.001),
            ("10 mA", 0.01),
            ("100 mA", 0.1),
            ("1 A", 1),
            ("3 A", 3),
            ("10 A", 10)
        ],
        'RESISTANCE_2W': [
            ("Auto", 0),
            ("100 Ω", 100),
            ("1 kΩ", 1000),
            ("10 kΩ", 10000),
            ("100 kΩ", 100000),
            ("1 MΩ", 1000000),
            ("10 MΩ", 10000000),
            ("100 MΩ", 100000000)
        ],
        'RESISTANCE_4W': [
            ("Auto", 0),
            ("100 Ω", 100),
            ("1 kΩ", 1000),
            ("10 kΩ", 10000),
            ("100 kΩ", 100000),
            ("1 MΩ", 1000000),
            ("10 MΩ", 10000000),
            ("100 MΩ", 100000000)
        ],
        'CAPACITANCE': [
            ("Auto", 0),
            ("1 nF", 1e-9),
            ("10 nF", 10e-9),
            ("100 nF", 100e-9),
            ("1 µF", 1e-6),
            ("10 µF", 10e-6),
            ("100 µF", 100e-6),
            ("1 mF", 1e-3),
            ("10 mF", 10e-3)
        ],
        'FREQUENCY': [
            ("Auto", 0),
            ("3 Hz", 3),
            ("20 Hz", 20),
            ("200 Hz", 200),
            ("2 kHz", 2000),
            ("20 kHz", 20000),
            ("200 kHz", 200000),
            ("1 MHz", 1000000)
        ],
        'TEMPERATURE': [
            ("Default", 0)
        ],
        'CONTINUITY': [
            ("Fixed 1 kΩ", 0)
        ],
        'DIODE': [
            ("Fixed", 0)
        ]
    }

    def __init__(self):
        """Initialize the GUI controller."""
        self.dmm: Optional[KeysightDM34461A] = None
        self.is_connected = False
        self.measurement_thread: Optional[threading.Thread] = None
        self.continuous_measurement = False
        self.measurement_data = []
        self.max_data_points = 65000

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('DMM_GUI')

        # Default save locations (from config at top of file)
        self.save_locations = {
            'data': DMM_DATA_PATH,
            'plots': DMM_PLOT_PATH
        }

        # Default settings
        self.default_settings = {
            'visa_address': 'USB0::0x2A8D::0xCE04::CN65410057::INSTR',
            'timeout_ms': 30000,
            'measurement_function': 'DC_VOLTAGE',
            'measurement_range': 10.0,
            'resolution': 1e-6,
            'nplc': 1.0,
            'measurement_interval': 1.0
        }

    @classmethod
    def get_range_choices(cls, function: str) -> list:
        """Get the range choices for a measurement function."""
        ranges = cls.MEASUREMENT_RANGES.get(function, [("Auto", 0)])
        return [r[0] for r in ranges]

    @classmethod
    def get_range_value(cls, function: str, range_label: str) -> float:
        """Convert a range label to its numeric value."""
        ranges = cls.MEASUREMENT_RANGES.get(function, [("Auto", 0)])
        for label, value in ranges:
            if label == range_label:
                return value
        return 0  # Default to auto

    def connect_instrument(self, visa_address: str, timeout_ms: int) -> Tuple[str, bool]:
        """Connect to the DMM instrument."""
        try:
            if self.is_connected:
                return "Already connected to instrument", True

            self.dmm = KeysightDM34461A(visa_address, int(timeout_ms))

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

    def single_measurement(self, function: str, range_label: str, resolution: float) -> Tuple[str, str]:
        """Perform a single measurement."""
        if not self.is_connected or not self.dmm:
            return "N/A", "Not connected to instrument"

        try:
            # Convert range label to numeric value
            range_val = self.get_range_value(function, range_label)
            # Convert range/resolution to None if 0 (auto)
            range_param = range_val if range_val > 0 else None
            res_param = resolution if resolution > 0 else None

            result = None
            unit = ''

            if function == 'DC_VOLTAGE':
                result = self.dmm.measure_dc_voltage(range_param, res_param)
                unit = 'V'
            elif function == 'AC_VOLTAGE':
                result = self.dmm.measure_ac_voltage(range_param, res_param)
                unit = 'V'
            elif function == 'DC_CURRENT':
                result = self.dmm.measure_dc_current(range_param, res_param)
                unit = 'A'
            elif function == 'AC_CURRENT':
                result = self.dmm.measure_ac_current(range_param, res_param)
                unit = 'A'
            elif function == 'RESISTANCE_2W':
                result = self.dmm.measure_resistance_2wire(range_param, res_param)
                unit = 'Ω'
            elif function == 'RESISTANCE_4W':
                result = self.dmm.measure_resistance_4wire(range_param, res_param)
                unit = 'Ω'
            elif function == 'CAPACITANCE':
                result = self.dmm.measure_capacitance(range_param, res_param)
                unit = 'F'
            elif function == 'FREQUENCY':
                result = self.dmm.measure_frequency(range_param, res_param)
                unit = 'Hz'
            elif function == 'TEMPERATURE':
                result = self.dmm.measure_temperature()
                unit = '°C'
            elif function == 'CONTINUITY':
                result = self.dmm.measure_continuity()
                unit = 'Ω'
            elif function == 'DIODE':
                result = self.dmm.measure_diode()
                unit = 'V'
            else:
                return "N/A", f"Unknown measurement function: {function}"

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

                # Format with SI prefixes
                formatted_result = self._format_with_si_prefix(result, unit)
                return formatted_result, "Measurement successful"
            else:
                return "N/A", "Measurement failed"

        except Exception as e:
            self.logger.error(f"Measurement error: {e}")
            return "N/A", f"Measurement error: {str(e)}"

    def start_continuous_measurement(self, function: str, range_label: str, resolution: float,
                                     interval: float) -> str:
        """Start continuous measurements in a separate thread."""
        if not self.is_connected:
            return "Not connected to instrument"

        if self.continuous_measurement:
            return "Continuous measurement already running"

        self.continuous_measurement = True
        self.measurement_thread = threading.Thread(
            target=self._continuous_measurement_worker,
            args=(function, range_label, resolution, interval),
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

    def _continuous_measurement_worker(self, function: str, range_label: str, resolution: float,
                                       interval: float):
        """Worker thread for continuous measurements."""
        while self.continuous_measurement and self.is_connected:
            try:
                self.single_measurement(function, range_label, resolution)
                time.sleep(interval)
            except Exception as e:
                self.logger.error(f"Continuous measurement error: {e}")
                break

    def get_statistics(self, last_n_points: int = 100) -> Tuple[str, str, str, str, str]:
        """Calculate statistics from recent measurements."""
        if not self.measurement_data:
            return "0", "N/A", "N/A", "N/A", "N/A"

        # Get recent data points
        recent_data = self.measurement_data[-int(last_n_points):] if len(self.measurement_data) > last_n_points else self.measurement_data
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
            recent_data = self.measurement_data[-int(last_n_points):] if len(self.measurement_data) > last_n_points else self.measurement_data

            if len(recent_data) < 2:
                return None

            timestamps = [point['timestamp'] for point in recent_data]
            values = [point['value'] for point in recent_data]
            function = recent_data[0]['function']

            fig, ax = plt.subplots(figsize=(12, 6))
            ax.plot(timestamps, values, 'b-', linewidth=1, marker='o', markersize=2)
            ax.set_xlabel('Time')
            ax.set_ylabel(f'Measurement Value ({self._get_unit(function)})')
            ax.set_title(f'{function.replace("_", " ").title()} Trend')
            ax.grid(True, alpha=0.3)

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
            'CAPACITANCE': 'F', 'FREQUENCY': 'Hz',
            'TEMPERATURE': '°C', 'CONTINUITY': 'Ω', 'DIODE': 'V'
        }
        return unit_map.get(function, '')

    def _format_with_si_prefix(self, value: float, base_unit: str) -> str:
        """Format a value with appropriate SI prefix."""
        if base_unit == '°C':
            return f"{value:.3f} {base_unit}"

        prefixes = [
            (1e12, 'T'), (1e9, 'G'), (1e6, 'M'), (1e3, 'k'),
            (1, ''), (1e-3, 'm'), (1e-6, 'µ'), (1e-9, 'n'),
            (1e-12, 'p'), (1e-15, 'f'),
        ]

        abs_value = abs(value)

        if abs_value == 0:
            return f"0.000 {base_unit}"

        for scale, prefix in prefixes:
            if abs_value >= scale:
                scaled_value = value / scale
                if abs(scaled_value) >= 100:
                    formatted = f"{scaled_value:.2f}"
                elif abs(scaled_value) >= 10:
                    formatted = f"{scaled_value:.3f}"
                else:
                    formatted = f"{scaled_value:.4f}"
                return f"{formatted} {prefix}{base_unit}"

        scaled_value = value / 1e-15
        return f"{scaled_value:.4f} f{base_unit}"

    def export_data(self, save_path: str, format_type: str = "CSV") -> str:
        """Export measurement data to file at user-specified location."""
        if not self.measurement_data:
            return "No data to export"

        if not save_path or save_path.strip() == "":
            return "Please enter a save location path"

        try:
            # Ensure the save directory exists
            save_dir = Path(save_path)
            save_dir.mkdir(parents=True, exist_ok=True)

            if not save_dir.is_dir():
                return f"Error: Path is not a directory: {save_path}"

            df = pd.DataFrame(self.measurement_data)
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

            if format_type == "CSV":
                filename = f"keysight_dmm_data_{timestamp_str}.csv"
                filepath = save_dir / filename
                df.to_csv(filepath, index=False)
            elif format_type == "JSON":
                filename = f"keysight_dmm_data_{timestamp_str}.json"
                filepath = save_dir / filename
                df.to_json(filepath, orient='records', date_format='iso')
            elif format_type == "Excel":
                filename = f"keysight_dmm_data_{timestamp_str}.xlsx"
                filepath = save_dir / filename
                df.to_excel(filepath, index=False)
            else:
                return "Unknown format"

            return f"Data exported to:\n{filepath}"
        except Exception as e:
            self.logger.error(f"Data export error: {e}")
            return f"Export error: {str(e)}"

    def save_trend_plot(self, save_path: str, last_n_points: int = 100) -> str:
        """Save the trend plot as PNG image."""
        if not self.measurement_data:
            return "No data to plot"

        if not save_path or save_path.strip() == "":
            return "Please enter a save location path"

        try:
            # Ensure the save directory exists
            save_dir = Path(save_path)
            save_dir.mkdir(parents=True, exist_ok=True)

            if not save_dir.is_dir():
                return f"Error: Path is not a directory: {save_path}"

            recent_data = self.measurement_data[-int(last_n_points):] if len(self.measurement_data) > last_n_points else self.measurement_data

            if len(recent_data) < 2:
                return "Insufficient data points for plot (need at least 2)"

            timestamps = [point['timestamp'] for point in recent_data]
            values = [point['value'] for point in recent_data]
            function = recent_data[0]['function']
            unit = self._get_unit(function)

            fig, ax = plt.subplots(figsize=(12, 6))
            ax.plot(timestamps, values, 'b-', linewidth=1.5, marker='o', markersize=3)
            ax.set_xlabel('Time', fontsize=12)
            ax.set_ylabel(f'Measurement Value ({unit})', fontsize=12)
            ax.set_title(f'Keysight DM34461A - {function.replace("_", " ").title()} Trend', fontsize=14)
            ax.grid(True, alpha=0.3)

            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=8))
            plt.xticks(rotation=45)

            # Add statistics annotation
            mean_val = np.mean(values)
            std_val = np.std(values)
            stats_text = f"Mean: {self._format_with_si_prefix(mean_val, unit)}\nStd Dev: {self._format_with_si_prefix(std_val, unit)}\nPoints: {len(values)}"
            ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=10,
                   verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

            plt.tight_layout()

            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"keysight_dmm_plot_{function}_{timestamp_str}.png"
            filepath = save_dir / filename

            plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
            plt.close(fig)

            return f"Plot saved to:\n{filepath}"
        except Exception as e:
            self.logger.error(f"Plot save error: {e}")
            return f"Plot save error: {str(e)}"

    def clear_data(self) -> str:
        """Clear all measurement data."""
        self.measurement_data.clear()
        return "Measurement data cleared"

    def get_instrument_status(self) -> Tuple[str, str, str, str]:
        """Get instrument status information."""
        if not self.is_connected or not self.dmm:
            return "Disconnected", "N/A", "N/A", "N/A"

        try:
            status = "Connected"

            info = self.dmm.get_instrument_info()
            if info:
                instrument_info = f"{info['manufacturer']} {info['model']} (S/N: {info['serial_number']})"
            else:
                instrument_info = "Unknown"

            errors = self.dmm.get_error_queue()
            error_str = str(errors) if errors else "None"

            temp = self.dmm.get_system_temperature()
            temp_str = f"{temp:.1f}°C" if temp else "N/A"

            return status, instrument_info, error_str, temp_str
        except Exception as e:
            self.logger.error(f"Status query error: {e}")
            return "Error", "N/A", f"Error: {str(e)}", "N/A"

    def reset_instrument(self) -> str:
        """Reset instrument to default state."""
        if not self.is_connected or not self.dmm:
            return "Not connected"
        try:
            if self.dmm.reset():
                return "Instrument reset successfully"
            return "Reset failed"
        except Exception as e:
            return f"Reset error: {str(e)}"

    def run_self_test(self) -> str:
        """Run instrument self-test."""
        if not self.is_connected or not self.dmm:
            return "Not connected"
        try:
            result = self.dmm.run_self_test()
            if result == 0:
                return "Self-test PASSED"
            return f"Self-test FAILED (code: {result})"
        except Exception as e:
            return f"Self-test error: {str(e)}"


def create_dmm_interface():
    """Create the main Gradio interface for DMM control."""
    controller = DMM_GUI_Controller()

    # CSS styling from Unified.py
    css = """
    /* ============================================================
       MAIN CONTAINER - Controls the entire interface width/height
       ============================================================ */
    .gradio-container {
        max-width: 100% !important;
        padding: 20px !important;
        margin: 0 !important;
        min-height: 100vh;
    }

    /* ============================================================
       CONTENT CONTAINER - Inner content area
       ============================================================ */
    .container {
        max-width: 100% !important;
        padding: 0 10px !important;
        margin: 0 !important;
    }

    /* ============================================================
       MAIN COMPONENT - Root component sizing
       ============================================================ */
    #component-0 {
        min-height: 100vh;
    }

    /* ============================================================
       TAB CONTENT - Each tab area
       ============================================================ */
    .tab {
        padding: 0 10px;
        min-height: calc(100vh - 120px);
    }

    /* ============================================================
       PANELS - Individual sections within tabs
       ============================================================ */
    .panel {
        margin: 5px 0;
    }

    /* ============================================================
       TAB NAVIGATION - The tab buttons at the top
       ============================================================ */
    .tab-nav {
        border-bottom: 2px solid #c034eb;
        margin-bottom: 12px;
    }

    /* ============================================================
       SELECTED TAB - The currently active tab appearance
       ============================================================ */
    .tab-selected {
        background-color: #e0e0ff;
        font-weight: 600;
    }
    """

    # Get the path to assets folder (same level as Unified.py)
    assets_path = Path(__file__).parent.parent.parent.parent / "assets" / "digantara_logo.png"

    with gr.Blocks(
        title="DIGANTARA Keysight DMM Control",
        theme=gr.themes.Soft(
            primary_hue="red",
            spacing_size="sm",
            radius_size="sm",
            text_size="sm"
        ),
        css=css
    ) as interface:
        # Header with logo and title (same as Unified.py)
        with gr.Row():
            with gr.Column(scale=1):
                gr.Image(
                    str(assets_path),
                    show_label=False,
                    container=False,
                    height=80,
                    width=550
                )
            with gr.Column(scale=5):
                gr.Markdown("# DIGANTARA Keysight DM34461A DMM Control")
                gr.Markdown("**Developed by: Anirudh Iyengar** | Digantara Research and Technologies Pvt. Ltd.")
                gr.Markdown("Professional 6.5-Digit TrueVolt Digital Multimeter Control Interface")

        with gr.Tabs():
            # Connection Tab
            with gr.Tab("Connection"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Instrument Connection")
                        visa_address = gr.Textbox(
                            label="VISA Address",
                            value=controller.default_settings['visa_address'],
                            placeholder="USB0::0x2A8D::0xCE04::CN65410057::INSTR",
                            info="Enter the VISA resource string for your DMM"
                        )
                        timeout_ms = gr.Dropdown(
                            label="Communication Timeout",
                            choices=[
                                ("5 seconds", 5000),
                                ("10 seconds", 10000),
                                ("30 seconds (Recommended)", 30000),
                                ("60 seconds", 60000),
                                ("120 seconds", 120000)
                            ],
                            value=30000,
                            info="Time to wait for instrument response"
                        )

                        with gr.Row():
                            connect_btn = gr.Button("Connect", variant="primary")
                            disconnect_btn = gr.Button("Disconnect", variant="secondary")

                        connection_status = gr.Textbox(
                            label="Connection Status",
                            interactive=False
                        )

                    with gr.Column(scale=1):
                        gr.Markdown("### Instrument Status")
                        status_connection = gr.Textbox(label="Connection", interactive=False)
                        status_instrument = gr.Textbox(label="Instrument", interactive=False)
                        status_errors = gr.Textbox(label="Errors", interactive=False)
                        status_temp = gr.Textbox(label="System Temperature", interactive=False)
                        refresh_status_btn = gr.Button("Refresh Status")

            # Measurement Tab
            with gr.Tab("Measurements"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Measurement Configuration")
                        measurement_function = gr.Dropdown(
                            label="Measurement Function",
                            choices=[
                                "DC_VOLTAGE", "AC_VOLTAGE",
                                "DC_CURRENT", "AC_CURRENT",
                                "RESISTANCE_2W", "RESISTANCE_4W",
                                "CAPACITANCE", "FREQUENCY", "TEMPERATURE",
                                "CONTINUITY", "DIODE"
                            ],
                            value="DC_VOLTAGE",
                            info="Select the type of measurement to perform"
                        )

                        measurement_range = gr.Dropdown(
                            label="Range",
                            choices=DMM_GUI_Controller.get_range_choices("DC_VOLTAGE"),
                            value="Auto",
                            info="Auto = auto-range (slower but convenient)"
                        )

                        resolution = gr.Dropdown(
                            label="Resolution",
                            choices=[
                                ("Default (Auto)", 0),
                                ("6.5 digits (Best)", 1e-7),
                                ("5.5 digits", 1e-6),
                                ("4.5 digits (Fast)", 1e-5),
                                ("3.5 digits (Fastest)", 1e-4)
                            ],
                            value=0,
                            info="Higher digits = more accurate but slower"
                        )

                        with gr.Row():
                            single_measure_btn = gr.Button("Single Measurement", variant="primary")
                            clear_data_btn = gr.Button("Clear Data", variant="secondary")

                    with gr.Column(scale=1):
                        gr.Markdown("### Measurement Results")
                        current_measurement = gr.Textbox(
                            label="Current Reading",
                            interactive=False,
                            lines=2
                        )

                        measurement_status = gr.Textbox(
                            label="Status",
                            interactive=False
                        )

                        gr.Markdown("### Continuous Measurements")
                        measurement_interval = gr.Dropdown(
                            label="Measurement Interval",
                            choices=[
                                ("100 ms (10 Hz) - Fast", 0.1),
                                ("200 ms (5 Hz)", 0.2),
                                ("500 ms (2 Hz)", 0.5),
                                ("1 second (1 Hz) - Recommended", 1.0),
                                ("2 seconds (0.5 Hz)", 2.0),
                                ("5 seconds (0.2 Hz)", 5.0),
                                ("10 seconds (0.1 Hz)", 10.0),
                                ("30 seconds", 30.0),
                                ("60 seconds (1 min)", 60.0)
                            ],
                            value=1.0,
                            info="Time between consecutive measurements"
                        )

                        with gr.Row():
                            start_continuous_btn = gr.Button("Start Continuous", variant="primary")
                            stop_continuous_btn = gr.Button("Stop Continuous", variant="secondary")

                        continuous_status = gr.Textbox(
                            label="Continuous Status",
                            interactive=False
                        )

            # Statistics Tab
            with gr.Tab("Statistics & Analysis"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Statistical Analysis")
                        stats_points = gr.Dropdown(
                            label="Number of Points to Analyze",
                            choices=[
                                ("Last 10 points", 10),
                                ("Last 50 points", 50),
                                ("Last 100 points (Recommended)", 100),
                                ("Last 250 points", 250),
                                ("Last 500 points", 500),
                                ("Last 1000 points", 1000),
                                ("All data (max 65000)", 65000)
                            ],
                            value=100,
                            info="Number of recent measurements for statistics"
                        )

                        calculate_stats_btn = gr.Button("Calculate Statistics", variant="primary")

                        stats_count = gr.Textbox(label="Count", interactive=False)
                        stats_mean = gr.Textbox(label="Mean", interactive=False)
                        stats_std = gr.Textbox(label="Standard Deviation", interactive=False)
                        stats_min = gr.Textbox(label="Minimum", interactive=False)
                        stats_max = gr.Textbox(label="Maximum", interactive=False)

                    with gr.Column(scale=2):
                        gr.Markdown("### Trend Plot")
                        plot_points = gr.Dropdown(
                            label="Points to Plot",
                            choices=[
                                ("Last 20 points", 20),
                                ("Last 50 points", 50),
                                ("Last 100 points (Recommended)", 100),
                                ("Last 250 points", 250),
                                ("Last 500 points", 500),
                                ("Last 1000 points", 1000)
                            ],
                            value=100,
                            info="Number of data points shown on graph"
                        )
                        update_plot_btn = gr.Button("Update Plot", variant="primary")
                        trend_plot = gr.Plot()

                        gr.Markdown("### Save Waveform/Plot")
                        plot_save_path = gr.Textbox(
                            label="Plot Save Directory",
                            value=controller.save_locations['plots'],
                            placeholder="Enter folder path to save plots",
                            info="Enter full path (e.g., C:\\Users\\YourName\\Desktop\\DMM_Plots)"
                        )
                        save_plot_btn = gr.Button("Save Plot as PNG (150 DPI)", variant="secondary")
                        plot_save_status = gr.Textbox(label="Save Status", interactive=False)

            # Data Export Tab
            with gr.Tab("Data Export"):
                with gr.Column():
                    gr.Markdown("### Export Measurement Data")

                    gr.Markdown("#### Save Location")
                    data_save_path = gr.Textbox(
                        label="Data Save Directory",
                        value=controller.save_locations['data'],
                        placeholder="Enter folder path to save data files",
                        info="Enter full path (e.g., C:\\Users\\YourName\\Desktop\\DMM_Data)"
                    )

                    export_format = gr.Dropdown(
                        label="Export Format",
                        choices=[
                            ("CSV (Recommended - Excel/Python compatible)", "CSV"),
                            ("JSON (Web/API compatible)", "JSON"),
                            ("Excel (.xlsx)", "Excel")
                        ],
                        value="CSV",
                        info="CSV is most versatile for data analysis"
                    )

                    export_btn = gr.Button("Export Data", variant="primary")
                    export_status = gr.Textbox(
                        label="Export Status",
                        interactive=False,
                        lines=2
                    )

                    gr.Markdown("### Data Preview (Last 20 measurements)")
                    data_preview = gr.Dataframe(
                        headers=["Timestamp", "Function", "Value", "Range", "Resolution"],
                        interactive=False
                    )

                    refresh_preview_btn = gr.Button("Refresh Preview")

            # System Tab
            with gr.Tab("System"):
                gr.Markdown("### System Controls")
                with gr.Row():
                    reset_btn = gr.Button("Reset Instrument", variant="stop")
                    self_test_btn = gr.Button("Self Test", variant="secondary")

                system_status = gr.Textbox(label="System Status", interactive=False)

        gr.Markdown("---")
        gr.Markdown("**DIGANTARA Lab Automation System** | Keysight DM34461A 6.5-Digit TrueVolt DMM Control")

        # Event handlers

        # Dynamic range dropdown update when measurement function changes
        def update_range_choices(function):
            choices = DMM_GUI_Controller.get_range_choices(function)
            return gr.Dropdown(choices=choices, value=choices[0])

        measurement_function.change(
            update_range_choices,
            inputs=[measurement_function],
            outputs=[measurement_range]
        )

        connect_btn.click(
            controller.connect_instrument,
            inputs=[visa_address, timeout_ms],
            outputs=[connection_status, gr.State()]
        )

        disconnect_btn.click(
            controller.disconnect_instrument,
            outputs=[connection_status]
        )

        refresh_status_btn.click(
            controller.get_instrument_status,
            outputs=[status_connection, status_instrument, status_errors, status_temp]
        )

        single_measure_btn.click(
            controller.single_measurement,
            inputs=[measurement_function, measurement_range, resolution],
            outputs=[current_measurement, measurement_status]
        )

        start_continuous_btn.click(
            controller.start_continuous_measurement,
            inputs=[measurement_function, measurement_range, resolution, measurement_interval],
            outputs=[continuous_status]
        )

        stop_continuous_btn.click(
            controller.stop_continuous_measurement,
            outputs=[continuous_status]
        )

        calculate_stats_btn.click(
            controller.get_statistics,
            inputs=[stats_points],
            outputs=[stats_count, stats_mean, stats_std, stats_min, stats_max]
        )

        update_plot_btn.click(
            controller.create_trend_plot,
            inputs=[plot_points],
            outputs=[trend_plot]
        )

        save_plot_btn.click(
            controller.save_trend_plot,
            inputs=[plot_save_path, plot_points],
            outputs=[plot_save_status]
        )

        export_btn.click(
            controller.export_data,
            inputs=[data_save_path, export_format],
            outputs=[export_status]
        )

        clear_data_btn.click(
            controller.clear_data,
            outputs=[measurement_status]
        )

        reset_btn.click(
            controller.reset_instrument,
            outputs=[system_status]
        )

        self_test_btn.click(
            controller.run_self_test,
            outputs=[system_status]
        )

        def update_data_preview():
            if controller.measurement_data:
                recent_data = controller.measurement_data[-20:]
                df_data = []
                for point in recent_data:
                    df_data.append([
                        point['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                        point['function'],
                        f"{point['value']:.6e}",
                        point['range'],
                        f"{point['resolution']:.2e}" if point['resolution'] else "Auto"
                    ])
                return df_data
            return []

        refresh_preview_btn.click(
            update_data_preview,
            outputs=[data_preview]
        )

    return interface


if __name__ == "__main__":
    print("Keysight DM34461A Digital Multimeter Automation GUI")
    print("=" * 60)
    print("Starting web interface...")

    hostname = socket.gethostname()
    print(f"Network access from other PCs: http://{hostname}:7866")
    interface = create_dmm_interface()
    interface.launch(
        server_name="0.0.0.0",
        server_port=7866,
        share=False,
        show_error=True
    )
