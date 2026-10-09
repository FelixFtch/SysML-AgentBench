package AlignCamera {
    public import UsvPayloadSpec::*;
    public import OptronicsKit::*;
    alias Camera for OptronicsKit::EoCameraUnit;
    alias Processor for OptronicsKit::VideoSink;
    alias ImageryPort for OptronicsKit::VideoOut;
    allocation camera allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
    allocation processor allocate UsvPayloadSpec::usv.processor to OptronicsKit::kit.recorder;
}
