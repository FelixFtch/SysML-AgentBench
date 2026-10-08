package AlignRadar {
    private import UavSensorSpec::*;
    private import RadarVendor::*;

    alias SearchRadar for RadarVendor::RadarModule_def;
    alias rangeKm for RadarVendor::RadarModule_def::maxRangeKm;
    alias Camera for RadarVendor::GimbalCamera_def;

    allocation radarAllocation allocate UavSensorSpec::uav.searchRadar to RadarVendor::payload.radar;
    allocation cameraAllocation allocate UavSensorSpec::uav.eoCamera to RadarVendor::payload.gimbal;
}
