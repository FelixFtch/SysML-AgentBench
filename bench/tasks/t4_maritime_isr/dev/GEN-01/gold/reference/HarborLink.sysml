package HarborLink {
    /* GEN-01 reference model. Human-authored gold, not an agent output.
       Synthetic development task. No numeric limits are stated in the task, so none are modeled. */
    port def ImageryPort;
    port def LinkPort;

    part def Camera {
        port imagery : ImageryPort;
    }
    part def Processor {
        port imageryIn : ImageryPort;
        port uplink : LinkPort;
    }
    part def Radio {
        port fromProcessor : LinkPort;
        port toShore : LinkPort;
    }
    part def ShoreStation {
        port fromVessel : LinkPort;
    }

    part vessel {
        part camera : Camera;
        part processor : Processor;
        part radio : Radio;
    }
    part shoreStation : ShoreStation;

    connect vessel.camera.imagery to vessel.processor.imageryIn;
    connect vessel.processor.uplink to vessel.radio.fromProcessor;
    connect vessel.radio.toShore to shoreStation.fromVessel;

    requirement def RawRetention {
        doc /* raw imagery is retained locally */
    }
}
