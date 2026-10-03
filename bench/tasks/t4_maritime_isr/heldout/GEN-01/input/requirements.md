# GEN-01 — synthetic, not an RTX specification

Package name: UsvLink

Write one SysML v2 package. Use these names and no others.

1. Port definitions ImageryPort and LinkPort.
2. Part definition Camera with port imagery of type ImageryPort.
3. Part definition Processor with port imageryIn of type ImageryPort and port uplink of type LinkPort.
4. Part definition Radio with port fromProcessor of type LinkPort and port toShore of type LinkPort.
5. Part definition CommandShip with port fromUsv of type LinkPort.
6. Part usage usv containing part usages camera, processor, and radio of those definitions.
7. Part usage commandShip of CommandShip.
8. Connections: usv.camera.imagery to usv.processor.imageryIn; usv.processor.uplink to usv.radio.fromProcessor; usv.radio.toShore to commandShip.fromUsv.
Do not invent numeric limits.
