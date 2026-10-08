```sysml
package AlignRadar {
    public import UavSensorSpec::*;
    public import RadarVendor::*;

    alias SearchRadar for RadarVendor::RadarModule_def;
    alias Camera for RadarVendor::GimbalCamera_def;
    alias rangeKm for RadarVendor::RadarModule_def::maxRangeKm;

    allocation searchRadarAlloc allocate UavSensorSpec::uav.searchRadar to RadarVendor::payload.radar;
    allocation eoCameraAlloc allocate UavSensorSpec::uav.eoCamera to RadarVendor::payload.gimbal;
}
```

```json
{
  "mappings": [
    {
      "oem_element": "UavSensorSpec::SearchRadar",
      "supplier_element": "RadarVendor::RadarModule_def",
      "mapping_type": "alias",
      "rationale": "Both are type definitions of the UAV's search radar; the vendor RadarModule_def is the supplier realization of the specification's SearchRadar."
    },
    {
      "oem_element": "UavSensorSpec::SearchRadar::rangeKm",
      "supplier_element": "RadarVendor::RadarModule_def::maxRangeKm",
      "mapping_type": "alias",
      "rationale": "Both attributes express the radar's detection range in kilometres on the same definition; the spec's rangeKm corresponds to the supplier's maxRangeKm."
    },
    {
      "oem_element": "UavSensorSpec::Camera",
      "supplier_element": "RadarVendor::GimbalCamera_def",
      "mapping_type": "alias",
      "rationale": "The specification's camera type is fulfilled by the vendor's EO camera definition (gimbal-stabilised); same role as the spec's electro-optical camera type."
    },
    {
      "oem_element": "UavSensorSpec::uav.searchRadar",
      "supplier_element": "RadarVendor::payload.radar",
      "mapping_type": "allocation",
      "rationale": "The spec's searchRadar part usage is satisfied by the vendor's radar part usage instantiated from the aliased RadarModule_def."
    },
    {
      "oem_element": "UavSensorSpec::uav.eoCamera",
      "supplier_element": "RadarVendor::payload.gimbal",
      "mapping_type": "allocation",
      "rationale": "The spec's eoCamera part usage is satisfied by the vendor's gimbal part usage instantiated from the aliased GimbalCamera_def."
    }
  ],
  "unmatched": [
    "RadarVendor::RadarModule_def::massKg",
    "UavSensorSpec::uav",
    "RadarVendor::payload"
  ]
}
```