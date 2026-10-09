package AlignCamera {
    private import OptronicsKit::*;
    private import UsvPayloadSpec::*;

    alias ImageryPort for OptronicsKit::VideoOut;
    alias Camera for OptronicsKit::EoCameraUnit;
    alias Processor for OptronicsKit::VideoSink;
    alias drawW for OptronicsKit::EoCameraUnit::powerDrawW;

    allocation camera allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
    allocation processor allocate UsvPayloadSpec::usv.processor to OptronicsKit::kit.recorder;
    allocation imagery allocate UsvPayloadSpec::usv.eoCamera.imagery to OptronicsKit::kit.cameraUnit.videoOut;
    allocation imageryIn allocate UsvPayloadSpec::usv.processor.imageryIn to OptronicsKit::kit.recorder.videoIn;
}
