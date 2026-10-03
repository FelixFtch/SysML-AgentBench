package RoundTripFusion {
    private import ScalarValues::*;
    part commandShip {
        port fromUsv;
        port fromUav;
        attribute fusionLatencyS : Real = 2.0;
    }
    requirement def Fusion {
        doc /* Fusion latency is 2 seconds and the command ship accepts two uplinks. */
    }
}
