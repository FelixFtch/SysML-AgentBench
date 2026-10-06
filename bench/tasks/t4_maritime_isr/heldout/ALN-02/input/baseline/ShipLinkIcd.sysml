package ShipLinkIcd {
    private import ScalarValues::*;
    port def LinkPort;
    port def HealthPort;
    part def Radio {
        port toShore : LinkPort;
        port health : HealthPort;
        attribute uplinkMbps : Real;
    }
    part def CommandShip {
        port fromUsv : LinkPort;
        port fromUav : LinkPort;
    }
    part usv {
        part radio : Radio;
    }
    part commandShip : CommandShip;
    connect usv.radio.toShore to commandShip.fromUsv;
}
