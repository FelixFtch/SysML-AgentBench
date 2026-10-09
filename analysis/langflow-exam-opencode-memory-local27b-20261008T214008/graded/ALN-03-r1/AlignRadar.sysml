package AlignRadar {
    private import UavSensorSpec::*;
    private import RadarVendor::*;
    alias SearchRadar for RadarVendor::RadarModule_def;
    alias Camera for RadarVendor::GimbalCamera_def;
    allocation uav_payload allocate UavSensorSpec::uav to RadarVendor::payload;
    allocation searchRadar_radar allocate UavSensorSpec::uav.searchRadar to RadarVendor::payload.radar;
    allocation eoCamera_gimbal allocate UavSensorSpec::uav.eoCamera to RadarVendor::payload.gimbal;
}
