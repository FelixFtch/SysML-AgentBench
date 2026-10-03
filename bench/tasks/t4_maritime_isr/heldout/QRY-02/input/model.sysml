package MaritimeISR {
    /* Synthetic maritime ISR reference model. Numbers are not RTX specifications.
       Ground truth for the benchmark: frozen before any agent is scored against it. */
    private import ScalarValues::*;

    port def ImageryPort;
    port def TrackPort;
    port def LinkPort;

    part def Camera {
        port imagery : ImageryPort;
    }
    part def AisReceiver {
        port tracks : TrackPort;
    }
    part def Radar {
        port tracks : TrackPort;
    }
    part def Processor {
        port imageryIn : ImageryPort;
        port trackIn : TrackPort;
        port trackOut : TrackPort;
        port uplink : LinkPort;
    }
    part def Radio {
        port fromProcessor : LinkPort;
        port toShore : LinkPort;
    }

    part def UnmannedSurfaceVessel {
        part eoCamera : Camera;
        part irCamera : Camera;
        part ais : AisReceiver;
        part processor : Processor;
        part radio : Radio;
        attribute powerLimitW : Real = 60.0;
        attribute uplinkMbps : Real = 8.0;
        attribute storageGB : Real = 128.0;
    }
    part def FixedWingUav {
        part eoCamera : Camera;
        part searchRadar : Radar;
        part processor : Processor;
        part radio : Radio;
        attribute powerLimitW : Real = 120.0;
        attribute downlinkMbps : Real = 20.0;
    }
    part def CommandShip {
        port fromUsv : LinkPort;
        port fromUav : LinkPort;
        port toShore : LinkPort;
        part fusion : Processor;
        attribute fusionLatencyS : Real = 2.0;
    }
    part def ShoreStation {
        port fromCommand : LinkPort;
        part archive : Processor;
        attribute backhaulMbps : Real = 50.0;
    }

    part usv : UnmannedSurfaceVessel;
    part uav : FixedWingUav;
    part commandShip : CommandShip;
    part shore : ShoreStation;

    connect usv.eoCamera.imagery to usv.processor.imageryIn;
    connect usv.irCamera.imagery to usv.processor.imageryIn;
    connect usv.ais.tracks to usv.processor.trackIn;
    connect usv.processor.uplink to usv.radio.fromProcessor;
    connect usv.radio.toShore to commandShip.fromUsv;
    connect uav.searchRadar.tracks to uav.processor.trackIn;
    connect uav.eoCamera.imagery to uav.processor.imageryIn;
    connect uav.processor.uplink to uav.radio.fromProcessor;
    connect uav.radio.toShore to commandShip.fromUav;
    connect commandShip.toShore to shore.fromCommand;

    requirement def LocalRawRetention {
        doc /* USV raw imagery is retained locally. Numeric retention is a separate synthetic budget, not implied here. */
    }
    requirement def PowerLimitUnchanged {
        doc /* Synthetic: USV input power limit stays 60 W. An agent must not edit this limit to make a design pass. */
    }
    requirement def TrackSharing {
        doc /* Synthetic: USV AIS tracks and UAV radar tracks are shared to the command ship, then to the shore archive. */
    }
}
