package AlignCamera {
    private import UsvPayloadSpec::*;
    private import OptronicsKit::*;

    alias ImageryPort for OptronicsKit::VideoOut;
    alias Camera for OptronicsKit::EoCameraUnit;
    alias imagery for OptronicsKit::EoCameraUnit::videoOut;
    alias drawW for OptronicsKit::EoCameraUnit::powerDrawW;
    alias Processor for OptronicsKit::VideoSink;
    alias imageryIn for OptronicsKit::VideoSink::videoIn;

    allocation platformAlloc allocate UsvPayloadSpec::usv to OptronicsKit::kit;
    allocation cameraAlloc allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
    allocation recorderAlloc allocate UsvPayloadSpec::usv.processor to OptronicsKit::kit.recorder;
}
