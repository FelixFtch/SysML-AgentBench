package FourNode {
    port def LinkPort;

    part def Radio {
        port toCommand : LinkPort;
    }

    part def ShoreStation {
        port fromCommand : LinkPort;
    }

    part usv {
        part radio : Radio;
    }

    part uav {
        part radio : Radio;
    }

    part commandShip {
        port fromUsv : LinkPort;
        port fromUav : LinkPort;
        port toShore : LinkPort;
    }

    part shore : ShoreStation;

    connection usvLink connect usv.radio.toCommand to commandShip.fromUsv;
    connection uavLink connect uav.radio.toCommand to commandShip.fromUav;
    connection shoreLink connect commandShip.toShore to shore.fromCommand;
}
