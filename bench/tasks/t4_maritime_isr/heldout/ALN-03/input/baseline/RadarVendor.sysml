package RadarVendor {
    private import ScalarValues::*;
    part def RadarModule_def {
        attribute maxRangeKm : Real;
        attribute massKg : Real;
    }
    part def GimbalCamera_def;
    part payload {
        part radar : RadarModule_def;
        part gimbal : GimbalCamera_def;
    }
}
