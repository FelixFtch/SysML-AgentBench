package AlignRadar {
    public import UavSensorSpec::*;
    private import RadarVendor::*;
    alias SearchRadar for RadarVendor::RadarModule_def;
    alias rangeKm for RadarVendor::RadarModule_def::maxRangeKm;
    alias Camera for RadarVendor::GimbalCamera_def;
    allocation radarToModule allocate UavSensorSpec::uav.searchRadar to RadarVendor::payload.radar;
    allocation cameraToGimbal allocate UavSensorSpec::uav.eoCamera to RadarVendor::payload.gimbal;
}
