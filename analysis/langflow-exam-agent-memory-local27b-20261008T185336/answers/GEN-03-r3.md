```sysml
package FusionNode {
    private import ScalarValues::*;
    port def LinkPort;
    part def Processor {
        port trackIn: LinkPort;
    }
    part commandShip {
        port fromUsv: LinkPort;
        port fromUav: LinkPort;
        part fusion: Processor;
        attribute fusionLatencyS: Real = 2.0;
    }
}
```