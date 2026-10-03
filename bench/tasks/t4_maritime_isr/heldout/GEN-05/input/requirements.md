# GEN-05 — synthetic, not an RTX specification

Package name: FourNode

1. Port definition LinkPort.
2. Part definition Radio with port toCommand of type LinkPort.
3. Part definition ShoreStation with port fromCommand of type LinkPort.
4. Part usages usv and uav, each containing part radio of Radio.
5. Part usage commandShip with ports fromUsv, fromUav, and toShore, each of type LinkPort.
6. Part usage shore of ShoreStation.
7. Connections: usv.radio.toCommand to commandShip.fromUsv; uav.radio.toCommand to commandShip.fromUav; commandShip.toShore to shore.fromCommand.
Do not invent numeric limits.
