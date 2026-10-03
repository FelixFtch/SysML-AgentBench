package UsvPlain {
    private import ScalarValues::*;
    port def ImageryPort;
    port def TrackPort;
    port def LinkPort;
    part def Camera { port imagery : ImageryPort; }
    part def AisReceiver { port tracks : TrackPort; }
    part def Processor {
        port imageryIn : ImageryPort;
        port trackIn : TrackPort;
        port uplink : LinkPort;
    }
    part def Radio { port fromProcessor : LinkPort; port toShore : LinkPort; }
    part usv {
        part eoCamera : Camera;
        part ais : AisReceiver;
        part processor : Processor;
        part radio : Radio;
        attribute powerLimitW : Real = 60.0;
    }
    connect usv.eoCamera.imagery to usv.processor.imageryIn;
    connect usv.ais.tracks to usv.processor.trackIn;
    connect usv.processor.uplink to usv.radio.fromProcessor;
}
