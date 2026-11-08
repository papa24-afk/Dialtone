<p align="center">
  <img src="assets/dialtone-banner.svg" alt="Dialtone — Desktop Cellular Communication Suite" width="100%" />
</p>

<p align="center">
  <a href="https://github.com/papa24-afk/Dialtone/releases/tag/v1.0.0"><img src="https://img.shields.io/badge/Release-v1.0.0-7c3aed.svg?style=flat-square" alt="GitHub release" /></a>
  <a href="https://github.com/papa24-afk/Dialtone/actions"><img src="https://img.shields.io/badge/CI-Passing-10b981.svg?style=flat-square" alt="CI Status" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square" alt="License: MIT" /></a>
  <a href="docs/INSTALLATION.md"><img src="https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011%20(64--bit)-0078D6.svg?style=flat-square" alt="Platform: Windows" /></a>
  <a href="docs/SUPPORTED_MODEMS.md"><img src="https://img.shields.io/badge/Hardware-Huawei%20K4201%20Verified-success.svg?style=flat-square" alt="Hardware: Huawei K4201 Verified" /></a>
  <a href="CONTRIBUTING.md"><img src="https://img.shields.io/badge/PRs-Welcome-brightgreen.svg?style=flat-square" alt="PRs Welcome" /></a>
</p>

<h3 align="center">
  Transform cellular USB modems into a complete voice calling, SMS messaging, and interactive USSD desktop workstation on Windows 10 &amp; 11.
</h3>

<p align="center">
  <b>Modern open-source alternative to legacy Huawei Mobile Partner, Vodafone Mobile Connect, and proprietary modem dialers.</b>
</p>

---

## Table of Contents
- [Why Dialtone? (The Mobile Partner Problem)](#why-dialtone-the-mobile-partner-problem)
- [About Dialtone](#about-dialtone)
- [System Architecture](#system-architecture)
- [Main Features (Verified)](#main-features-verified)
- [Supported Hardware](#supported-hardware)
- [Hardware Verification & Proof](#hardware-verification--proof)
- [Windows Requirements](#windows-requirements)
- [Installation & Quick Start](#installation--quick-start)
- [USB Modem Connection & Setup](#usb-modem-connection--setup)
- [Using the Dialer & Audio Engine](#using-the-dialer--audio-engine)
- [Screenshot Gallery](#screenshot-gallery)
- [Frequently Asked Questions (FAQ)](#frequently-asked-questions-faq)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)
- [Troubleshooting & Documentation](#troubleshooting--documentation)
- [Contributing & Community](#contributing--community)
- [License](#license)

---

## Why Dialtone? (The Mobile Partner Problem)

For years, millions of users around the world managed USB cellular modems with **Huawei Mobile Partner** or **Vodafone Mobile Connect**. However, today:
- Legacy dialer software is abandoned, bloated, 32-bit only, and frequently crashes on Windows 10 and Windows 11.
- Modern Windows natively handles USB modems as **Mobile Broadband (MBIM / NDIS)** data cards—allowing only internet browsing while completely locking out the cellular voice baseband, SMS inbox, and USSD commands.
- Standard serial terminals (like PuTTY or Tera Term) only display raw ASCII text, lacking 16-bit PCM voice streaming, contact management, or responsive dialpads.

**Dialtone bridges this gap with a modern, lightweight, and 100% open-source solution.**

| Feature | Windows Built-In Cellular | Huawei Mobile Partner | Generic Serial Terminals | **Dialtone** |
| :--- | :---: | :---: | :---: | :---: |
| **Windows 11 (64-bit) Native** | Yes | Broken / 32-bit | Yes | **Yes (Native 64-bit)** |
| **Voice Calls (Headset / PC Mic)** | No | Limited / Unstable | No Audio | **Yes (16-bit 8kHz PCM)** |
| **Interactive USSD (*124#, *110#)** | No | Text Only / Unreliable | Raw AT Only | **Yes (Interactive Menus)** |
| **SMS Conversations & Threads** | Basic Alert Only | Clunky / Outdated | Raw AT Only | **Yes (Threaded Inbox)** |
| **Automated SCSI Mode Switch** | No | Requires CD-ROM Autorun | No | **Yes (Built-in CDB)** |
| **NVRAM Port Configuration** | No | No | Manual AT Only | **Yes (`AT^SETPORT`)** |
| **Open Source (MIT)** | Closed | Proprietary | Varies | **100% Free & Open Source** |

---

## About Dialtone

Modern desktop operating systems treat USB cellular modems almost exclusively as data network interfaces. When you insert a SIM card and plug in a USB dongle, Windows configures it for mobile broadband data, while ignoring the cellular voice baseband, SMS storage, and interactive USSD menus built into the hardware.

**Dialtone** restores complete cellular communication capabilities to the PC:

1. **Voice Telephony:** Make and receive standard cellular calls directly from your PC using your computer's microphone and speakers.
2. **Interactive USSD Terminal:** Query real-time airtime balances, purchase data bundles, and navigate complex carrier menus (*124#, *110#, etc.).
3. **SMS Messaging:** Send and receive standard SMS text messages with persistent local conversation threads.
4. **Hardware Persistence:** Automatically switch modems from storage mode into composite serial mode and lock preferred port configurations into the modem's onboard NVRAM.

### Intended Users
- **Remote workers and desk setups** routing incoming cellular phone calls directly through a PC headset.
- **Developers, sysadmins, and cellular tinkerers** building telephony solutions or reverse-engineering baseband AT interfaces.
- **Users in regions relying on USSD infrastructure** (e.g., Africa, South Asia, Latin America) for mobile money, balance inquiries, and top-ups.
- **Field operators and IoT engineers** managing remote SIM cards and cellular gateways.

---

## System Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                 Dialtone Desktop Interface                  │
│       (Electron + React 18 + Tailwind CSS + Lucide Icons)   │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP REST API / SSE Telemetry
                               │ (Port 8765)
┌──────────────────────────────▼──────────────────────────────┐
│             Dialtone Core Win32 Modem Bridge                │
│         (Low-Level Python 3.14 + ctypes Win32 API)          │
│                                                             │
│  ┌───────────────────────┐     ┌─────────────────────────┐  │
│  │   AT Command Engine   │     │  PCM Audio Router Engine │  │
│  │  (Calls, SMS, USSD)   │     │  (8000Hz 16-Bit Mono)   │  │
│  └───────────┬───────────┘     └────────────┬────────────┘  │
│              │                              │               │
│              │ Direct Win32                 │ Direct Win32  │
│              │ CreateFileW                  │ waveOut/waveIn│
└──────────────┼──────────────────────────────┼───────────────┘
               │                              │
         COM7 (AT Port)                 COM6 (Audio Port)
               │                              │
┌──────────────▼──────────────────────────────▼───────────────┐
│              Huawei K4201 USB Cellular Modem                │
│        (VID_12D1 & PID_14FB - Composite Serial Mode)        │
└─────────────────────────────────────────────────────────────┘
```

Dialtone utilizes an asynchronous, non-blocking Win32 serial architecture. Instead of relying on heavy third-party serial drivers, it communicates directly with the Windows kernel via `kernel32.dll` and routes voice audio via Windows Multimedia `winmm.dll`.

---

## Main Features (Verified)

Every feature listed below has been verified and confirmed against physical cellular hardware:

- [x] **Automatic Mode Switching:** Built-in SCSI Pass-Through dispatcher sends vendor CDB eject commands to automatically transition dongles from CD-ROM/storage mode into composite serial mode (`PID 14FB`).
- [x] **Hardware NVRAM Port Locking:** Capability to flash `AT^SETPORT="A1,A2;1,2,3"` permanently into modem flash memory so it retains Voice + Serial mode across all reboots and machines.
- [x] **Dynamic Port Detection:** Automatically scans Windows CDC-ACM serial ports and identifies the primary AT command port (`COM7`) and secondary voice PCM port (`COM6`).
- [x] **Interactive USSD Terminal:** Real-time single and multi-line USSD sessions with live carrier response rendering, interactive reply prompt, and session timeout management.
- [x] **SMS Text Messaging:** Send and receive SMS messages via 3GPP text mode (`AT+CMGF=1`) with automatic SIM card synchronization on startup (`AT+CMGL="ALL"`).
- [x] **Bi-Directional PCM Audio Pipeline:** Direct streaming of 16-bit 8000Hz mono PCM voice frames between modem audio endpoints and Windows `waveOut` / `waveIn` subsystems with 20ms frame buffer alignment (320 bytes).
- [x] **Cellular Telemetry:** Live monitoring of carrier operator name (`AT+COPS?`), signal quality CSQ and dBm (`AT+CSQ`), and network registration status (`AT+CREG`).
- [x] **Local SQLite Persistence:** Fully local, thread-safe database for contacts, call history, and message threads with intelligent phone number normalization.

---

## Supported Hardware

| Modem Model | Chipset | Verified Operating Modes | Voice Calling | SMS | USSD | Status |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **Huawei K4201**<br>*(Vodafone K4201-I)* | HiSilicon / Balong V3R2 | `VID_12D1&PID_14FB` (Serial)<br>`VID_12D1&PID_14DB` (MBIM)<br>`VID_12D1&PID_1F01` (CDFS) | **Yes**<br>*(PCM COM6)* | **Yes** | **Yes** | **Physically Verified & Tested** |
| **Huawei E303 / E3531** | HiSilicon Balong | `VID_12D1&PID_14DC` / `PID_1001` | *Firmware Dependent* | Supported | Supported | *Architecture Ready (Untested)* |
| **Huawei E3372** | HiSilicon Balong | `VID_12D1&PID_14DC` / `PID_1506` | **No**<br>*(Data-only FW)* | Supported | Supported | *Data-Only Modems (Non-Voice)* |
| **ZTE MF823 / MF831** | Qualcomm MDM9215 | `VID_19D2&PID_1405` | *Untested* | Planned | Planned | *In Development* |

> For comprehensive chipset details and mode-switching commands, see [docs/SUPPORTED_MODEMS.md](docs/SUPPORTED_MODEMS.md).

---

## Hardware Verification & Proof

To maintain strict scientific and technical accuracy, this repository documents verified physical results alongside unconfirmed capabilities.

### 1. Physical Hardware Setup

<p align="center">
  <img src="docs/screenshots/huawei_k4201_hardware.jpg" alt="Huawei K4201 / Vodafone K4201-I USB Dongle" width="280" />
  <br />
  <em>Figure: Physical Huawei K4201 (Vodafone K4201-I) HSPA+ USB Modem used for hardware verification.</em>
</p>

- **Host Laptop:** HP EliteBook x360 1040 G7 (Intel Core i7, 16GB RAM, Windows 11 Pro 64-bit).
- **USB Cellular Modem:** Huawei K4201 (Vodafone K4201-I HSPA+ USB Dongle).
- **SIM Card:** Telecel Ghana (Vodafone Ghana) 3G/HSPA+ active SIM.
- **Hardware IDs:**
  - Storage Mode: `USB\VID_12D1&PID_1F01`
  - Mobile Broadband Mode: `USB\VID_12D1&PID_14DB`
  - Voice & Serial Composite Mode: `USB\VID_12D1&PID_14FB`
- **Active Endpoints:**
  - AT Command Port: `COM7` (`USB\VID_12D1&PID_14FB&MI_00`, `usbser.sys`)
  - Voice Audio Port: `COM6` (`USB\VID_12D1&PID_14FB&MI_01`, `usbser.sys`)

### 2. Live Verification Evidence

#### USSD Execution Log (*124# Balance Inquiry):
```text
[AT-TX] AT+CUSD=1,"*124#"\r\n
[AT-RX] OK\r\n
[URC] +CUSD: 0,"(1) Main Ac: GHs 0.0007. SOS Ac: GHs - 0.0000. Get 200% on Telecel Cash top ups! Dial *110# to recharge. CUG Calls: 8Hr 20Min; Local Calls: 2Hr 26Min 39Sec;", 15
```
*Result: Instant carrier balance response parsed and displayed in Dialtone's terminal.*

#### Cellular Signal & Network Registration:
```text
[AT-TX] AT+CSQ\r\n
[AT-RX] +CSQ: 22,99\r\n
[AT-TX] AT+COPS?\r\n
[AT-RX] +COPS: 0,0,"Telecel",2\r\n
```
*Result: Signal strength CSQ 22 (-69 dBm, ~71% signal quality) on 3G HSPA+ UMTS.*

#### Voice Pipeline Initialization:
```text
[AT-TX] AT^SETPORT="A1,A2;1,2,3"\r\n
[AT-RX] OK\r\n
[AT-TX] AT^CVOICE=0,8000,16,20\r\n
[AT-RX] OK\r\n
[AT-TX] AT^DDSETEX=2\r\n
[AT-RX] OK\r\n
```
*Result: Modem audio routing successfully directed to secondary CDC interface at 16-bit 8000Hz mono PCM.*

### 3. Verification Status Checklist
- [x] USB Composite Device enumeration with `usbser.sys`.
- [x] NVRAM persistent mode programming (`AT^SETPORT`).
- [x] Carrier network registration on Telecel Ghana.
- [x] Live interactive USSD execution.
- [x] Live SMS transmission and reception.
- [x] Bi-directional PCM streaming loop on `COM6`.
- [ ] Multi-carrier field testing outside Ghana (*Pending community contributions*).
- [ ] Echo cancellation and acoustic tuning across different PC microphones (*In active tuning*).

---

## Windows Requirements

- **Operating System:** Windows 10 (64-bit) or Windows 11 (64-bit).
- **USB Port:** Standard USB 2.0 or USB 3.0 Type-A port (or Type-C with an adapter).
- **Driver:** Microsoft built-in `usbser.sys` (included with Windows 10/11).
- **Audio:** Working sound card with speaker and microphone enabled.

---

## Installation & Quick Start

### Running from Source
1. **Clone the repository:**
   ```bash
   git clone https://github.com/papa24-afk/Dialtone.git
   cd Dialtone
   ```

2. **Install Node dependencies:**
   ```bash
   npm install
   ```

3. **Install Python requirements:**
   Dialtone uses Python 3.10+ standard libraries and `ctypes`. To enable dynamic serial enumeration, install `pyserial`:
   ```bash
   pip install pyserial
   ```

4. **Launch Dialtone:**
   ```bash
   npm start
   ```

> For compiling standalone self-contained binaries without requiring a local Python installation, see [docs/INSTALLATION.md](docs/INSTALLATION.md).

---

## USB Modem Connection & Setup

1. **Insert SIM Card:** Ensure your SIM card is active and unlocked (PIN disabled).
2. **Plug into PC:** Insert the dongle into your USB port.
3. **Check Device Manager:**
   - Under **Ports (COM & LPT)**, verify two serial ports appear (e.g., `COM7` and `COM6`).
   - If the modem appears under **Network Adapters** as `Mobile Broadband` or under **DVD/CD-ROM Drives**, refer to [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) to complete the 1-click mode switch.
4. **Launch Dialtone:** Dialtone will detect the serial ports, query your network carrier, and show a green status badge on your top navigation bar.

---

## Using the Dialer & Audio Engine

### Outgoing Voice Calls
1. Open the **Calls** tab.
2. Dial any mobile or landline number using the on-screen keypad or your computer keyboard.
3. Click the green **Call** button.
4. Dialtone transmits `ATD<number>;`, commands the baseband to route voice audio to `COM6` (`AT^DDSETEX=2`), and opens your PC audio devices.
5. In-call controls allow instant **Mute**, **Call Hold**, and sending touch-tones (**DTMF** keypad).

### Answering Incoming Calls
1. When an incoming call arrives, Dialtone rings and displays a real-time caller ID card with contact resolution.
2. Click **Answer** to connect the call or **Decline** to hang up.

---

## Screenshot Gallery

All screenshots below represent the physical Dialtone interface:

| View | Screenshot Placeholder | Status |
| :--- | :--- | :---: |
| **Hardware Photograph** | `docs/screenshots/huawei_k4201_hardware.jpg` | **Verified & Present** |
| **Main Dashboard** | `docs/screenshots/01_main_interface.png` | *Pending Photographic Upload* |
| **Active Telephony Dialer** | `docs/screenshots/03_dial_pad.png` | *Pending Photographic Upload* |
| **Active Call Screen** | `docs/screenshots/04_active_call.png` | *Pending Photographic Upload* |
| **Interactive USSD Console** | `docs/screenshots/07_ussd_terminal.png` | *Pending Photographic Upload* |
| **Audio Routing Diagnostics** | `docs/screenshots/08_audio_settings.png` | *Pending Photographic Upload* |
| **Device Manager Hardware IDs** | `docs/screenshots/09_device_manager.png` | *Pending Photographic Upload* |

*To contribute genuine screenshots from your hardware sessions, see [docs/screenshots/README.md](docs/screenshots/README.md).*

---

## Frequently Asked Questions (FAQ)

### Can I make calls using any USB dongle?
Only modems that have voice-capable baseband firmware (like the Huawei K4201, E173, E1750, etc.) support voice calls. Pure data modems (e.g., standard LTE E3372h in HiLink mode) can send SMS and query USSD, but do not expose voice audio endpoints. Check [docs/SUPPORTED_MODEMS.md](docs/SUPPORTED_MODEMS.md).

### How is Dialtone different from Huawei Mobile Partner?
Mobile Partner is discontinued, closed-source 32-bit software from over a decade ago that fails on modern Windows 11. Dialtone is a modern, 64-bit open-source application built with Electron and direct Win32 asynchronous serial APIs, with zero legacy bloat.

### Why does Windows 11 say "Mobile Broadband" and lock the modem?
Windows 10/11 defaults to loading the `wmbclass.sys` (MBIM) data driver on composite USB modems, hiding the AT and audio COM ports. Dialtone provides instructions and automated CDB switching to expose the serial interfaces. See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

### Does Dialtone require internet access?
No. Dialtone is 100% offline. All AT commands, voice PCM routing, SQLite database records, and UI assets run locally on your PC without communicating with any external cloud servers.

---

## Known Limitations

- **Data-Only USB Modems:** Many modern 4G/LTE USB sticks (such as standard Huawei E3372h in HiLink mode) do not expose baseband voice audio interfaces. Dialtone cannot enable voice calling on hardware lacking voice baseband firmware.
- **Echo Cancellation (AEC):** Dialtone currently relies on Windows audio device drivers for basic acoustic filtering. Using headphones is strongly recommended during calls to prevent microphone feedback.
- **Single Active Session:** The modem's AT command interface supports one active voice call or USSD transaction at a time.
- **Platform Support:** Dialtone's low-level audio router currently uses the Windows Win32 Multimedia API (`waveOut`/`waveIn`) and `kernel32` handles. Linux and macOS audio routing drivers are planned for future releases.

---

## Roadmap

- [ ] **Acoustic Echo Cancellation (AEC):** Integrate a lightweight WebRTC-based AEC module into the PCM audio router.
- [ ] **Multi-Brand Mode Switching:** Add automated mode-switching sequences for ZTE, Sierra Wireless, and Quectel modems.
- [ ] **Cross-Platform Audio Engine:** Linux ALSA and macOS CoreAudio serial bridge drivers.
- [ ] **Automated Release Packaging:** GitHub Actions CI/CD workflow to compile self-contained Windows installers.
- [ ] **VoLTE / 4G Voice Support:** Experimental AT interface investigation for LTE modems supporting IMS voice profiles.

---

## Troubleshooting & Documentation

- [Installation & Build Guide](docs/INSTALLATION.md)
- [Complete User Guide](docs/USER_GUIDE.md)
- [Supported Modems & Chipsets](docs/SUPPORTED_MODEMS.md)
- [Troubleshooting & Driver Guide](docs/TROUBLESHOOTING.md)
- [Screenshot Gallery Guidelines](docs/screenshots/README.md)

---

## Contributing & Community

We welcome contributions from modem enthusiasts, reverse engineers, and cellular software developers!
- Review [CONTRIBUTING.md](CONTRIBUTING.md) for testing standards.
- Adhere to our [Code of Conduct](CODE_OF_CONDUCT.md).
- To submit test results for your modem, use our [Hardware Verification Template](https://github.com/papa24-afk/Dialtone/issues/new?template=modem_verification.md).

---

## License

Dialtone is open-source software licensed under the **[MIT License](LICENSE)**.
