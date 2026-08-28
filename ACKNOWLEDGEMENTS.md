# Acknowledgements

This Home Assistant integration is an independent implementation built around the
public Asterisk Manager Interface (AMI) protocol and the Grandstream HT503 local
web interface.

The project was motivated in part by the Home Assistant Asterisk integration by
TECH7Fox and by the Asterisk project documentation/source tree. No Asterisk source
code is embedded in this integration.

The HT503 status reader targets the legacy status layout exposed by the device at
`/cgi-bin/index` after login through `/cgi-bin/dologin`.
