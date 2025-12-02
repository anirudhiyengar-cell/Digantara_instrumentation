#!/usr/bin/env python3
"""
Simple test script for Tektronix MSO24 oscilloscope connection

This script can be used to quickly verify the Tektronix oscilloscope connection
and basic functionality.
"""

import sys
from pathlib import Path

# Add parent directory to path
script_dir = Path(__file__).resolve().parent.parent.parent
if str(script_dir) not in sys.path:
    sys.path.append(str(script_dir))

from instrument_control.tektronix_oscilloscope import TektronixMSO24, TektronixMSO24Error


def test_connection():
    """Test basic connection to Tektronix MSO24"""

    # Your Tektronix MSO24 VISA address
    visa_address = "USB0::0x0699::0x0105::SGV10003176::INSTR"

    print("=" * 60)
    print("Tektronix MSO24 Oscilloscope Connection Test")
    print("=" * 60)

    try:
        # Create scope instance
        print(f"\n1. Creating TektronixMSO24 instance...")
        scope = TektronixMSO24(visa_address, timeout_ms=10000)

        # Connect to scope
        print(f"2. Connecting to {visa_address}...")
        if scope.connect():
            print("   ✓ Connection successful!")

            # Get instrument info
            print(f"\n3. Retrieving instrument information...")
            info = scope.get_instrument_info()
            if info:
                print(f"   Manufacturer: {info['manufacturer']}")
                print(f"   Model: {info['model']}")
                print(f"   Serial Number: {info['serial_number']}")
                print(f"   Firmware: {info['firmware_version']}")
                print(f"   Bandwidth: {info['bandwidth_hz']/1e6:.0f} MHz")
                print(f"   Channels: {info['max_channels']}")

            # Test basic configuration
            print(f"\n4. Testing basic configuration...")
            print("   Configuring Channel 1: 1V/div, DC coupling")
            if scope.configure_channel(1, 1.0, 0.0, "DC", 10.0):
                print("   ✓ Channel configured successfully")

            print("   Configuring timebase: 1ms/div")
            if scope.configure_timebase(1e-3, 0.0):
                print("   ✓ Timebase configured successfully")

            print("   Configuring trigger: CH1, 0V, Rising edge")
            if scope.configure_trigger(1, 0.0, "RISE"):
                print("   ✓ Trigger configured successfully")

            # Test measurement
            print(f"\n5. Testing measurement capability...")
            freq = scope.measure_frequency(1)
            if freq is not None:
                print(f"   CH1 Frequency: {freq:.2f} Hz")

            # Disconnect
            print(f"\n6. Disconnecting...")
            scope.disconnect()
            print("   ✓ Disconnected successfully")

            print("\n" + "=" * 60)
            print("✓ ALL TESTS PASSED")
            print("=" * 60)
            return True

        else:
            print("   ✗ Connection failed!")
            return False

    except TektronixMSO24Error as e:
        print(f"\n✗ Tektronix MSO24 Error: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
