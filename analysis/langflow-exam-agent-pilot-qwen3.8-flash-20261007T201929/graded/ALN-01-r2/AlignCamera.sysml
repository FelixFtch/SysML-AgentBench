package AlignCamera {
    private import UsvPayloadSpec::*;
    private import OptronicsKit::*;

    alias ImageryPort for OptronicsKit::VideoOut;
    alias Camera for OptronicsKit::EoCameraUnit;
    alias Processor for OptronicsKit::VideoSink;

    alias drawW for OptronicsKit::EoCameraUnit::powerDrawW;
    alias imagery for OptronicsKit::EoCameraUnit::videoOut;
    alias imageryIn for OptronicsKit::VideoSink::videoIn;

    allocation alignTop      allocate UsvPayloadSpec::usv          to OptronicsKit::kit;
    allocation alignCamera   allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
    allocation alignProcessr allocate UsvPayloadSpec::usv.processor to OptronicsKit::kit.recorder;
}
