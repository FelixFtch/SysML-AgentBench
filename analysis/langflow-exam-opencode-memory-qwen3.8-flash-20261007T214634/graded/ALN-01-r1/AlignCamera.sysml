package AlignCamera {
    private import UsvPayloadSpec::*;
    private import OptronicsKit::*;

    alias ImageryPort for OptronicsKit::VideoOut;
    alias Camera for OptronicsKit::EoCameraUnit;
    alias Processor for OptronicsKit::VideoSink;
    alias imagery for OptronicsKit::EoCameraUnit::videoOut;
    alias imageryIn for OptronicsKit::VideoSink::videoIn;
    alias drawW for OptronicsKit::EoCameraUnit::powerDrawW;

    allocation allocateUsvToKit allocate UsvPayloadSpec::usv to OptronicsKit::kit;
    allocation allocateEoCameraToCameraUnit allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
    allocation allocateProcessorToRecorder allocate UsvPayloadSpec::usv.processor to OptronicsKit::kit.recorder;
}
