```sysml
package AlignRadar {
    private import UavSensorSpec::*;
    private import RadarVendor::*;

    alias SearchRadar for RadarVendor::RadarModule_def;
    alias Camera for RadarVendor::GimbalCamera_def;
    alias rangeKm for RadarVendor::RadarModule_def::maxRangeKm;

    allocation radarAllocation allocate UavSensorSpec::uav.searchRadar to RadarVendor::payload.radar;
    allocation gimbalAllocation allocate UavSensorSpec::uav.eoCamera to RadarVendor::payload.gimbal;
}
```

```json
{
  "mappings": [
    {
      "oem_element": "UavSensorSpec::SearchRadar",
      "supplier_element": "RadarVendor::RadarModule_def",
      "mapping_type": "alias",
      "rationale": "The specification search radar definition and the vendor radar module definition describe the same kind of radar part; the alias binds the spec name to the supplier definition so the usage keeps the spec's short name."
    },
    {
      "oem_element": "UavSensorSpec::Camera",
      "supplier_element": "RadarVendor::GimbalCamera_def",
      "mapping_type": "alias",
      "rationale": "The spec camera definition corresponds to the vendor gimbal camera definition: both are the electro-optical sensor part with no internal features."
    },
    {
      "oem_element": "UavSensorSpec::SearchRadar::rangeKm",
      "supplier_element": "RadarVendor::RadarModule_def::maxRangeKm",
      "mapping_type": "alias",
      "rationale": "Both are Real range attributes of the radar definition expressed in kilometres; the vendor's maxRangeKm is the supplier-side realization of the spec's rangeKm."
    },
    {
      "oem_element": "UavSensorSpec::uav.searchRadar",
      "supplier_element": "RadarVendor::payload.radar",
      "mapping_type": "allocation",
      "rationale": "The spec's searchRadar part usage, typed by SearchRadar aliased to RadarModule_def, is satisfied by the vendor's radar part usage inside payload."
    },
    {
      "oem_element": "UavSensorSpec::uav.eoCamera",
      "supplier_element": "RadarVendor::payload.gimbal",
      "mapping_type": "allocation",
      "rationale": "The spec's eoCamera part usage, typed by Camera aliased to GimbalCamera_def, is satisfied by the vendor's gimbal part usage inside payload."
    }
  ],
  "unmatched": [
    "UavSensorSpec::uav",
    "RadarVendor::payload",
    "RadarVendor::RadarModule_def::massKg"
  ]
}
```