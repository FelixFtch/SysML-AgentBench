# GEN-02 — synthetic, not an RTX specification

Package name: UavSearch

1. Port definitions TrackPort, ImageryPort, and LinkPort.
2. Part definition Radar with port tracks of type TrackPort.
3. Part definition Camera with port imagery of type ImageryPort.
4. Part definition Processor with ports trackIn of type TrackPort, imageryIn of type ImageryPort, and uplink of type LinkPort.
5. Part definition Radio with ports fromProcessor and toShore, both of type LinkPort.
6. Part usage uav containing searchRadar, eoCamera, processor, and radio.
7. Connections: uav.searchRadar.tracks to uav.processor.trackIn; uav.eoCamera.imagery to uav.processor.imageryIn; uav.processor.uplink to uav.radio.fromProcessor.
Do not invent numeric limits.
