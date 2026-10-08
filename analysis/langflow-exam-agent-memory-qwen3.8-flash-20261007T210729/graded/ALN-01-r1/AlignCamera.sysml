package AlignCamera {
    public import UsvPayloadSpec::*;
    public import OptronicsKit::*;

    alias Camera for OptronicsKit::EoCameraUnit;
    alias Processor for OptronicsKit::VideoSink;
    alias ImageryPort for OptronicsKit::VideoOut;

    alias imagery for OptronicsKit::EoCameraUnit::videoOut;
    alias imageryIn for OptronicsKit::VideoSink::videoIn;
    alias drawW for OptronicsKit::EoCameraUnit::powerDrawW;

    allocation usvToKit allocate UsvPayloadSpec::usv to OptronicsKit::kit;
    allocation eoCameraToCameraUnit allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
    allocation processorToRecorder allocate UsvPayloadSpec::usv.processor to OptronicsKit::kit.recorder;
}
