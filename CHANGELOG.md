# Changelog

## 2.0.0-beta.3 - 2026-08-28

- Safer reconfigure/reauth flows: stored AMI and HT503 passwords are preserved when the password field is left blank and are no longer sent back to the frontend as suggested values.
- Duplicate protection also matches host/port entries created by the original v1 integration.
- Endpoint-discovery event listeners are removed after each discovery run.
- `asterisk.send_action` is registered integration-wide, validates calls and can return the direct AMI response.
- AMI reconnect health check reduced to 5 seconds.
- Added HACS and Hassfest GitHub validation workflow.
- Added local mock tests for Asterisk 18-style AMI discovery and HT503 FXS/FXO parsing during build validation.

## 2.0.0-beta.2 - 2026-08-28

- Full Home Assistant GUI setup for Asterisk AMI.
- AMI connection validation before saving.
- Reconfigure and re-authentication flows.
- Automatic PJSIP and legacy chan_sip endpoint discovery.
- Multi-select endpoint picker with optional manual endpoints.
- Device state, registration, connected-line and DTMF entities.
- Generic `asterisk.send_action` service.
- Optional Grandstream HT503 local monitoring in a dedicated GUI step.
- FXS/FXO state, user ID and registration entities.
- Portuguese and English translations.
- Diagnostics with credential redaction.
- Blocking AMI calls moved off the Home Assistant event loop.
