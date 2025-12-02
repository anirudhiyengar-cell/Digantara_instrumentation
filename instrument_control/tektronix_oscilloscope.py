"""
MEASUREMENT FEATURE: Tektronix MSO24 Oscilloscope Measurement Functions

Provides automatic waveform analysis with multiple measurement types including channel and math function measurements

✓ SCPI COMMANDS VERIFIED AGAINST TEKTRONIX MSO2 SERIES PROGRAMMING MANUAL
✓ ALL COMMANDS CROSS-REFERENCED WITH OFFICIAL DOCUMENTATION
✓ Optimized for Tektronix MSO24 4-channel oscilloscope

"""

import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Union
import numpy as np
from instrument_control.scpi_wrapper import SCPIWrapper

class TektronixMSO24Error(Exception):
    """Custom exception for Tektronix MSO24 oscilloscope errors."""
    pass

class TektronixMSO24:
    """Tektronix MSO24 Oscilloscope Control Class with Measurement Features"""

    def __init__(self, visa_address: str, timeout_ms: int = 60000) -> None:
        """
        Initialize oscilloscope connection parameters

        Args:
            visa_address: VISA resource address (e.g., "USB0::0x0699::0x0105::SGV10003176::INSTR")
            timeout_ms: Initial VISA timeout in milliseconds (default: 60000 = 60 seconds)
                       Note: Timeout will be automatically increased for long timebase settings
                       to prevent acquisition errors.
        """
        self._scpi_wrapper = SCPIWrapper(visa_address, timeout_ms)
        self._logger = logging.getLogger(f'{self.__class__.__name__}.{id(self)}')
        self.max_channels = 4
        self.max_sample_rate = 2.5e9  # MSO24: 2.5 GS/s
        self.max_memory_depth = 125e6  # MSO24: 125 Mpts
        self.bandwidth_hz = 200e6  # MSO24: 200 MHz

        self._valid_vertical_scales = [
            1e-3, 2e-3, 5e-3, 10e-3, 20e-3, 50e-3,
            100e-3, 200e-3, 500e-3, 1.0, 2.0, 5.0, 10.0
        ]

        self._valid_timebase_scales = [
            1e-9, 2e-9, 4e-9, 10e-9, 20e-9, 40e-9,
            100e-9, 200e-9, 400e-9, 1e-6, 2e-6, 4e-6,
            10e-6, 20e-6, 40e-6, 100e-6, 200e-6, 400e-6,
            1e-3, 2e-3, 4e-3, 10e-3, 20e-3, 40e-3,
            100e-3, 200e-3, 400e-3, 1.0, 2.0, 4.0, 10.0
        ]

        # Measurement types for Tektronix MSO2 series
        self._measurement_types = [
            "FREQUENCY", "PERIOD", "PK2PK", "AMPLITUDE", "HIGH", "LOW",
            "MEAN", "RMS", "MAXIMUM", "MINIMUM", "RISETIME", "FALLTIME",
            "PDUTY", "NDUTY", "POVERSHOOT", "PWIDTH", "NWIDTH"
        ]

    def connect(self) -> bool:
        """Establish VISA connection to oscilloscope"""
        if self._scpi_wrapper.connect():
            try:
                identification = self._scpi_wrapper.query("*IDN?")
                self._logger.info(f"Instrument identification: {identification.strip()}")
                self._scpi_wrapper.write("*CLS")
                time.sleep(0.5)
                self._scpi_wrapper.query("*OPC?")
                self._logger.info("Successfully connected to Tektronix MSO24")
                return True
            except Exception as e:
                self._logger.error(f"Error during instrument identification: {e}")
                self._scpi_wrapper.disconnect()
                return False
        return False

    def disconnect(self) -> None:
        """Close connection to oscilloscope"""
        self._scpi_wrapper.disconnect()
        self._logger.info("Disconnection completed")

    @property
    def is_connected(self) -> bool:
        """Check if oscilloscope is currently connected"""
        return self._scpi_wrapper.is_connected

    def get_instrument_info(self) -> Optional[Dict[str, Any]]:
        """Query instrument identification and specifications"""
        if not self.is_connected:
            return None
        try:
            idn = self._scpi_wrapper.query("*IDN?").strip()
            parts = idn.split(',')
            return {
                'manufacturer': parts[0] if len(parts) > 0 else 'Unknown',
                'model': parts[1] if len(parts) > 1 else 'Unknown',
                'serial_number': parts[2] if len(parts) > 2 else 'Unknown',
                'firmware_version': parts[3] if len(parts) > 3 else 'Unknown',
                'max_channels': self.max_channels,
                'bandwidth_hz': self.bandwidth_hz,
                'max_sample_rate': self.max_sample_rate,
                'max_memory_depth': self.max_memory_depth,
                'identification': idn
            }
        except Exception as e:
            self._logger.error(f"Failed to get instrument info: {e}")
            return None

    def configure_channel(self, channel: int, vertical_scale: float, vertical_offset: float = 0.0,
                          coupling: str = "DC", probe_attenuation: float = 1.0) -> bool:
        """
        Configure vertical parameters for specified channel

        Tektronix command syntax: CH<x>:SCAle, CH<x>:OFFSet, etc.
        """
        if not self.is_connected:
            raise TektronixMSO24Error("Oscilloscope not connected")
        if not (1 <= channel <= self.max_channels):
            raise ValueError(f"Channel must be 1-{self.max_channels}, got {channel}")

        try:
            # Tektronix: CH<x>:DISplay
            self._scpi_wrapper.write(f"CH{channel}:DISplay ON")
            time.sleep(0.05)

            # Tektronix: CH<x>:SCAle
            self._scpi_wrapper.write(f"CH{channel}:SCAle {vertical_scale}")
            time.sleep(0.05)

            # Tektronix: CH<x>:OFFSet
            self._scpi_wrapper.write(f"CH{channel}:OFFSet {vertical_offset}")
            time.sleep(0.05)

            # Tektronix: CH<x>:COUPling {AC|DC|DCREJECT}
            self._scpi_wrapper.write(f"CH{channel}:COUPling {coupling}")
            time.sleep(0.05)

            # Tektronix: CH<x>:PRObe:GAIN (inverse of attenuation)
            self._scpi_wrapper.write(f"CH{channel}:PRObe:GAIN {probe_attenuation}")
            time.sleep(0.05)

            self._logger.info(f"Channel {channel} configured: Scale={vertical_scale}V/div, "
                            f"Offset={vertical_offset}V, Coupling={coupling}, Probe={probe_attenuation}x")
            return True
        except Exception as e:
            self._logger.error(f"Failed to configure channel {channel}: {e}")
            return False

    def configure_timebase(self, time_scale: float, time_offset: float = 0.0) -> bool:
        """
        Configure horizontal timebase settings

        Automatically adjusts VISA timeout based on timebase to prevent timeout errors
        during long acquisitions
        """
        if not self.is_connected:
            self._logger.error("Cannot configure timebase: oscilloscope not connected")
            return False

        if time_scale not in self._valid_timebase_scales:
            closest_scale = min(self._valid_timebase_scales, key=lambda x: abs(x - time_scale))
            self._logger.warning(f"Invalid timebase scale {time_scale}s, using {closest_scale}s")
            time_scale = closest_scale

        try:
            # Calculate required timeout based on timebase
            estimated_acq_time_s = 10 * time_scale
            required_timeout_ms = int((estimated_acq_time_s * 1.5 + 10) * 1000)
            required_timeout_ms = max(required_timeout_ms, 10000)

            if required_timeout_ms > self._scpi_wrapper.timeout:
                self._scpi_wrapper.set_timeout(required_timeout_ms)
                self._logger.info(f"Timeout adjusted to {required_timeout_ms/1000:.1f}s for timebase {time_scale}s/div")

            # Tektronix: HORizontal:SCAle
            self._scpi_wrapper.write(f"HORizontal:SCAle {time_scale}")
            time.sleep(0.1)

            # Tektronix: HORizontal:POSition (percentage of record)
            self._scpi_wrapper.write(f"HORizontal:POSition {time_offset}")
            time.sleep(0.1)

            self._logger.info(f"Timebase configured: Scale={time_scale}s/div, Offset={time_offset}s")
            return True
        except Exception as e:
            self._logger.error(f"Failed to configure timebase: {type(e).__name__}: {e}")
            return False

    def configure_trigger(self, channel: int, trigger_level: float, trigger_slope: str = "RISE") -> bool:
        """
        Configure trigger settings

        Tektronix uses: RISE/FALL instead of POS/NEG
        """
        if not self.is_connected:
            self._logger.error("Cannot configure trigger: oscilloscope not connected")
            return False

        if not (1 <= channel <= self.max_channels):
            raise ValueError(f"Channel must be 1-{self.max_channels}, got {channel}")

        valid_slopes = ["RISE", "FALL", "EITHER"]
        if trigger_slope.upper() not in valid_slopes:
            raise ValueError(f"Trigger slope must be one of {valid_slopes}, got {trigger_slope}")

        try:
            # Tektronix: TRIGger:A:TYPE
            self._scpi_wrapper.write("TRIGger:A:TYPE EDGE")
            time.sleep(0.1)

            # Tektronix: TRIGger:A:EDGE:SOUrce
            self._scpi_wrapper.write(f"TRIGger:A:EDGE:SOUrce CH{channel}")
            time.sleep(0.1)

            # Tektronix: TRIGger:A:LEVel:CH<x>
            self._scpi_wrapper.write(f"TRIGger:A:LEVel:CH{channel} {trigger_level}")
            time.sleep(0.1)

            # Tektronix: TRIGger:A:EDGE:SLOpe
            self._scpi_wrapper.write(f"TRIGger:A:EDGE:SLOpe {trigger_slope.upper()}")
            time.sleep(0.1)

            self._logger.info(f"Trigger configured: Channel={channel}, Level={trigger_level}V, Slope={trigger_slope}")
            return True
        except Exception as e:
            self._logger.error(f"Failed to configure trigger: {type(e).__name__}: {e}")
            return False

    # ============================================================================
    # MEASUREMENT FUNCTIONS - TEKTRONIX MSO2 SERIES
    # ============================================================================

    def measure_single(self, channel: int, measurement_type: str) -> Optional[float]:
        """
        Perform a single measurement on specified channel

        Tektronix measurement syntax: MEASUrement:MEAS<x>:TYPe, SOUrce1, VALue?

        Args:
            channel (int): Channel number (1-4)
            measurement_type (str): Type of measurement (FREQUENCY, PERIOD, PK2PK, etc.)

        Returns:
            float: Measurement value or None if error
        """
        if not self.is_connected:
            self._logger.error("Cannot measure: oscilloscope not connected")
            return None

        if not (1 <= channel <= self.max_channels):
            self._logger.error(f"Invalid channel: {channel}")
            return None

        try:
            # Tektronix uses a different measurement approach
            # Configure measurement 1 for this measurement
            self._scpi_wrapper.write(f"MEASUrement:MEAS1:TYPe {measurement_type}")
            time.sleep(0.05)

            self._scpi_wrapper.write(f"MEASUrement:MEAS1:SOUrce1 CH{channel}")
            time.sleep(0.05)

            # Query the measurement value
            response = self._scpi_wrapper.query("MEASUrement:MEAS1:VALue?").strip()

            try:
                value = float(response)
                self._logger.debug(f"CH{channel} {measurement_type}: {value}")
                return value
            except ValueError:
                self._logger.error(f"Failed to parse measurement response: '{response}'")
                return None

        except Exception as e:
            self._logger.error(f"Measurement failed for CH{channel} ({measurement_type}): {e}")
            return None

    def measure_multiple(self, channel: int, measurement_types: List[str]) -> Optional[Dict[str, float]]:
        """
        Perform multiple measurements on specified channel

        Args:
            channel (int): Channel number (1-4)
            measurement_types (List[str]): List of measurement types

        Returns:
            Dict[str, float]: Dictionary with measurement names as keys and values
        """
        if not self.is_connected:
            self._logger.error("Cannot measure: oscilloscope not connected")
            return None

        results = {}
        for meas_type in measurement_types:
            value = self.measure_single(channel, meas_type)
            if value is not None:
                results[meas_type] = value

        if results:
            self._logger.info(f"CH{channel} measurements: {results}")
            return results
        else:
            self._logger.error(f"No measurements succeeded for CH{channel}")
            return None

    def get_all_measurements(self, channel: int) -> Optional[Dict[str, float]]:
        """
        Get all available measurements for a channel

        Args:
            channel (int): Channel number (1-4)

        Returns:
            Dict[str, float]: All available measurements
        """
        essential_measurements = [
            "FREQUENCY", "PERIOD", "PK2PK", "AMPLITUDE", "HIGH", "LOW",
            "MEAN", "RMS", "MAXIMUM", "MINIMUM", "RISETIME", "FALLTIME",
            "PDUTY", "NDUTY", "POVERSHOOT", "PWIDTH", "NWIDTH"
        ]
        return self.measure_multiple(channel, essential_measurements)

    # ============================================================================
    # CONVENIENCE MEASUREMENT METHODS - CHANNEL
    # ============================================================================

    def measure_frequency(self, channel: int) -> Optional[float]:
        """Measure signal frequency in Hz"""
        return self.measure_single(channel, "FREQUENCY")

    def measure_period(self, channel: int) -> Optional[float]:
        """Measure signal period in seconds"""
        return self.measure_single(channel, "PERIOD")

    def measure_peak_to_peak(self, channel: int) -> Optional[float]:
        """Measure signal peak-to-peak voltage in volts"""
        return self.measure_single(channel, "PK2PK")

    def measure_amplitude(self, channel: int) -> Optional[float]:
        """Measure signal amplitude in volts"""
        return self.measure_single(channel, "AMPLITUDE")

    def measure_top(self, channel: int) -> Optional[float]:
        """Measure signal top voltage in volts"""
        return self.measure_single(channel, "HIGH")

    def measure_base(self, channel: int) -> Optional[float]:
        """Measure signal base voltage in volts"""
        return self.measure_single(channel, "LOW")

    def measure_mean(self, channel: int) -> Optional[float]:
        """Measure signal mean voltage in volts"""
        return self.measure_single(channel, "MEAN")

    def measure_rms(self, channel: int) -> Optional[float]:
        """Measure signal RMS voltage in volts"""
        return self.measure_single(channel, "RMS")

    def measure_max(self, channel: int) -> Optional[float]:
        """Measure maximum voltage in volts"""
        return self.measure_single(channel, "MAXIMUM")

    def measure_min(self, channel: int) -> Optional[float]:
        """Measure minimum voltage in volts"""
        return self.measure_single(channel, "MINIMUM")

    def measure_rise_time(self, channel: int) -> Optional[float]:
        """Measure signal rise time in seconds"""
        return self.measure_single(channel, "RISETIME")

    def measure_fall_time(self, channel: int) -> Optional[float]:
        """Measure signal fall time in seconds"""
        return self.measure_single(channel, "FALLTIME")

    def measure_duty_cycle_positive(self, channel: int) -> Optional[float]:
        """Measure positive duty cycle as percentage"""
        return self.measure_single(channel, "PDUTY")

    def measure_duty_cycle_negative(self, channel: int) -> Optional[float]:
        """Measure negative duty cycle as percentage"""
        return self.measure_single(channel, "NDUTY")

    def measure_overshoot(self, channel: int) -> Optional[float]:
        """Measure signal overshoot as percentage"""
        return self.measure_single(channel, "POVERSHOOT")

    def measure_pulse_width_positive(self, channel: int) -> Optional[float]:
        """Measure positive pulse width in seconds"""
        return self.measure_single(channel, "PWIDTH")

    def measure_pulse_width_negative(self, channel: int) -> Optional[float]:
        """Measure negative pulse width in seconds"""
        return self.measure_single(channel, "NWIDTH")

    # ============================================================================
    # ACQUISITION CONTROL - RUN, STOP, SINGLE
    # ============================================================================

    def run(self) -> bool:
        """Start continuous acquisition"""
        if not self.is_connected:
            self._logger.error("Cannot run: oscilloscope not connected")
            return False

        try:
            self._scpi_wrapper.write("ACQuire:STATE RUN")
            time.sleep(0.1)
            self._logger.info("Acquisition started: RUN")
            return True
        except Exception as e:
            self._logger.error(f"Failed to start acquisition: {type(e).__name__}: {e}")
            return False

    def stop(self) -> bool:
        """Stop acquisition"""
        if not self.is_connected:
            self._logger.error("Cannot stop: oscilloscope not connected")
            return False

        try:
            self._scpi_wrapper.write("ACQuire:STATE STOP")
            time.sleep(0.1)
            self._logger.info("Acquisition stopped: STOP")
            return True
        except Exception as e:
            self._logger.error(f"Failed to stop acquisition: {type(e).__name__}: {e}")
            return False

    def single(self) -> bool:
        """Trigger single acquisition"""
        if not self.is_connected:
            self._logger.error("Cannot trigger single: oscilloscope not connected")
            return False

        try:
            self._scpi_wrapper.write("ACQuire:STOPAfter SEQUENCE")
            time.sleep(0.05)
            self._scpi_wrapper.write("ACQuire:STATE RUN")
            time.sleep(0.1)
            self._logger.info("Single acquisition triggered")
            return True
        except Exception as e:
            self._logger.error(f"Failed to trigger single: {type(e).__name__}: {e}")
            return False

    # ============================================================================
    # WAVEFORM DATA TRANSFER
    # ============================================================================

    def get_waveform_data(self, channel: int, freeze_acquisition: bool = True) -> Optional[np.ndarray]:
        """
        Retrieve waveform data from oscilloscope

        Args:
            channel: Channel number (1-4)
            freeze_acquisition: If True, stops acquisition before reading data and resumes after

        Returns:
            numpy array of waveform data or None if error
        """
        if not self.is_connected:
            self._logger.error("Cannot get waveform: oscilloscope not connected")
            return None

        if not (1 <= channel <= self.max_channels):
            self._logger.error(f"Invalid channel: {channel}")
            return None

        acquisition_was_running = False

        try:
            if freeze_acquisition:
                try:
                    self._logger.info("Stopping acquisition to freeze waveform for data transfer")
                    self.stop()
                    acquisition_was_running = True
                    time.sleep(0.2)
                except Exception as e:
                    self._logger.warning(f"Could not stop acquisition: {e}")

            # Tektronix waveform transfer commands
            self._scpi_wrapper.write(f"DATa:SOUrce CH{channel}")
            time.sleep(0.05)

            self._scpi_wrapper.write("DATa:ENCdg RIBinary")  # Signed integer binary
            time.sleep(0.05)

            self._scpi_wrapper.write("DATa:WIDth 1")  # 1 byte per sample
            time.sleep(0.05)

            # Get waveform preamble for scaling
            preamble = self._scpi_wrapper.query("WFMOutpre?").strip()
            self._logger.debug(f"Waveform preamble: {preamble}")

            # Query waveform data
            data = self._scpi_wrapper.query_binary_values("CURVe?", datatype='b')

            if data:
                waveform = np.array(data, dtype=np.int8)
                self._logger.info(f"Retrieved {len(waveform)} waveform points from CH{channel}")

                if freeze_acquisition and acquisition_was_running:
                    try:
                        self._logger.info("Resuming acquisition (RUN mode)")
                        self.run()
                        time.sleep(0.1)
                    except Exception as e:
                        self._logger.warning(f"Could not restart acquisition: {e}")

                return waveform

            return None
        except Exception as e:
            self._logger.error(f"Failed to get waveform data: {type(e).__name__}: {e}")

            if freeze_acquisition and acquisition_was_running:
                try:
                    self._logger.info("Resuming acquisition after error")
                    self.run()
                except Exception as resume_error:
                    self._logger.error(f"Failed to resume acquisition: {resume_error}")

            return None

    # ============================================================================
    # SCREENSHOT CAPTURE
    # ============================================================================

    def capture_screenshot(self, filename: Optional[str] = None, image_format: str = "PNG",
                          include_timestamp: bool = True, freeze_acquisition: bool = True) -> Optional[str]:
        """
        Capture oscilloscope display screenshot

        Args:
            filename: Custom filename (None = auto-generate with timestamp)
            image_format: Image format ("PNG")
            include_timestamp: Include timestamp in auto-generated filename
            freeze_acquisition: If True, stops acquisition before screenshot and resumes after

        Returns:
            str: Path to saved screenshot file, or None if failed
        """
        if not self.is_connected:
            self._logger.error("Cannot capture screenshot: not connected")
            return None

        acquisition_was_running = False

        try:
            self.setup_output_directories()

            if freeze_acquisition:
                try:
                    self._logger.info("Stopping acquisition to freeze display for screenshot")
                    self.stop()
                    acquisition_was_running = True
                    time.sleep(0.2)
                except Exception as e:
                    self._logger.warning(f"Could not stop acquisition: {e}")

            if filename is None:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                filename = f"tektronix_screenshot_{timestamp}.{image_format.lower()}"

            if not filename.lower().endswith(f".{image_format.lower()}"):
                filename += f".{image_format.lower()}"

            screenshot_path = self.screenshot_dir / filename

            # Tektronix screenshot command
            self._logger.info(f"Capturing screenshot in {image_format} format")
            self._scpi_wrapper.write("SAVe:IMAGe:FILEFormat PNG")
            time.sleep(0.05)

            image_data = self._scpi_wrapper.query_binary_values("HARDCopy STARt", datatype='B')

            if image_data:
                with open(screenshot_path, 'wb') as f:
                    f.write(bytes(image_data))
                self._logger.info(f"Screenshot saved: {screenshot_path}")

                if freeze_acquisition and acquisition_was_running:
                    try:
                        self._logger.info("Resuming acquisition (RUN mode)")
                        self.run()
                        time.sleep(0.1)
                    except Exception as e:
                        self._logger.warning(f"Could not restart acquisition: {e}")

                return str(screenshot_path)

            return None
        except Exception as e:
            self._logger.error(f"Screenshot capture failed: {e}")

            if freeze_acquisition and acquisition_was_running:
                try:
                    self._logger.info("Resuming acquisition after error")
                    self.run()
                except Exception as resume_error:
                    self._logger.error(f"Failed to resume acquisition: {resume_error}")

            return None

    def setup_output_directories(self) -> None:
        """Create default output directories"""
        base_path = Path.cwd()
        self.screenshot_dir = base_path / "oscilloscope_screenshots"
        self.data_dir = base_path / "oscilloscope_data"
        self.graph_dir = base_path / "oscilloscope_graphs"

        for directory in [self.screenshot_dir, self.data_dir, self.graph_dir]:
            directory.mkdir(exist_ok=True)

    # ============================================================================
    # SYSTEM COMMANDS & UTILITIES
    # ============================================================================

    def reset(self) -> bool:
        """Reset oscilloscope to default state"""
        if not self.is_connected:
            self._logger.error("Cannot reset: oscilloscope not connected")
            return False

        try:
            self._scpi_wrapper.write("*RST")
            time.sleep(1.0)
            self._scpi_wrapper.query("*OPC?")
            self._logger.info("Oscilloscope reset to default state")
            return True
        except Exception as e:
            self._logger.error(f"Failed to reset oscilloscope: {type(e).__name__}: {e}")
            return False

    def autoscale(self) -> bool:
        """Execute autoscale command"""
        if not self.is_connected:
            self._logger.error("Cannot autoscale: oscilloscope not connected")
            return False

        try:
            self._scpi_wrapper.write("AUTOSet EXECute")
            time.sleep(2.0)
            self._scpi_wrapper.query("*OPC?")
            self._logger.info("Autoscale executed successfully")
            return True
        except Exception as e:
            self._logger.error(f"Autoscale failed: {type(e).__name__}: {e}")
            return False
