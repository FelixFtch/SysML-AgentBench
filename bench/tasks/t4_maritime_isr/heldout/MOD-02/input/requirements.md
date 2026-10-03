# MOD-02 — synthetic, not an RTX specification

Package name stays VesselAlign. Edit the baseline.

Add part usage ais of AisReceiver inside vessel. Connect vessel.ais.tracks to vessel.processor.trackIn.
Add requirement definition TimeAlign whose doc comment says tracks and imagery share a timestamp.
Keep the camera connection. Do not invent numeric limits.
