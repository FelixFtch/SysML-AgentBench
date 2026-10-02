// SYNTHETIC OFFER M-01. Fixed source catalog. Parser NOT RUN.
package MechatronicsOffer {
    private import ScalarValues::*;
    private import RoverLibrary::*;
    part def OfferedChassis :> DriveBase {
        :>> wheelRadius_m = 0.05;
        :>> track_m = 0.28;
        doc /* CH-01 includes MOTOR-L, MOTOR-R, MOTOR-CTRL. Do not purchase/count twice. */
    }
    part def Battery96 :> Battery {
        :>> energy_Wh = 96.0;
        :>> length_mm = 120.0; :>> width_mm = 80.0; :>> height_mm = 45.0;
    }
    part def Battery160 :> Battery {
        :>> energy_Wh = 160.0;
        :>> length_mm = 140.0; :>> width_mm = 80.0; :>> height_mm = 45.0;
    }
    part def OriginalTray :> Tray {
        :>> insideLength_mm = 130.0; :>> insideWidth_mm = 90.0; :>> insideHeight_mm = 50.0;
    }
    part def ExpandedTray :> Tray {
        :>> insideLength_mm = 150.0; :>> insideWidth_mm = 90.0; :>> insideHeight_mm = 50.0;
        doc /* CNC candidate envelope only; strength, tolerances and manufacturing NOT CHECKED. */
    }
}