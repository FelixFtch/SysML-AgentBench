package UsvPayloadSpec {
    private import ScalarValues::*;
    port def ImageryPort;
    part def Camera {
        port imagery : ImageryPort;
        attribute drawW : Real;
    }
    part def Processor {
        port imageryIn : ImageryPort;
    }
    part usv {
        part eoCamera : Camera;
        part processor : Processor;
        connect eoCamera.imagery to processor.imageryIn;
    }
}
