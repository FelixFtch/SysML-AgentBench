```sysml
package AlignRadar {
    private import UavSensorSpec::*;
    private import RadarVendor::*;
    alias SearchRadar for RadarVendor::RadarModule_def;
    alias Camera for RadarVendor::GimbalCamera_def;
    allocation uav_payload allocate UavSensorSpec::uav to RadarVendor::payload;
    allocation searchRadar_radar allocate UavSensorSpec::uav.searchRadar to RadarVendor::payload.radar;
    allocation eoCamera_gimbal allocate UavSensorSpec::uav.eoCamera to RadarVendor::payload.gimbal;
}
```
```json
{
  "mappings": [
    {
      "oem_element": "UavSensorSpec::uav",
      "supplier_element": "RadarVendor::payload",
      "mapping_type": "allocation",
      "rationale": "Both are the containing payload part usages of the UAV sensor system."
    },
    {
      "oem_element": "UavSensorSpec::uav.searchRadar",
      "supplier_element": "RadarVendor::payload.radar",
      "mapping_type": "allocation",
      "rationale": "Both are the radar module part usages in the payload."
    },
    {
      "oem_element": "UavSensorSpec::uav.eoCamera",
      "supplier_element": "RadarVendor::payload.gimbal",
      "mapping_type": "allocation",
      "rationale": "Both are the electro-optical camera part usages in the payload."
    }
  ],
  "unmatched": [
    "UavSensorSpec::SearchRadar",
    "UavSensorSpec::Camera",
    "RadarVendor::RadarModule_def",
    "RadarVendor::GimbalCamera_def",
    "UavSensorSpec::SearchRadar::rangeKm",
    "RadarVendor::RadarModule_def::maxRangeKm",
    "RadarVendor::RadarModule_def::massKg"
  ]
}
```