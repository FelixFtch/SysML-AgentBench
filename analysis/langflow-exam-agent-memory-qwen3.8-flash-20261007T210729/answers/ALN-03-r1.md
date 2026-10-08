```sysml
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
```

```json
{
  "mappings": [
    {
      "oem_element": "UavSensorSpec::SearchRadar",
      "supplier_element": "RadarVendor::RadarModule_def",
      "mapping_type": "alias",
      "rationale": "The specification search radar definition is realized by the supplier radar module definition; both are part definitions of a radar payload."
    },
    {
      "oem_element": "UavSensorSpec::SearchRadar::rangeKm",
      "supplier_element": "RadarVendor::RadarModule_def::maxRangeKm",
      "mapping_type": "alias",
      "rationale": "The spec range attribute on the radar def denotes the same radar range quantity as the supplier max range attribute; both are Real attributes on the radar part definition."
    },
    {
      "oem_element": "UavSensorSpec::Camera",
      "supplier_element": "RadarVendor::GimbalCamera_def",
      "mapping_type": "alias",
      "rationale": "The specification camera definition corresponds to the supplier gimbal camera definition, the only camera part def offered."
    },
    {
      "oem_element": "UavSensorSpec::uav",
      "supplier_element": "RadarVendor::payload",
      "mapping_type": "allocation",
      "rationale": "The spec UAV usage that owns the sensor parts is allocated to the supplier payload usage that owns the same sensor parts."
    },
    {
      "oem_element": "UavSensorSpec::uav.searchRadar",
      "supplier_element": "RadarVendor::payload.radar",
      "mapping_type": "allocation",
      "rationale": "The spec search radar part usage is fulfilled by the supplier radar part usage typed by the aliased radar module definition."
    },
    {
      "oem_element": "UavSensorSpec::uav.eoCamera",
      "supplier_element": "RadarVendor::payload.gimbal",
      "mapping_type": "allocation",
      "rationale": "The spec EO camera part usage is fulfilled by the supplier gimbal camera part usage typed by the aliased camera definition."
    }
  ],
  "unmatched": [
    "RadarVendor::RadarModule_def::massKg"
  ]
}
```