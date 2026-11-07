# Contributing to Dialtone

Thank you for your interest in contributing to **Dialtone**! 

Dialtone is a real-world, hardware-oriented open-source project designed to bridge standard cellular USB modems with modern desktop operating systems for calls, SMS, and USSD. Because cellular modem firmware, baseband commands, and audio routing vary significantly across manufacturers and carriers, **rigorous verification and technical precision** are central to this project.

---

## Code of Conduct

We expect all contributors to adhere to a welcoming, respectful, and collaborative standard of conduct. Please treat fellow maintainers and users with empathy and professional respect.

---

## How Can You Contribute?

### 1. Hardware Verification & Device Testing
Modem compatibility is our greatest community need. If you own a USB cellular dongle (Huawei, ZTE, Sierra Wireless, Quectel, SIMCom, etc.):
- Test modem detection and mode-switching with Dialtone.
- Document the USB `VID` and `PID` in both storage and modem states.
- Verify AT command responses (`AT+CGMM`, `AT+CGMR`, `AT+CSQ`, `AT+COPS?`).
- Test voice audio capabilities (`AT^CVOICE=?`, secondary PCM COM ports).
- Submit a PR updating [`docs/SUPPORTED_MODEMS.md`](docs/SUPPORTED_MODEMS.md) with your exact findings.

> **Rule for Hardware Reports:** Never claim a modem supports voice or calls unless you have verified real audio transmission over physical hardware. Clearly distinguish tested features from unconfirmed ones.

### 2. Reporting Issues
When filing an issue:
1. Specify your **operating system version** (e.g., Windows 11 Build 22631).
2. State the **exact modem model**, hardware version, and carrier.
3. Include the USB Hardware IDs from Device Manager (`USB\VID_xxxx&PID_xxxx`).
4. Provide the relevant console logs from `backend.log`.
5. **Sanitize personal data**: Redact your phone numbers, IMSI numbers, IMEI numbers, and private contact information before submitting logs or screenshots.

### 3. Submitting Code Changes
1. Fork the repository and create your branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Follow existing code patterns:
   - Python code adheres to PEP 8 and maintains low-level Win32 ctypes safety.
   - Electron and UI code should remain lightweight, clean, and offline-first without unneeded heavy runtime dependencies.
3. Test your changes locally on hardware or with the provided hardware test scripts (`test_voice_at.py`, `test_sms_hardware.py`, `test_ussd_hardware.py`).
4. Commit with descriptive messages (e.g., `feat(modem): add ZTE MF823 mode switch command sequence`).
5. Open a Pull Request detailing what was changed and the physical test results.

---

## Security and Privacy Guidelines

- **Never commit live credentials, API keys, or SIM secrets.**
- **Never commit `.db` files or call histories.**
- All sample logs in documentation or tests must use standard dummy values (e.g., `+15551234567` or `*100#`).
