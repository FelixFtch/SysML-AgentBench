package AlignRadar {
    private import UavSensorSpec::*;
    private import RadarVendor::*;
    alias SearchRadar for RadarVendor::RadarModule_def;
    alias Camera for RadarVendor::GimbalCamera_def;
    alias rangeKm for RadarVendor::RadarModule_def::maxRangeKm;
    allocation payload allocate UavSensorSpec::uav to RadarVendor::payload;
    allocation radar allocate UavSensorSpec::uav.searchRadar to RadarVendor::payload.radar;
    allocation camera allocate UavSensorSpec::uav.eoCamera to RadarVendor::payload.gimbal;
}
