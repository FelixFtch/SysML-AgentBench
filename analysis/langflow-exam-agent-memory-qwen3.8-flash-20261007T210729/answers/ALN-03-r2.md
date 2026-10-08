```sysml
package AlignRadar {
    private import UavSensorSpec::*;
    private import RadarVendor::*;

    alias SearchRadar for RadarVendor::RadarModule_def;
    alias Camera for RadarVendor::GimbalCamera_def;
    alias rangeKm for RadarVendor::RadarModule_def::maxRangeKm;

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
      "rationale": "The specification search-radar part definition is realised by the vendor's radar module part definition; both are part definitions of the same role, so the spec short name SearchRadar aliases the supplier definition."
    },
    {
      "oem_element": "UavSensorSpec::Camera",
      "supplier_element": "RadarVendor::GimbalCamera_def",
      "mapping_type": "alias",
      "rationale": "The specification camera part definition corresponds to the vendor's gimbal camera part definition; both are unstructured part definitions for the EO imaging payload."
    },
    {
      "oem_element": "UavSensorSpec::SearchRadar::rangeKm",
      "supplier_element": "RadarVendor::RadarModule_def::maxRangeKm",
      "mapping_type": "alias",
      "rationale": "Same meaning and same type (Real kilometres of radar range): the spec range attribute is supplied by the vendor's maximum-range attribute."
    },
    {
      "oem_element": "UavSensorSpec::uav",
      "supplier_element": "RadarVendor::payload",
      "mapping_type": "allocation",
      "rationale": "The spec top-level sensor-bearing part usage is allocated to the vendor's payload part usage, which hosts the same two child part usages."
    },
    {
      "oem_element": "UavSensorSpec::uav.searchRadar",
      "supplier_element": "RadarVendor::payload.radar",
      "mapping_type": "allocation",
      "rationale": "Usage-to-usage allocation: the spec radar instance sits inside uav, the vendor radar instance sits inside payload, and their types are the aliased pair SearchRadar / RadarModule_def."
    },
    {
      "oem_element": "UavSensorSpec::uav.eoCamera",
      "supplier_element": "RadarVendor::payload.gimbal",
      "mapping_type": "allocation",
      "rationale": "Usage-to-usage allocation: the spec EO camera instance sits inside uav, the vendor gimbal camera instance sits inside payload, and their types are the aliased pair Camera / GimbalCamera_def."
    }
  ],
  "unmatched": [
    "RadarVendor::RadarModule_def::massKg"
  ]
}
```