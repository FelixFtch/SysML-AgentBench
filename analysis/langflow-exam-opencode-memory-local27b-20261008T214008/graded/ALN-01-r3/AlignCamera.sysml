package AlignCamera {
    public import OptronicsKit::*;
    public import UsvPayloadSpec::*;
    alias ImageryPort for OptronicsKit::VideoOut;
    alias Camera for OptronicsKit::EoCameraUnit;
    alias drawW for OptronicsKit::EoCameraUnit::powerDrawW;
    alias Processor for OptronicsKit::VideoSink;
    allocation camera_allocate allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
    allocation processor_allocate allocate UsvPayloadSpec::usv.processor to OptronicsKit::kit.recorder;
}
