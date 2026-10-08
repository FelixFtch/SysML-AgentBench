```sysml
package AlignRadar {
    private import UavSensorSpec::*;
    private import RadarVendor::*;

    alias SearchRadar for RadarVendor::RadarModule_def;
    alias rangeKm for RadarVendor::RadarModule_def::maxRangeKm;
    alias Camera for RadarVendor::GimbalCamera_def;

    allocation radarAllocation allocate UavSensorSpec::uav.searchRadar to RadarVendor::payload.radar;
    allocation cameraAllocation allocate UavSensorSpec::uav.eoCamera to RadarVendor::payload.gimbal;
}
```

```json
{
  "mappings": [
    {
      "oem_element": "UavSensorSpec::SearchRadar",
      "supplier_element": "RadarVendor::RadarModule_def",
      "mapping_type": "alias",
      "rationale": "Both definitions describe the UAV's search radar; the specification's SearchRadar corresponds to the vendor's RadarModule definition."
    },
    {
      "oem_element": "UavSensorSpec::SearchRadar::rangeKm",
      "supplier_element": "RadarVendor::RadarModule_def::maxRangeKm",
      "mapping_type": "alias",
      "rationale": "The names differ but the meaning is the same attribute: the radar's (maximum) detection range in kilometres, typed Real in both models."
    },
    {
      "oem_element": "UavSensorSpec::Camera",
      "supplier_element": "RadarVendor::GimbalCamera_def",
      "mapping_type": "alias",
      "rationale": "The specified electro-optical camera is the vendor's gimbal-camera part definition; both are the imaging payload definition carried by the aircraft."
    },
    {
      "oem_element": "UavSensorSpec::uav.searchRadar",
      "supplier_element": "RadarVendor::payload.radar",
      "mapping_type": "allocation",
      "rationale": "The specification's searchRadar usage (typed SearchRadar, aliased to RadarModule_def) is realised by the vendor's radar usage inside its payload."
    },
    {
      "oem_element": "UavSensorSpec::uav.eoCamera",
      "supplier_element": "RadarVendor::payload.gimbal",
      "mapping_type": "allocation",
      "rationale": "The specification's eoCamera usage (typed Camera, aliased to GimbalCamera_def) is realised by the vendor's gimbal camera usage inside its payload."
    }
  ],
  "unmatched": [
    "RadarVendor::RadarModule_def::massKg",
    "UavSensorSpec::uav",
    "RadarVendor::payload"
  ]
}
```