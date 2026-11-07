# Dialtone Installation & Build Guide

This document describes how to set up, build, and run Dialtone on Windows 10 and Windows 11 (64-bit).

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Running from Source](#running-from-source)
3. [Building Standalone Distribution](#building-standalone-distribution)
4. [Hardware Requirements](#hardware-requirements)
5. [Windows Driver Requirements](#windows-driver-requirements)

---

## 1. Prerequisites

To run or build Dialtone from source, ensure you have:
- **Operating System:** Windows 10 (64-bit) or Windows 11 (64-bit).
- **Node.js:** Node.js 18.x or later with `npm`.
- **Python:** Python 3.10 to 3.14 (64-bit).
- **Git:** Git for Windows.

Dialtone's core backend utilizes the Python standard library and low-level Win32 `ctypes` bindings (`kernel32.dll`, `winmm.dll`), which eliminates complex C++ compiler toolchains during standard execution.

---

## 2. Running from Source

1. **Clone the repository:**
   ```bash
   git clone https://github.com/papa24-afk/Dialtone.git
   cd Dialtone
   ```

2. **Install Node dependencies:**
   ```bash
   npm install
   ```

3. **Install optional Python dependencies:**
   The backend runs using standard Python libraries. For dynamic COM port auto-discovery, install `pyserial`:
   ```bash
   pip install pyserial
   ```

4. **Start the application:**
   Launch Dialtone with npm:
   ```bash
   npm start
   ```
   Electron will launch the application window and automatically initialize the Python background modem bridge on `http://127.0.0.1:8765`.

---

## 3. Building Standalone Distribution

To distribute Dialtone to systems without Python or development tools installed:

1. **Install PyInstaller:**
   ```bash
   pip install pyinstaller
   ```

2. **Compile the standalone backend binary:**
   ```bash
   pyinstaller --noconfirm --onefile --clean \
     --distpath "src/backend" \
     --workpath "build/backend" \
     "src/backend/modem_bridge.py"
   ```
   This generates `src/backend/modem_bridge.exe`, a self-contained 64-bit binary containing the Python runtime, SQLite manager, and audio router.

3. **Package with Electron:**
   When `modem_bridge.exe` is present inside `src/backend`, `main.cjs` automatically detects and launches the standalone binary instead of requiring a system Python executable.

---

## 4. Hardware Requirements

- **Cellular USB Modem:** A compatible 3G/4G USB modem (e.g., Huawei K4201). See [SUPPORTED_MODEMS.md](SUPPORTED_MODEMS.md) for detailed compatibility.
- **Active SIM Card:** A functional mini/micro/nano SIM card with active cellular voice, SMS, and data service.
- **Audio Peripherals:** Standard laptop speakers/headphones and microphone for call audio.

---

## 5. Windows Driver Requirements

- On Windows 10 and Windows 11, the standard Microsoft CDC-ACM USB Serial driver (`usbser.sys`) is built into the OS.
- When a compatible modem is switched into Composite Serial Mode (`VID_12D1&PID_14FB`), Windows automatically binds `usbser.sys` to each serial interface, exposing standard virtual COM ports (e.g., `COM7` for AT commands and `COM6` for PCM audio).
- If your device defaults to Mobile Broadband mode (`MBIM`), consult [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for switching instructions.
