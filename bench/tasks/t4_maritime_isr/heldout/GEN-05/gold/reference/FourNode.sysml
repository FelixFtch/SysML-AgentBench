package FourNode {
    port def LinkPort;
    part def Radio { port toCommand : LinkPort; }
    part def ShoreStation { port fromCommand : LinkPort; }
    part usv { part radio : Radio; }
    part uav { part radio : Radio; }
    part commandShip {
        port fromUsv : LinkPort;
        port fromUav : LinkPort;
        port toShore : LinkPort;
    }
    part shore : ShoreStation;
    connect usv.radio.toCommand to commandShip.fromUsv;
    connect uav.radio.toCommand to commandShip.fromUav;
    connect commandShip.toShore to shore.fromCommand;
}
