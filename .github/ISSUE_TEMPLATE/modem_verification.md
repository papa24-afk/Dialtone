---
name: Hardware Verification Report
about: Submit test results for a USB cellular modem model
title: '[HARDWARE] Verification: '
labels: hardware-verification
assignees: ''
---

## Device Information
- **Manufacturer**: [e.g. Huawei, ZTE, Sierra Wireless, Quectel]
- **Commercial Model**: [e.g. Huawei K4201, ZTE MF831]
- **Branded Carrier (if locked/customized)**: [e.g. Vodafone K4201-I, Airtel E173]
- **Firmware Version (from `AT+CGMR`)**: 

## USB Identification
- **Storage Mode USB ID**: `USB\VID_xxxx&PID_xxxx`
- **Serial / Active Mode USB ID**: `USB\VID_xxxx&PID_xxxx`
- **AT Command Port**: [e.g. COM3, COM7]
- **Secondary / Audio Port (if present)**: [e.g. COM4, COM6]

## Verification Checklist
- [ ] Modem recognized by Windows CDC-ACM (`usbser.sys`)
- [ ] Network registration successful (`AT+CREG?` / `AT+COPS?`)
- [ ] USSD session working (`*124#` or local carrier code)
- [ ] SMS send and receive verified (`AT+CMGS` / `AT+CMGL`)
- [ ] Outgoing voice call connected (`ATD`)
- [ ] Incoming voice call alert (`RING` / `+CLIP`)
- [ ] Voice audio heard through PC speakers
- [ ] Microphone voice transmitted to recipient

## Operating Environment
- **Host OS**: [e.g. Windows 11 Build 22631, Windows 10 x64]
- **Carrier / Country**: [e.g. Telecel / Ghana, EE / UK, Jio / India]
- **Network Generation**: [e.g. 2G GSM, 3G HSPA+, 4G LTE]

## Notes & Baseband Quirks
Describe any special mode-switching strings (`AT^SETPORT`, SCSI eject sequences) or firmware quirks required for this device.
