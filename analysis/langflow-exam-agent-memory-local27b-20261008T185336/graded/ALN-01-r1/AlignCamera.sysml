package AlignCamera {
    private import UsvPayloadSpec::*;
    private import OptronicsKit::*;
    alias ImageryPort for OptronicsKit::VideoOut;
    alias Camera for OptronicsKit::EoCameraUnit;
    alias Processor for OptronicsKit::VideoSink;
    alias imagery for OptronicsKit::EoCameraUnit::videoOut;
    alias drawW for OptronicsKit::EoCameraUnit::powerDrawW;
    alias imageryIn for OptronicsKit::VideoSink::videoIn;
    allocation usvKit allocate UsvPayloadSpec::usv to OptronicsKit::kit;
    allocation eoCameraUnit allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
    allocation recorder allocate UsvPayloadSpec::usv.processor to OptronicsKit::kit.recorder;
}
