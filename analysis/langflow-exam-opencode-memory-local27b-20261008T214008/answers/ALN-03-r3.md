```sysml
package AlignRadar {
    private import UavSensorSpec::*;
    private import RadarVendor::*;

    alias SearchRadar for RadarVendor::RadarModule_def;
    alias rangeKm for RadarVendor::RadarModule_def::maxRangeKm;
    alias Camera for RadarVendor::GimbalCamera_def;

    allocation searchRadar allocate UavSensorSpec::uav.searchRadar to RadarVendor::payload.radar;
    allocation eoCamera allocate UavSensorSpec::uav.eoCamera to RadarVendor::payload.gimbal;
}
```

```json
{
  "mappings": [
    {
      "oem_element": "UavSensorSpec::SearchRadar",
      "supplier_element": "RadarVendor::RadarModule_def",
      "mapping_type": "alias",
      "rationale": "Both define the radar sensor module."
    },
    {
      "oem_element": "UavSensorSpec::SearchRadar::rangeKm",
      "supplier_element": "RadarVendor::RadarModule_def::maxRangeKm",
      "mapping_type": "alias",
      "rationale": "Both capture the radar range capability in km."
    },
    {
      "oem_element": "UavSensorSpec::Camera",
      "supplier_element": "RadarVendor::GimbalCamera_def",
      "mapping_type": "alias",
      "rationale": "Both define the camera/imager sensor module."
    },
    {
      "oem_element": "UavSensorSpec::uav.searchRadar",
      "supplier_element": "RadarVendor::payload.radar",
      "mapping_type": "allocation",
      "rationale": "Allocates the specification's radar usage to the supplier's radar sensor usage."
    },
    {
      "oem_element": "UavSensorSpec::uav.eoCamera",
      "supplier_element": "RadarVendor::payload.gimbal",
      "mapping_type": "allocation",
      "rationale": "Allocates the specification's camera usage to the supplier's gimbal/camera usage."
    }
  ],
  "unmatched": [
    "UavSensorSpec::uav",
    "RadarVendor::payload",
    "RadarVendor::RadarModule_def::massKg"
  ]
}
```