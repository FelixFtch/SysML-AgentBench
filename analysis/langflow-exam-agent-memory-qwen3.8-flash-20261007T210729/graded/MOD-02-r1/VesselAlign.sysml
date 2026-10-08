package VesselAlign {
    port def ImageryPort;
    port def TrackPort;
    part def Camera { port imagery : ImageryPort; }
    part def AisReceiver { port tracks : TrackPort; }
    part def Processor {
        port imageryIn : ImageryPort;
        port trackIn : TrackPort;
    }
    part vessel {
        part camera : Camera;
        part processor : Processor;
        part ais : AisReceiver;
    }
    requirement def TimeAlign {
        doc /* tracks and imagery share a timestamp */
    }
    connect vessel.camera.imagery to vessel.processor.imageryIn;
    connect vessel.ais.tracks to vessel.processor.trackIn;
}
