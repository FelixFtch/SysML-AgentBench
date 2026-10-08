```sysml
package AlignRadar {
    private import UavSensorSpec::*;
    private import RadarVendor::*;

    alias SearchRadar for RadarVendor::RadarModule_def;
    alias Camera for RadarVendor::GimbalCamera_def;
    alias rangeKm for RadarVendor::RadarModule_def::maxRangeKm;

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
      "rationale": "The specified search radar definition is fulfilled by the vendor radar module definition; aliasing lets the vendor module be used wherever SearchRadar is required."
    },
    {
      "oem_element": "UavSensorSpec::Camera",
      "supplier_element": "RadarVendor::GimbalCamera_def",
      "mapping_type": "alias",
      "rationale": "The EO camera definition corresponds to the vendor gimbal camera definition (same role, electro-optical imaging payload)."
    },
    {
      "oem_element": "UavSensorSpec::SearchRadar::rangeKm",
      "supplier_element": "RadarVendor::RadarModule_def::maxRangeKm",
      "mapping_type": "alias",
      "rationale": "Same Real-valued radar range characteristic in km; the vendor states it as a maximum range bound."
    },
    {
      "oem_element": "UavSensorSpec::uav.searchRadar",
      "supplier_element": "RadarVendor::payload.radar",
      "mapping_type": "allocation",
      "rationale": "The radar part usage on the UAV assembly is satisfied by the vendor radar part usage in its payload assembly."
    },
    {
      "oem_element": "UavSensorSpec::uav.eoCamera",
      "supplier_element": "RadarVendor::payload.gimbal",
      "mapping_type": "allocation",
      "rationale": "The EO camera part usage on the UAV assembly is satisfied by the vendor gimbal camera part usage in its payload assembly."
    }
  ],
  "unmatched": [
    "RadarVendor::RadarModule_def::massKg"
  ]
}
```