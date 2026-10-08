```sysml
package FusionNode {
    private import ScalarValues::*;
    port def LinkPort {}
    part def Processor {
        port trackIn : LinkPort;
    }
    part commandShip {
        part fusion : Processor;
        port fromUsv : LinkPort;
        port fromUav : LinkPort;
        attribute fusionLatencyS : Real = 2.0;
    }
}
```