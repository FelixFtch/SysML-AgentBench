package FourNode {
    part LinkPort {}
    part Radio {
        end toCommand;
    }
    part ShoreStation {
        end fromCommand;
    }
    part usv {
        end radio;
    }
    part uav {
        end radio;
    }
    part commandShip {
        end fromUsv;
        end fromUav;
        end toShore;
    }
    part shore {
        end fromCommand;
    }
}
