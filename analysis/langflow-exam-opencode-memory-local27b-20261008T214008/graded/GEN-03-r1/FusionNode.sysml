package FusionNode

private import ScalarValues::*;

portdef LinkPort;

partdef Processor {
    port trackIn : LinkPort;
}

part commandShip {
    port fromUsv : LinkPort;
    port fromUav : LinkPort;
    fusionLatencyS : Real = 2.0;
    part fusion : Processor;
}
