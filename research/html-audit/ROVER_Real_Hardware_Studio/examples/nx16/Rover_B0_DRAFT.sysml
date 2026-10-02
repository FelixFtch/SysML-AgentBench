// Hardware profile Jetson Orin NX 16GB; Livox Mid-360S; RealSense D435i
// rover-hardware-catalog/1; sources checked 2026-09-15.
// GUI graph is authored data, NOT a parser result. Import ALL companion model files.
// ROVER SINGLE-PAGE CASE · candidate B0
// NOT PARSER-VALIDATED. Template output from browser fixture, NOT an LLM result.
// Import the companion RoverLibrary and supplier files; review with a real tool.
package Rover_B0 {
    private import ScalarValues::*;
    private import RoverLibrary::*;
    private import PerceptionOffer::*;
    private import MechatronicsOffer::*;
    private import SoftwareOffer::*;
    private import HardwareOffers::*;

    // CMBSE-inspired referencing: aliases reference source definitions;
    // they are not unit converters or proof of semantic equivalence.
    alias LidarChoice for PerceptionOffer::OfferedLidar;
    alias ChassisChoice for MechatronicsOffer::OfferedChassis;

    requirement def MapNavigation {
        doc /* R-01: Navigate between specified stations on the supplied indoor map. */
    }
    requirement def LocalStop {
        doc /* R-02: Enter stopping behavior on the approved obstacle condition.
               Obstacle threshold and physical stopping performance need review. */
    }
    requirement def OfflineOperation {
        doc /* R-03: Basic navigation and stopping must not depend on Internet. */
    }
    requirement def RuntimeTarget {
        doc /* R-04: At least 2 h under the declared battery-side mean-load scenario. */
        attribute minimum_h : Real = 2.0;
    }
    requirement def WidthLimit {
        doc /* R-05: Overall width with accessories at most 350 mm. */
        attribute maximum_mm : Real = 350.0;
    }
    requirement def StateVisibility {
        doc /* R-06: Identify idle, navigating, stopped and fault modes. */
    }
    requirement def OfflineVision {
        doc /* R-07 / CR-08: Add depth imaging, local processing and local recording;
               preserve R-03, R-04 and R-05. Model proposal, not executable driver. */
    }

    part rover {
        attribute plannedLidarSupply_V : Real = 12;
        attribute assumedComputeInput_W : Real = 24;
        attribute assumedCameraReserve_W : Real = 4;
        attribute assumedDcEfficiency : Real = 0.9;
        doc /* These four parameters are design assumptions, not manufacturer measured load. */
        part lidar : LidarChoice;
        part compute : JetsonAssembly;
        part livoxDriver : LivoxDriver;
        part stateEstimator : StateEstimator;
        part cloudProjection : CloudProjection;
        doc /* Navigation and drivers DEPLOYED on compute; software nodes are not extra boards. */
        part chassis : ChassisChoice;
        part navigation : LocalNavigation;
        part battery : Battery96;
        part tray : OriginalTray;
        part commandAdapter : DiffDriveAdapter {
            :>> wheelRadius_m = 0.05;
            :>> track_m = 0.28;
        }
        part camera : OfferedDepthCamera;
        part realsenseDriver : RealSenseDriver;
        part visionProcessor : LocalVision;
        part imageRecorder : LocalRecorder;
        connect lidar.packets to livoxDriver.packetIn;
        connect livoxDriver.cloudOut to cloudProjection.cloudIn;
        connect cloudProjection.scanOut to navigation.scanIn;
        connect livoxDriver.imuOut to stateEstimator.imuIn;
        // State estimator to navigation TF/odometry deployment still needs full model detail.
        connect navigation.commandOut to commandAdapter.bodyIn;
        connect commandAdapter.wheelOut to chassis.input;
        connect camera.usbStream to realsenseDriver.usbIn;
        connect realsenseDriver.frameOut to visionProcessor.frameIn;
        connect realsenseDriver.frameOut to imageRecorder.frameIn;
        connect visionProcessor.resultOut to imageRecorder.observationIn;

        attribute baseLoadAtBattery_W : Real = 32.777778;
        attribute addedVisionLoadAtBattery_W : Real = 17.777778;
        attribute meanLoadAtBattery_W : Real = baseLoadAtBattery_W + addedVisionLoadAtBattery_W;
        attribute usableEnergyFraction : Real = 0.8;
        attribute estimatedRuntime_h : Real = battery.energy_Wh * usableEnergyFraction / meanLoadAtBattery_W;
        attribute overallWidth_mm : Real = 330.0;
        // Scalar suffix units are a bounded teaching convention, not unit-library validation.
        // Electrical rails, harness, mass/inertia and calibrated mounting are not modeled fully.
    }

    requirement mapNavigation : MapNavigation;
    requirement localStop : LocalStop;
    requirement offlineOperation : OfflineOperation;
    requirement runtimeRequirement : RuntimeTarget;
    requirement widthRequirement : WidthLimit;
    requirement stateVisibility : StateVisibility;
    requirement localVisionRequirement : OfflineVision;

    // Separate candidate constraints from requirement assertions and test evidence.
    constraint estimatedRuntimeCheck {
        rover.estimatedRuntime_h >= runtimeRequirement.minimum_h
    }
    constraint overallWidthCheck {
        rover.overallWidth_mm <= widthRequirement.maximum_mm
    }
    constraint fixedOrientationBatteryFit {
        rover.battery.length_mm <= rover.tray.insideLength_mm and
        rover.battery.width_mm <= rover.tray.insideWidth_mm and
        rover.battery.height_mm <= rover.tray.insideHeight_mm
    }

    action def FollowRoute;
    action def IssueStopRequest;
    action def RecordState;
    action def CaptureFrame;
    action def ProcessLocally;
    action def StoreLocally;

    action operationalWorkflow {
        first start;
        then action followRoute : FollowRoute;
        then action recordState : RecordState;
        then done;
        doc /* STOP/FAULT branching is an obligation for the executable controller.
               The authored state catalogue below is not a completed transition implementation. */
    }
    action localVisionWorkflow {
        first start;
        then action capture : CaptureFrame;
        then action process : ProcessLocally;
        then action save : StoreLocally;
        then done;
        doc /* R-07: local behavior proposal. No image recognition, disk I/O or motion runs here. */
    }
    state def OperationalStates {
        state idle;
        state navigating;
        state stopped;
        state fault;
    }
    // Verification intentions only. No successful verification is asserted in this draft.
    doc /* Intended evidence: parsed-model diagnostics, requirement review, numerical
           runtime/fit checks, controlled stopping and independent physical testing.
           Browser arithmetic is NOT execution of this SysML file. */
}
