package AlignRadar {
    private import UavSensorSpec::*;
    private import RadarVendor::*;
    alias SearchRadar for RadarVendor::RadarModule_def;
    alias rangeKm for RadarVendor::RadarModule_def::maxRangeKm;
    alias Camera for RadarVendor::GimbalCamera_def;
    allocation uavToPayload allocate UavSensorSpec::uav to RadarVendor::payload;
    allocation searchRadarToRadar allocate UavSensorSpec::uav.searchRadar to RadarVendor::payload.radar;
    allocation eoCameraToGimbal allocate UavSensorSpec::uav.eoCamera to RadarVendor::payload.gimbal;
}
