// TEACHING DRAFT. Parser NOT RUN. File is a supported-subset proposal, not validated code.
package RoverLibrary {
    private import ScalarValues::*;
    item def Scan2D;
    item def ImuSample;
    item def BodyVelocity { attribute v_mps : Real; attribute yaw_rps : Real; }
    item def WheelRPM { attribute left_rpm : Real; attribute right_rpm : Real; }
    item def RGBDFrame;
    item def LocalObservation;
    port def ScanPort { out item sample : Scan2D; }
    port def ImuPort { out item sample : ImuSample; }
    port def BodyCommandPort { out item command : BodyVelocity; }
    port def WheelCommandPort { out item command : WheelRPM; }
    port def ImagePort { out item frame : RGBDFrame; }
    port def LocalObservationPort { out item observation : LocalObservation; }
    part def Imu { port output : ImuPort; }
    part def Motor;
    part def MotorController { port input : ~WheelCommandPort; }
    part def LidarModule { port output : ScanPort; part imu : Imu; }
    part def DriveBase {
        part motorLeft : Motor; part motorRight : Motor;
        part controller : MotorController;
        port input : ~WheelCommandPort;
        connect input to controller.input;
        attribute wheelRadius_m : Real;
        attribute track_m : Real;
    }
    part def Navigation {
        port scanIn : ~ScanPort;
        port imuIn : ~ImuPort;
        port commandOut : BodyCommandPort;
        attribute requiresInternet : Boolean;
    }
    part def DiffDriveAdapter {
        port bodyIn : ~BodyCommandPort;
        port wheelOut : WheelCommandPort;
        attribute wheelRadius_m : Real;
        attribute track_m : Real;
        doc /* R-01 adapter obligation: declared planar kinematics and signs.
               A model connector does not implement a running motor driver. */
    }
    part def Battery { attribute energy_Wh : Real; attribute length_mm : Real; attribute width_mm : Real; attribute height_mm : Real; }
    part def Tray { attribute insideLength_mm : Real; attribute insideWidth_mm : Real; attribute insideHeight_mm : Real; }
    part def Camera { port frameOut : ImagePort; }
    part def VisionProcessor { port frameIn : ~ImagePort; port resultOut : LocalObservationPort; }
    part def Recorder { port frameIn : ~ImagePort; port observationIn : ~LocalObservationPort; }
}