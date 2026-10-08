```sysml
package FusionNode {
    private import ScalarValues::*;

    port def LinkPort;

    part def Processor {
        port trackIn : LinkPort;
    }

    part commandShip {
        attribute fusionLatencyS : Real = 2.0;
        port fromUsv : LinkPort;
        port fromUav : LinkPort;
        part fusion : Processor;
    }
}
```