# GEN-01 (development) — synthetic, not an RTX specification

Package name: HarborLink

Write a SysML v2 model of one unmanned surface vessel sharing camera data with one shore station.

Required content, and nothing beyond it:

1. A part definition Camera with a port named imagery of type ImageryPort.
2. A part definition Processor with a port named imageryIn of type ImageryPort and a port named uplink of type LinkPort.
3. A part definition Radio with a port named fromProcessor of type LinkPort and a port named toShore of type LinkPort.
4. A part definition ShoreStation with a port named fromVessel of type LinkPort.
5. Port definitions ImageryPort and LinkPort.
6. One part usage of each definition, nested in a part usage named vessel, except the shore station which is a sibling of vessel.
7. Connections: camera imagery to processor imageryIn; processor uplink to radio fromProcessor; radio toShore to shore station fromVessel.
8. A requirement definition RawRetention whose doc comment states that raw imagery is retained locally. Do not invent a numeric limit.
