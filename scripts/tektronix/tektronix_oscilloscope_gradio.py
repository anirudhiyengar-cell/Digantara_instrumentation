#!/usr/bin/env python3
"""
Tektronix MSO24 Oscilloscope Control - Clean Gradio Interface

Professional-grade web-based GUI for oscilloscope automation.
This interface uses high-level methods from the instrument control module.

Features:
- Clean separation of concerns
- High-level instrument control methods
- Comprehensive error handling
- Professional UI with file management
- Automated measurements and plotting

Author: Professional Instrumentation Control System
Date: 2025-12-02
"""

import sys
import logging
import threading
import time
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
import os

import gradio as gr
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams['agg.path.chunksize'] = 10000
plt.rcParams['path.simplify_threshold'] = 0.5

script_dir = Path(__file__).resolve().parent.parent.parent
if str(script_dir) not in sys.path:
    sys.path.append(str(script_dir))

try:
    from instrument_control.tektronix_oscilloscope import TektronixMSO24, TektronixMSO24Error
except ImportError as e:
    print(f"Error importing instrument control modules: {e}")
    print("Please ensure the instrument_control module is properly installed.")
    sys.exit(1)


def parse_timebase_string(value: str) -> float:
    """Parse timebase string with units to float in seconds"""
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
    "Rising": "RISE",
    "Falling": "FALL"
}


def format_si_value(value: float, kind: str) -> str:
    """Format value with appropriate SI prefix"""
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
    """Format measurement value based on type"""
    if value is None:
        return "N/A"
    if meas_type == "FREQUENCY":
        return format_si_value(value, "freq")
    if meas_type in ["PERIOD", "RISETIME", "FALLTIME", "PWIDTH", "NWIDTH"]:
        return format_si_value(value, "time")
    if meas_type in ["AMPLITUDE", "HIGH", "LOW", "MEAN", "RMS", "MAXIMUM", "MINIMUM", "PK2PK"]:
        return format_si_value(value, "volt")
    if meas_type in ["PDUTY", "NDUTY", "POVERSHOOT"]:
        return format_si_value(value, "percent")
    return f"{value}"


class TektronixOscilloscopeGUI:
    """Main GUI controller for Tektronix MSO24 oscilloscope"""

    def __init__(self):
        self.scope = None
        self.io_lock = threading.RLock()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.connected = False

        # Default connection parameters
        self.default_visa_address = "USB0::0x0699::0x0105::SGV10003176::INSTR"

    def connect_scope(self, visa_address: str) -> Tuple[str, str]:
        """Connect to oscilloscope"""
        try:
            with self.io_lock:
                if self.scope and self.connected:
                    return "Already connected", self._get_connection_info()

                self.scope = TektronixMSO24(visa_address, timeout_ms=60000)

                if self.scope.connect():
                    self.connected = True
                    info = self.scope.get_instrument_info()
                    self._logger.info(f"Connected to {info}")
                    return "✓ Connected successfully", self._get_connection_info()
                else:
                    self.connected = False
                    return "✗ Connection failed", "Not connected"
        except Exception as e:
            self._logger.error(f"Connection error: {e}")
            self.connected = False
            return f"✗ Error: {str(e)}", "Not connected"

    def disconnect_scope(self) -> Tuple[str, str]:
        """Disconnect from oscilloscope"""
        try:
            with self.io_lock:
                if self.scope and self.connected:
                    self.scope.disconnect()
                    self.connected = False
                    self.scope = None
                    return "✓ Disconnected successfully", "Not connected"
                else:
                    return "Already disconnected", "Not connected"
        except Exception as e:
            return f"✗ Error: {str(e)}", "Not connected"

    def _get_connection_info(self) -> str:
        """Get formatted connection information"""
        if not self.connected or not self.scope:
            return "Not connected"

        info = self.scope.get_instrument_info()
        if info:
            return f"""Connected to:
Manufacturer: {info['manufacturer']}
Model: {info['model']}
Serial: {info['serial_number']}
Firmware: {info['firmware_version']}
Bandwidth: {info['bandwidth_hz']/1e6:.0f} MHz
Channels: {info['max_channels']}"""
        return "Connected (info unavailable)"

    def configure_acquisition(self, channel: int, v_scale: float, v_offset: float,
                            coupling: str, probe_atten: float,
                            t_scale: str, trigger_level: float, trigger_slope: str) -> str:
        """Configure oscilloscope acquisition parameters"""
        if not self.connected:
            return "✗ Not connected to oscilloscope"

        try:
            with self.io_lock:
                # Parse timebase
                time_scale = parse_timebase_string(t_scale)

                # Configure channel
                if not self.scope.configure_channel(channel, v_scale, v_offset, coupling, probe_atten):
                    return f"✗ Failed to configure channel {channel}"

                # Configure timebase
                if not self.scope.configure_timebase(time_scale, 0.0):
                    return "✗ Failed to configure timebase"

                # Configure trigger
                slope = TRIGGER_SLOPE_MAP.get(trigger_slope, "RISE")
                if not self.scope.configure_trigger(channel, trigger_level, slope):
                    return "✗ Failed to configure trigger"

                return f"""✓ Configuration successful:
Channel {channel}: {v_scale}V/div, Offset={v_offset}V
Coupling: {coupling}, Probe: {probe_atten}x
Timebase: {t_scale}
Trigger: Level={trigger_level}V, Slope={trigger_slope}"""

        except Exception as e:
            self._logger.error(f"Configuration error: {e}")
            return f"✗ Error: {str(e)}"

    def capture_and_measure(self, channel: int) -> Tuple[str, str]:
        """Capture waveform and perform measurements"""
        if not self.connected:
            return "✗ Not connected", ""

        try:
            with self.io_lock:
                # Stop acquisition for stable measurement
                self.scope.stop()
                time.sleep(0.2)

                # Get all measurements
                measurements = self.scope.get_all_measurements(channel)

                # Resume acquisition
                self.scope.run()

                if not measurements:
                    return "✗ No measurements available", ""

                # Format measurements
                result = f"Channel {channel} Measurements:\n"
                result += "=" * 40 + "\n"

                key_measurements = [
                    ("FREQUENCY", "Frequency"),
                    ("PERIOD", "Period"),
                    ("PK2PK", "Peak-to-Peak"),
                    ("AMPLITUDE", "Amplitude"),
                    ("HIGH", "High Level"),
                    ("LOW", "Low Level"),
                    ("MEAN", "Mean"),
                    ("RMS", "RMS"),
                    ("RISETIME", "Rise Time"),
                    ("FALLTIME", "Fall Time"),
                    ("PDUTY", "Positive Duty"),
                    ("PWIDTH", "Positive Width"),
                ]

                for meas_type, label in key_measurements:
                    if meas_type in measurements:
                        formatted_val = format_measurement_value(meas_type, measurements[meas_type])
                        result += f"{label:20s}: {formatted_val}\n"

                return "✓ Measurements captured", result

        except Exception as e:
            self._logger.error(f"Measurement error: {e}")
            return f"✗ Error: {str(e)}", ""

    def capture_screenshot(self, filename: str = "") -> Tuple[str, Optional[str]]:
        """Capture oscilloscope screenshot"""
        if not self.connected:
            return "✗ Not connected", None

        try:
            with self.io_lock:
                screenshot_path = self.scope.capture_screenshot(
                    filename=filename if filename else None,
                    image_format="PNG",
                    freeze_acquisition=True
                )

                if screenshot_path:
                    return f"✓ Screenshot saved: {screenshot_path}", screenshot_path
                else:
                    return "✗ Screenshot capture failed", None

        except Exception as e:
            self._logger.error(f"Screenshot error: {e}")
            return f"✗ Error: {str(e)}", None

    def run_acquisition(self) -> str:
        """Start continuous acquisition"""
        if not self.connected:
            return "✗ Not connected"

        try:
            with self.io_lock:
                if self.scope.run():
                    return "✓ Acquisition running (RUN mode)"
                return "✗ Failed to start acquisition"
        except Exception as e:
            return f"✗ Error: {str(e)}"

    def stop_acquisition(self) -> str:
        """Stop acquisition"""
        if not self.connected:
            return "✗ Not connected"

        try:
            with self.io_lock:
                if self.scope.stop():
                    return "✓ Acquisition stopped"
                return "✗ Failed to stop acquisition"
        except Exception as e:
            return f"✗ Error: {str(e)}"

    def single_acquisition(self) -> str:
        """Trigger single acquisition"""
        if not self.connected:
            return "✗ Not connected"

        try:
            with self.io_lock:
                if self.scope.single():
                    return "✓ Single acquisition triggered"
                return "✗ Failed to trigger single acquisition"
        except Exception as e:
            return f"✗ Error: {str(e)}"

    def autoscale_scope(self) -> str:
        """Execute autoscale"""
        if not self.connected:
            return "✗ Not connected"

        try:
            with self.io_lock:
                if self.scope.autoscale():
                    return "✓ Autoscale completed"
                return "✗ Autoscale failed"
        except Exception as e:
            return f"✗ Error: {str(e)}"


def create_gradio_interface():
    """Create Gradio web interface"""
    gui = TektronixOscilloscopeGUI()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    with gr.Blocks(title="Tektronix MSO24 Oscilloscope Control") as app:
        gr.Markdown("# Tektronix MSO24 Oscilloscope Control Interface")
        gr.Markdown("Professional web-based control for Tektronix MSO24 4-channel oscilloscope")

        with gr.Tab("Connection"):
            with gr.Row():
                with gr.Column():
                    visa_input = gr.Textbox(
                        label="VISA Address",
                        value=gui.default_visa_address,
                        placeholder="USB0::0x0699::0x0105::SGV10003176::INSTR"
                    )
                    with gr.Row():
                        connect_btn = gr.Button("Connect", variant="primary")
                        disconnect_btn = gr.Button("Disconnect")

                    connection_status = gr.Textbox(label="Status", lines=2, interactive=False)

                with gr.Column():
                    connection_info = gr.Textbox(
                        label="Instrument Information",
                        lines=8,
                        interactive=False,
                        value="Not connected"
                    )

        with gr.Tab("Configuration"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Channel Configuration")
                    channel_select = gr.Dropdown(
                        choices=[1, 2, 3, 4],
                        value=1,
                        label="Channel"
                    )
                    v_scale = gr.Number(label="Vertical Scale (V/div)", value=1.0)
                    v_offset = gr.Number(label="Vertical Offset (V)", value=0.0)
                    coupling = gr.Dropdown(
                        choices=["DC", "AC"],
                        value="DC",
                        label="Coupling"
                    )
                    probe_atten = gr.Number(label="Probe Attenuation", value=10.0)

                with gr.Column():
                    gr.Markdown("### Timebase & Trigger")
                    timebase = gr.Textbox(label="Timebase (e.g., 1ms, 10us)", value="1ms")
                    trigger_level = gr.Number(label="Trigger Level (V)", value=0.0)
                    trigger_slope = gr.Dropdown(
                        choices=["Rising", "Falling"],
                        value="Rising",
                        label="Trigger Slope"
                    )

                    configure_btn = gr.Button("Apply Configuration", variant="primary")
                    config_status = gr.Textbox(label="Configuration Status", lines=6, interactive=False)

        with gr.Tab("Acquisition & Measurements"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Acquisition Control")
                    with gr.Row():
                        run_btn = gr.Button("RUN")
                        stop_btn = gr.Button("STOP")
                        single_btn = gr.Button("SINGLE")

                    acq_status = gr.Textbox(label="Acquisition Status", lines=2, interactive=False)

                    autoscale_btn = gr.Button("Autoscale", variant="secondary")
                    autoscale_status = gr.Textbox(label="Autoscale Status", lines=1, interactive=False)

                with gr.Column():
                    gr.Markdown("### Measurements")
                    meas_channel = gr.Dropdown(
                        choices=[1, 2, 3, 4],
                        value=1,
                        label="Measurement Channel"
                    )
                    measure_btn = gr.Button("Capture Measurements", variant="primary")
                    measure_status = gr.Textbox(label="Status", lines=2, interactive=False)
                    measurements_output = gr.Textbox(
                        label="Measurement Results",
                        lines=15,
                        interactive=False
                    )

        with gr.Tab("Screenshot"):
            with gr.Column():
                screenshot_filename = gr.Textbox(
                    label="Filename (optional - leave empty for auto-generated)",
                    placeholder="my_screenshot.png"
                )
                screenshot_btn = gr.Button("Capture Screenshot", variant="primary")
                screenshot_status = gr.Textbox(label="Status", lines=2, interactive=False)
                screenshot_display = gr.Image(label="Screenshot Preview", type="filepath")

        # Event handlers
        connect_btn.click(
            fn=gui.connect_scope,
            inputs=[visa_input],
            outputs=[connection_status, connection_info]
        )

        disconnect_btn.click(
            fn=gui.disconnect_scope,
            inputs=[],
            outputs=[connection_status, connection_info]
        )

        configure_btn.click(
            fn=gui.configure_acquisition,
            inputs=[channel_select, v_scale, v_offset, coupling, probe_atten,
                   timebase, trigger_level, trigger_slope],
            outputs=[config_status]
        )

        run_btn.click(
            fn=gui.run_acquisition,
            inputs=[],
            outputs=[acq_status]
        )

        stop_btn.click(
            fn=gui.stop_acquisition,
            inputs=[],
            outputs=[acq_status]
        )

        single_btn.click(
            fn=gui.single_acquisition,
            inputs=[],
            outputs=[acq_status]
        )

        autoscale_btn.click(
            fn=gui.autoscale_scope,
            inputs=[],
            outputs=[autoscale_status]
        )

        measure_btn.click(
            fn=gui.capture_and_measure,
            inputs=[meas_channel],
            outputs=[measure_status, measurements_output]
        )

        screenshot_btn.click(
            fn=gui.capture_screenshot,
            inputs=[screenshot_filename],
            outputs=[screenshot_status, screenshot_display]
        )

    return app


if __name__ == "__main__":
    app = create_gradio_interface()
    app.launch(
        server_name="127.0.0.1",
        server_port=7860,
        inbrowser=True,
        share=False,
        show_error=True
    )
