package AlignCamera {
    public import UsvPayloadSpec::*;
    private import OptronicsKit::*;
    alias Camera for OptronicsKit::EoCameraUnit;
    alias ImageryPort for OptronicsKit::VideoOut;
    alias imagery for OptronicsKit::EoCameraUnit::videoOut;
    alias drawW for OptronicsKit::EoCameraUnit::powerDrawW;
    allocation eoCameraToUnit allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
}
