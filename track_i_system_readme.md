# Track-I: CSI Camera + YOLO + Dual Haptic Feedback + TTS + UI System

Track-I is a real-time embedded computer vision and assistive feedback system designed for platforms like NVIDIA Jetson. It integrates a CSI camera (IMX219), YOLOv8 object detection, dual haptic feedback motors (DA7280 x2 via TCA9548A multiplexer), Text-to-Speech (TTS) announcements, and an interactive OpenCV-based graphical user interface.

---

## Features

- **Multi-threaded Architecture**: Separates camera capture, YOLO inference, haptic control, and TTS synthesis into independent daemon threads to maintain high performance.
- **Real-Time Object Detection**: Uses YOLOv8 (compatible with PyTorch or optimized TensorRT engines) to detect and classify obstacles.
- **Spatial & Proximity Grading**: 
  - **Horizontal Positioning**: Categorizes objects into `LEFT`, `CENTER`, or `RIGHT`.
  - **Hazard Levels**: Evaluates proximity into `FAR`, `NEAR`, and `DANGER` based on bounding box area and vertical screen position.
- **Dual Haptic Feedback**: Drives dual DA7280 haptic drivers over an I2C multiplexer (TCA9548A) to provide directional and intensity-scaled vibration alerts.
- **Text-to-Speech (TTS) Integration**: Supports engines like `espeak-ng` to announce hazards with immediate interrupt capabilities for critical danger events.
- **Interactive UI**: Provides a clean OpenCV display with visual indicators, zone dividers, FPS counters, and an on-screen exit button.

---

## Hardware Requirements

1. **Host Board**: NVIDIA Jetson Nano / Xavier / Orin (or any Linux board with CSI camera support and I2C capability).
2. **Camera**: Sony IMX219 CSI Camera (or compatible GStreamer-supported source).
3. **I2C Devices**:
   - TCA9548A I2C Multiplexer (Address: `0x70`)
   - Dual DA7280 Haptic Drivers (Address: `0x4A`, connected to channels `0` and `1`).
4. **Audio Output**: Speaker or headphone jack for TTS announcements.

---

## Software Prerequisites & Installation

### 1. System Dependencies
Ensure your system has the necessary audio engines and build essentials installed:
```bash
sudo apt update
sudo apt install -y espeak-ng python3-pip python3-opencv
```

### 2. Python Libraries
Install the required Python packages (ensure PyTorch and Ultralytics are configured for your hardware, especially if using a Jetson device):
```bash
pip install ultralytics opencv-python smbus2 torch torchvision
```

---

## Configuration

You can configure parameters directly at the top of the `track_i.py` script:
- **Camera Resolution & FPS**: `WIDTH`, `HEIGHT`, `FPS`
- **YOLO Model**: `MODEL_PATH` (change to `.engine` for TensorRT optimization)
- **I2C Bus & Addresses**: `I2C_BUS = 7`, `TCA9548A_ADDR = 0x70`, `DA7280_ADDR = 0x4A`
- **TTS Settings**: `TTS_ENABLED = True`, `TTS_LANG = "en"` (or `"ko"`)

---

## Running the Application

Execute the script from your terminal with appropriate permissions (I2C and camera access):
```bash
python3 track_i.py
```

### Controls & Shutdown
- **GUI Window**: Click the **EXIT** button on the top-right, press `q`, `Q`, or `ESC`.
- **Terminal**: Press `q` or `Ctrl+C`.