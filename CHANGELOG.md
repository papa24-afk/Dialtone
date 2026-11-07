# Changelog

All notable changes to the Dialtone project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-07

### Added
- **Core Desktop Architecture**: Electron frontend powered by a high-performance Python Win32 modem bridge.
- **Huawei USB Dongle Support**: Initial verification and hardware integration for the Huawei K4201 (Vodafone K4201-I) modem.
- **Hardware Mode Switcher**: Automated SCSI pass-through CDB dispatcher (`110620...` and `1b00...`) that intercepts virtual CDFS/CD-ROM partitions and transitions dongles into Composite Serial Mode (`VID_12D1&PID_14FB`).
- **Permanent NVRAM Port Locking**: Capability to program modem NVRAM via `AT^SETPORT="A1,A2;1,2,3"` to persist AT and PC UI voice serial ports across system reboots.
- **Dynamic Serial Port Discovery**: Automatic detection of cellular AT command endpoints (`COM7`) and secondary voice PCM streaming endpoints (`COM6`) via Windows CDC ACM device descriptors.
- **Interactive USSD Terminal**: Full support for single and multi-line network USSD queries (`*124#`, `*110#`, etc.) with session continuity and numerical menu responses.
- **SMS Messaging Engine**: Complete inbound and outbound SMS pipeline using 3GPP AT text mode (`AT+CMGF=1`), with unsolicited indication (`+CMTI`) handling and local thread grouping.
- **PCM Voice Audio Pipeline**: Direct Win32 serial streaming for 16-bit 8000Hz mono PCM audio over secondary modem endpoints, synchronized with Windows Multimedia waveOut and waveIn subsystems with 20ms frame alignment (320 bytes).
- **Local SQLite Persistence**: Thread-safe storage for contacts, call history, message threads, and audio hardware preferences with automatic phone number normalization.
- **Offline Self-Contained UI**: Dark-themed desktop dashboard with real-time SSE telemetry, cellular status header, dialpad, SMS conversations, USSD console, device inspection, and audio diagnostics.

### Verified Hardware
- Huawei K4201 (HSPA+ USB Stick) on Telecel Ghana (Vodafone GH) network.
- Windows 11 (x64) and Windows 10 (x64) compatibility via native `usbser.sys` drivers.
