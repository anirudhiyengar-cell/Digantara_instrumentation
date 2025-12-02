# Tektronix MSO24 Enhanced Control Interface

## 🚀 Professional-Grade Oscilloscope Automation

This enhanced Gradio interface provides comprehensive control for the **Tektronix MSO24** oscilloscope with all the advanced features you implemented for the Keysight scope.

### 📊 Available Interfaces

1. **tektronix_oscilloscope_gradio.py** - Basic interface (519 lines)
2. **tektronix_oscilloscope_gradio_en.py** - **ENHANCED** interface (3768 lines) ⭐

## ✨ Enhanced Features (11 Comprehensive Tabs)

### 1. **Connection**
- Connect/disconnect with status monitoring
- Instrument information display
- Connection health indicators

### 2. **Channel Configuration**
- Multi-channel setup (4 channels)
- Vertical scale, offset configuration
- Coupling selection (DC/AC)
- Probe attenuation
- Individual channel enable/disable

### 3. **Timebase & Trigger**
- Horizontal timebase configuration
- Trigger level and slope setup
- Edge trigger configuration
- Trigger source selection

### 4. **Advanced Triggers** ⚡
- **Pulse Width Trigger**: Detect specific pulse widths
- **Timeout Trigger**: Trigger on signal timeouts
- **Trigger Holdoff**: Prevent false triggers
- **Trigger Sweep Modes**: Auto, Normal, Single

### 5. **Acquisition Control** 📡
- **Acquisition Modes**: Sample, Peak Detect, Average, Hi-Res
- **Sample Rate Control**: Optimize for signal characteristics
- **Record Length**: Adjust memory depth
- **Averaging**: Reduce noise with averaging
- RUN / STOP / SINGLE controls
- Acquisition status monitoring

### 6. **Markers & Cursors** 📍
- **X-Axis Cursors**: Time measurements
- **Y-Axis Cursors**: Voltage measurements
- **Delta Measurements**: ΔX, ΔY calculations
- Automated cursor positioning
- Frequency calculation from cursors (1/ΔX)

### 7. **Math Functions** 🧮
- **Arithmetic Operations**: ADD, SUBTRACT, MULTIPLY, DIVIDE
- **FFT Analysis**: Frequency domain analysis
- **Source Selection**: Any combination of channels
- **Math Display Control**: Show/hide math waveforms
- **Scale Adjustment**: Independent vertical scaling

### 8. **Setup Management** 💾
- **Save Setups**: Store instrument configurations
- **Recall Setups**: Load saved configurations
- **Setup Library**: Manage multiple configurations
- Quick configuration switching

### 9. **Function Generators** (if available on your model)
- Waveform generation
- Frequency and amplitude control
- Output enable/disable

### 10. **Measurements** 📏
- **Automatic Measurements**: All standard parameters
  - Frequency, Period, Peak-to-Peak
  - Amplitude, High, Low levels
  - Rise Time, Fall Time
  - Duty Cycle (Positive/Negative)
  - Pulse Width (Positive/Negative)
  - RMS, Mean, Min, Max
  - Overshoot percentage
- **Multi-Channel Measurements**: Measure all channels simultaneously
- **Math Function Measurements**: Measure computed waveforms
- Real-time measurement updates
- Formatted SI unit display

### 11. **Operations & File Management** 📁
- **Waveform Acquisition**: Capture from multiple sources
- **CSV Export**: Save waveform data
- **Plot Generation**: Create publication-ready graphs
- **Screenshot Capture**: Save oscilloscope display
- **Batch Operations**: Process multiple channels
- **Custom File Naming**: Organized data storage
- **Directory Management**: Automatic folder creation

## 🎯 Quick Start - Enhanced Interface

### Launch the Enhanced Interface

```bash
python scripts/tektronix/tektronix_oscilloscope_gradio_en.py
```

Then open your browser to: **http://127.0.0.1:7860**

### Default VISA Address
```
USB0::0x0699::0x0105::SGV10003176::INSTR
```

## 🔧 Advanced Workflows

### Workflow 1: Complete Signal Analysis

1. **Connect** to oscilloscope
2. **Configure Channels**: Set appropriate scales
3. **Set Trigger**: Configure edge trigger
4. **Enable Measurements**: Select measurement parameters
5. **Capture Waveform**: Acquire data
6. **Export Data**: Save CSV and plots
7. **Take Screenshot**: Document setup

### Workflow 2: Pulse Width Analysis

1. Configure channel for pulse signal
2. Go to **Advanced Triggers** tab
3. Select **Pulse Width Trigger**
4. Set threshold and pulse width criteria
5. Capture and analyze pulses

### Workflow 3: Frequency Domain Analysis

1. Capture time-domain waveform
2. Go to **Math Functions** tab
3. Configure FFT on desired channel
4. Adjust FFT parameters (window, span)
5. Measure frequency components
6. Export FFT data

### Workflow 4: Multi-Channel Comparison

1. Configure all 4 channels
2. Set common timebase
3. Go to **Operations** tab
4. Select all channels for acquisition
5. Click **Acquire Waveforms**
6. Generate plots for all channels
7. Export CSV files

## 📐 Measurement Capabilities

The interface provides **17+ automatic measurements**:

| Category | Measurements |
|----------|-------------|
| **Frequency** | Frequency, Period |
| **Amplitude** | Peak-to-Peak, Amplitude, High, Low, Mean, RMS, Max, Min |
| **Timing** | Rise Time, Fall Time, Positive Width, Negative Width |
| **Duty Cycle** | Positive Duty, Negative Duty |
| **Quality** | Overshoot (%) |

All measurements include:
- ✅ Automatic SI prefix formatting (mV, µs, kHz, etc.)
- ✅ Real-time updates
- ✅ Error handling
- ✅ Multi-channel support

## 🎨 Interface Features

### Visual Design
- **Purple Theme**: Professional Digantara branding
- **Organized Tabs**: Logical feature grouping
- **Status Indicators**: Real-time feedback
- **Responsive Layout**: Works on various screen sizes

### User Experience
- **Clear Labels**: Intuitive control names
- **Help Text**: Contextual guidance
- **Error Messages**: Descriptive troubleshooting
- **Progress Indicators**: Operation status

## 🔬 Technical Specifications

### Tektronix MSO24 Support
- ✅ 4 Analog Channels
- ✅ 200 MHz Bandwidth
- ✅ 2.5 GS/s Sample Rate
- ✅ 125 Mpts Memory Depth
- ✅ All trigger modes
- ✅ Math functions
- ✅ Automated measurements

### Performance
- **Thread-Safe**: Concurrent operations supported
- **Logging**: Comprehensive error tracking
- **Timeout Management**: Handles long acquisitions
- **Data Validation**: Input verification

## 📝 Example Use Cases

### 1. Digital Signal Validation
```
1. Connect PWM signal to CH1
2. Configure: 5V/div, DC coupling
3. Set trigger: 2.5V, Rising edge
4. Measure: Frequency, Duty Cycle, Rise Time
5. Verify against specifications
```

### 2. Power Supply Ripple Analysis
```
1. Use AC coupling on CH1
2. Set: 10mV/div
3. Configure: Average mode (16 averages)
4. Measure: RMS voltage
5. Capture screenshot for report
```

### 3. Communication Protocol Debugging
```
1. CH1: Clock signal
2. CH2: Data signal
3. Use X-cursors to measure bit periods
4. Math: CH1-CH2 to see phase relationship
5. Export waveforms for further analysis
```

## 🚨 Troubleshooting

### Common Issues

**Connection Failed**
- Verify VISA address matches your instrument
- Check USB cable connection
- Install/update NI-VISA drivers

**Measurements Show N/A**
- Ensure signal is triggering
- Check vertical scale (signal not clipped/too small)
- Verify trigger level is appropriate

**Timeout Errors**
- Increase timeout for long acquisitions
- Check sample rate and record length settings

**Math Functions Not Displaying**
- Ensure source channels are enabled
- Check math function scale setting
- Verify operation type is correct

## 🔄 Comparison: Basic vs Enhanced

| Feature | Basic (519 lines) | Enhanced (3768 lines) |
|---------|------------------|----------------------|
| Tabs | 4 | 11 |
| Trigger Modes | Edge only | Edge, Pulse, Width, Timeout |
| Measurements | Basic | Comprehensive (17+) |
| Math Functions | ❌ | ✅ Full suite |
| Markers/Cursors | ❌ | ✅ With delta calculations |
| Acquisition Modes | Basic | Sample, Average, Peak, Hi-Res |
| File Management | Limited | Complete workflow |
| Setup Save/Recall | ❌ | ✅ |
| Batch Operations | ❌ | ✅ |
| Professional UI | Basic | Advanced with branding |

## 📦 File Structure

```
scripts/tektronix/
├── tektronix_test.py                    # Connection test (97 lines)
├── tektronix_oscilloscope_gradio.py     # Basic interface (519 lines)
├── tektronix_oscilloscope_gradio_en.py  # ENHANCED interface (3768 lines) ⭐
├── README.md                            # Basic documentation
└── README_ENHANCED.md                   # This file
```

## 💡 Tips for Best Results

1. **Start Simple**: Use basic interface first to verify connection
2. **Learn Gradually**: Explore one tab at a time
3. **Save Setups**: Create configurations for common tests
4. **Use Batch Mode**: Process multiple channels efficiently
5. **Document Everything**: Use screenshots and CSV exports
6. **Check Logs**: Review console output for troubleshooting

## 🎓 Learning Resources

- **Tektronix MSO2 Series Manual**: Complete SCPI command reference
- **Application Notes**: Signal measurement best practices
- **Your Files**: Check `oscilloscope_screenshots/`, `oscilloscope_data/`, `oscilloscope_graphs/`

## 👨‍💻 Developer Info

**Developed by**: Anirudh Iyengar
**Organization**: Digantara Research and Technologies Pvt. Ltd.
**Based on**: Enhanced Keysight DSOX6004A interface
**Adapted for**: Tektronix MSO24 (MSO2 Series)
**Date**: December 2, 2025

---

## 🌟 Why Use the Enhanced Interface?

The enhanced interface brings **professional-grade oscilloscope automation** to your Tektronix MSO24:

✅ **Save Time**: Batch operations and automated workflows
✅ **Increase Accuracy**: Automated measurements eliminate manual errors
✅ **Better Documentation**: Integrated screenshot and data export
✅ **Advanced Analysis**: Math functions and FFT capabilities
✅ **Reproducibility**: Save and recall complete setups
✅ **Professional Results**: Publication-ready plots and reports

**Start using it today and experience the difference!** 🚀
