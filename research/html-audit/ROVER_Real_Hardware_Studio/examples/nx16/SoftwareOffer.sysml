// SYNTHETIC OFFER S-01. Application proposals, not operational software.
package SoftwareOffer {
    private import RoverLibrary::*;
    part def LocalNavigation :> Navigation {
        :>> requiresInternet = false;
        doc /* Consumes Scan2D and declared IMU input; emits BodyVelocity.
               Controller behavior and physical stopping are not tested. */
    }
    part def LocalVision :> VisionProcessor;
    part def LocalRecorder :> Recorder;
}