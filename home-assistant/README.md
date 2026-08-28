# Home Assistant Asterisk AMI + HT503 beta

Test package for the Home Assistant integration developed for Asterisk/Issabel and Grandstream HT503.

## Version

`2.0.0-beta.2`

## What is included

- GUI AMI connection setup and validation.
- PJSIP and legacy chan_sip discovery.
- Multi-select extension picker plus manual endpoints.
- Device-state, registration, connected-line and DTMF entities.
- Generic `asterisk.send_action` service.
- Dedicated optional HT503 GUI step.
- HT503 FXS/FXO state, User ID and registration.
- Portuguese and English translations.
- Diagnostics with passwords redacted.

## Test installation

Download `ha-asterisk-ami-ht503-v2.0.0-beta.2.zip`, extract it, and copy `custom_components/asterisk` into the Home Assistant `/config/custom_components/` directory. Restart Home Assistant, then add **Asterisk AMI + HT503** from Settings > Devices & services.

This beta branch intentionally leaves the repository `master` branch unchanged while the integration is tested.
