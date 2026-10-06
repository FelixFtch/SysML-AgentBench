package OptronicsKit {
    private import ScalarValues::*;
    port def VideoOut;
    part def EoCameraUnit {
        port videoOut : VideoOut;
        attribute powerDrawW : Real;
        attribute heaterW : Real;
    }
    part def VideoSink {
        port videoIn : VideoOut;
    }
    part kit {
        part cameraUnit : EoCameraUnit;
        part recorder : VideoSink;
        connect cameraUnit.videoOut to recorder.videoIn;
    }
}
