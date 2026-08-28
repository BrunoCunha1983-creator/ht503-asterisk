# Asterisk AMI + Grandstream HT503 for Home Assistant

A Home Assistant custom integration for **Asterisk / Issabel** using the
**Asterisk Manager Interface (AMI)**, with optional direct monitoring of a
**Grandstream HT503 FXS/FXO gateway**.

The integration is configured entirely from the Home Assistant GUI. No
`configuration.yaml` entries are required.

## Main features

- GUI setup and connection test for Asterisk AMI.
- GUI reconfiguration of AMI host, port and credentials.
- GUI options with automatic integration reload.
- Automatic PJSIP endpoint discovery through `PJSIPShowEndpoints`.
- Optional legacy `chan_sip` discovery through `SIPpeers`.
- Filter all endpoints or only selected extensions.
- Endpoint state sensors.
- Endpoint registered/available binary sensors.
- Connected-line/call sensors.
- Sent and received DTMF sensors.
- AMI connectivity entity and Asterisk version information.
- Generic `asterisk.send_action` Home Assistant action.
- Optional Grandstream HT503 direct status monitoring.
- HT503 FXS state, User ID and registration.
- HT503 FXO state, User ID and registration.
- HT503 connectivity entity.
- English and Portuguese UI translations.
- Diagnostics without exposing stored passwords.

## Home Assistant requirement

This branch targets Home Assistant **2026.6 or newer** because it uses the
current options-flow reload API.

## Before installing

If the original `TECH7Fox/asterisk-hass-integration` is installed, remove or
replace it before installing this integration. Both use the `asterisk` domain
and must not be installed side by side.

## Asterisk / Issabel AMI

AMI normally listens on TCP port **5038**. Create a dedicated manager user for
Home Assistant and allow the Home Assistant IP address.

On Issabel, put local overrides in the appropriate custom manager file rather
than editing generated configuration that Issabel may overwrite. A starting
configuration is:

```ini
[homeassistant]
secret = CHANGE_THIS_PASSWORD
deny = 0.0.0.0/0.0.0.0
permit = HOME_ASSISTANT_IP/255.255.255.255
read = system,call,command,dtmf,reporting,cdr,dialplan
write = system,call,command,originate
```

Reload the Asterisk manager after changing its configuration. For initial
troubleshooting you can temporarily use broader AMI permissions, then reduce
them once the actions required by your installation are confirmed.

Do **not** expose port 5038 directly to the Internet.

## Installation with HACS

1. In HACS open **Custom repositories**.
2. Add the GitHub repository URL containing this integration.
3. Select **Integration**.
4. Install **Asterisk AMI + HT503**.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration**.
7. Search for **Asterisk AMI + HT503**.

## GUI setup

### 1. Asterisk Manager Interface

Enter:

- Asterisk/Issabel host or IP.
- AMI port, normally `5038`.
- AMI username.
- AMI password.

The integration tests the login before continuing.

### 2. Extensions and entities

Choose whether to discover:

- PJSIP endpoints.
- Legacy `chan_sip` peers.

The integration asks Asterisk for the endpoint list and shows the results as a
**multi-select field** in the Home Assistant GUI. Leave the selection empty to
monitor every discovered endpoint from the enabled protocols, or select only
the extensions you want.

`Additional manual endpoints` accepts comma-separated values such as
`PJSIP/200,SIP/300`. A bare number such as `201` is treated as PJSIP. This is
useful for an endpoint that is temporarily offline and therefore missing from
discovery.

You can independently enable/disable device-state, registration,
connected-line and DTMF entities.

### 3. Grandstream HT503 (optional)

When **Enable Grandstream HT503** is switched on, the GUI opens a dedicated
HT503 step instead of showing its credentials all the time. Enter:

- HT503 local IP/hostname.
- HTTP port, normally `80`.
- HT503 administrator password.
- Poll interval, default `30` seconds.

The integration validates the HT503 before saving. It logs in through
`/cgi-bin/dologin` and reads the live status table from `/cgi-bin/index`.
The status table is parsed locally; no cloud service is used.

## Changing settings later

Open **Settings → Devices & services → Asterisk AMI + HT503**.

- Use **Reconfigure** to change the AMI server or credentials.
- Use **Configure / Options** to change endpoint discovery, selected extensions,
  entity types or HT503 settings.

Saving options automatically reloads the integration.

## HT503 entities

When enabled, one Grandstream HT503 device is created with entities similar to:

- `HT503 Connected`
- `HT503 FXS State`
- `HT503 FXS User ID`
- `HT503 FXS Registered`
- `HT503 FXO State`
- `HT503 FXO User ID`
- `HT503 FXO Registered`

This lets Home Assistant compare what the HT503 itself reports with what
Asterisk reports through AMI.

## `asterisk.send_action`

The integration exposes a generic Home Assistant action for advanced AMI use. It can optionally return Asterisk's direct AMI response to the caller.
Example:

```yaml
action: asterisk.send_action
data:
  action: PJSIPQualify
  parameters:
    Endpoint: "200"
```

The AMI manager user's `write` permissions determine which actions Asterisk
will accept.

## Security

- Keep AMI on the trusted LAN/VPN only.
- Use a dedicated AMI account for Home Assistant.
- Restrict `permit` to the Home Assistant address whenever practical.
- Use a strong AMI secret.
- The HT503 integration uses its legacy HTTP interface, so keep it on a trusted
  local network and do not expose it to the Internet.

## Technical references

- Asterisk Manager Interface (AMI).
- `PJSIPShowEndpoints` / `EndpointList` / `EndpointListComplete`.
- Asterisk `DeviceStateChange`, channel and DTMF events.
- Grandstream HT503 local status page.

## Status

`2.0.0-beta.3` is the test build with endpoint multi-selection, a dedicated HT503 GUI step, safer credential reconfiguration and AMI action responses. Test it on a non-critical Home Assistant instance before relying on it for automations that control calls.
