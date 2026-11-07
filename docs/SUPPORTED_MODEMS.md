# Supported Modems & Hardware Compatibility Guide

This document maintains the hardware compatibility list, chipset specifications, and configuration details for USB cellular modems used with Dialtone.

> **Important Note on Cellular Voice Support:** Not all cellular USB dongles support voice calls. Many newer 4G/LTE USB modems operate exclusively as mobile broadband data cards (NDIS/CDC-ECM/MBIM) without internal voice baseband routing or voice AT commands enabled in firmware. **Dialtone does not claim voice capabilities for data-only modems.**

---

## 1. Hardware Compatibility Status

| Manufacturer | Model | Commercial Brand | Hardware IDs (Vendor / Product) | SMS Support | USSD Support | Voice Call Support | Verification Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **Huawei** | **K4201** | Vodafone K4201-I | `VID_12D1&PID_14FB` (Serial Mode)<br>`VID_12D1&PID_14DB` (Broadband Mode)<br>`VID_12D1&PID_1F01` (CDFS Mode) | Verified | Verified | Verified (PCM COM6) | **Physically Verified & Tested** |
| **Huawei** | E303 / E3531 | Hilink / Stick | `VID_12D1&PID_14DC` / `PID_1001` | Architecture Ready | Architecture Ready | Firmware Dependent | Community Testing Needed |
| **Huawei** | E3372 | 4G LTE USB Stick | `VID_12D1&PID_14DC` / `PID_1506` | Architecture Ready | Architecture Ready | Data-Only (Non-Voice FW) | Community Testing Needed |
| **ZTE** | MF823 / MF831 | 4G USB Modem | `VID_19D2&PID_1405` / `PID_1403` | In Development | In Development | Untested | Community Testing Needed |
| **Sierra Wireless** | AirCard 313U | 3G/4G USB Modem | `VID_1199&PID_68AA` | In Development | In Development | Model Dependent | Community Testing Needed |

---

## 2. Deep Dive: Huawei K4201 (Vodafone K4201-I)

The **Huawei K4201** is the primary reference modem developed and tested with Dialtone.

### Technical Profile
- **Chipset:** HiSilicon Balong V3R2 / Qualcomm baseband.
- **Form Factor:** USB 2.0 Dongle with standard SIM slot.
- **Networks:** HSPA+ / UMTS (900/2100 MHz) and GSM / GPRS / EDGE (850/900/1800/1900 MHz).
- **Audio Interface:** Secondary CDC-ACM serial port (`COM6`) carrying 16-bit 8000Hz mono PCM audio frames.
- **AT Command Port:** Primary CDC-ACM serial port (`COM7`).

### USB Operating Modes

| Mode | USB VID & PID | Driver Assigned | Description |
| :--- | :--- | :--- | :--- |
| **CD-ROM / Storage** | `VID_12D1&PID_1F01` | `usbstor.sys` (Mass Storage) | Initial mode on power-up presenting virtual CD containing Vodafone driver installer. |
| **Mobile Broadband** | `VID_12D1&PID_14DB` | `wmbclass.sys` (MBIM) | Windows 10/11 default data broadband mode. Voice and AT ports are not exposed. |
| **Composite Voice & Serial** | `VID_12D1&PID_14FB` | `usbser.sys` (USB Serial) | Target Dialtone mode. Exposes AT command interface (`MI_00`) and PCM voice streaming interface (`MI_01`). |

---

## 3. Modem Modes: Stick vs. HiLink

When selecting a cellular modem for desktop communication, understanding the firmware mode is vital:

### 1. Traditional "Stick" Mode (Recommended for Dialtone)
- Presents direct virtual serial COM ports (`usbser`).
- Standard Hayes AT command set (`ATD`, `ATA`, `AT+CMGS`, `AT+CUSD`).
- Permits low-level baseband audio DSP interaction.
- Ideal for Dialtone's calling, SMS, and USSD architecture.

### 2. "HiLink" Mode (Router / Web UI Mode)
- Presents the modem to Windows as an Ethernet network card (CDC-ECM / RNDIS) at `192.168.8.1`.
- Managed via an internal web dashboard.
- Traditional serial COM ports and voice endpoints are disabled or locked behind proprietary HTTP APIs.

---

## 4. How to Inspect Your Modem's Hardware IDs & COM Ports

To identify your modem's current state on Windows:

1. Press `Win + X` and select **Device Manager**.
2. Check the following sections:
   - **Ports (COM & LPT):** Look for `USB Serial Device` or `Huawei Mobile Connect - 3G PC UI Interface`. Note the COM port number (e.g., `COM7`).
   - **Network adapters:** Look for `Cellular` or `Mobile Broadband Adapter` (indicates MBIM/Broadband mode).
   - **DVD/CD-ROM drives:** Look for virtual carrier drives (indicates Mass Storage mode).
3. To view Hardware IDs:
   - Right-click the device -> **Properties** -> **Details** tab.
   - In the Property drop-down, select **Hardware Ids**.
   - You will see strings like `USB\VID_12D1&PID_14FB&REV_0102&MI_00`.

---

## 5. Mode Switching & NVRAM Persistence

Dialtone incorporates an automated mode switcher that dispatches SCSI commands to move modems out of storage mode into composite serial mode:

```text
SCSI Eject / Mode-Switch Sequences:
1. 11 06 20 00 00 01 00 00 00 00 00 00 00 00 00 00
2. 11 06 00 00 00 00 00 00 00 00 00 00 00 00 00 00
3. 1b 00 00 00 02 00 00 00 00 00 00 00 00 00 00 00
```

### Permanent NVRAM Configuration (Huawei)
To lock a Huawei modem permanently into Serial + Voice mode across all PCs without requiring mode switching on each boot, Dialtone programs the modem's onboard flash memory:
```text
AT^SETPORT="A1,A2;1,2,3"
```
- `A1`: Virtual CD-ROM
- `A2`: MicroSD Reader
- `1`: 3G Modem Interface
- `2`: 3G PC UI / Voice Interface
- `3`: Diagnostic Interface
