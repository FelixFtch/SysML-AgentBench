# GEN-03 — synthetic, not an RTX specification

Package name: FusionNode

1. Port definition LinkPort.
2. Part definition Processor with port trackIn of type LinkPort.
3. Part usage commandShip with ports fromUsv and fromUav of type LinkPort.
4. Nested part usage fusion of Processor.
5. Attribute fusionLatencyS on commandShip, type Real, value 2.0.
Do not add other numbers.
