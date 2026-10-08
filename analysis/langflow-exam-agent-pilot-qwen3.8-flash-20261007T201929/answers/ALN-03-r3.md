```sysml
package AlignRadar {
    private import UavSensorSpec::*;
    private import RadarVendor::*;

    alias SearchRadar for RadarVendor::RadarModule_def;
    alias Camera for RadarVendor::GimbalCamera_def;
    alias rangeKm for RadarVendor::RadarModule_def::maxRangeKm;

    allocation allocateSearchRadar allocate UavSensorSpec::uav.searchRadar to RadarVendor::payload.radar;
    allocation allocateCamera allocate UavSensorSpec::uav.eoCamera to RadarVendor::payload.gimbal;
}
```

```json
{
  "mappings": [
    {
      "oem_element": "UavSensorSpec::SearchRadar",
      "supplier_element": "RadarVendor::RadarModule_def",
      "mapping_type": "alias",
      "rationale": "The spec's search radar definition and the vendor's radar module definition denote the same kind of part: the radar carried by the UAV. Vendor RadarModule_def is the concrete realization of SearchRadar."
    },
    {
      "oem_element": "UavSensorSpec::Camera",
      "supplier_element": "RadarVendor::GimbalCamera_def",
      "mapping_type": "alias",
      "rationale": "Both definitions model the EO imaging payload device; the gimbal camera supplied is the vendor realization of the spec's Camera part definition."
    },
    {
      "oem_element": "UavSensorSpec::SearchRadar::rangeKm",
      "supplier_element": "RadarVendor::RadarModule_def::maxRangeKm",
      "mapping_type": "alias",
      "rationale": "Same quantity and unit domain (real, kilometres) describing the radar range figure of the same part definition; the spec's rangeKm is the vendor's maxRangeKm."
    },
    {
      "oem_element": "UavSensorSpec::uav::searchRadar",
      "supplier_element": "RadarVendor::payload::radar",
      "mapping_type": "allocation",
      "rationale": "The spec's searchRadar usage typed by SearchRadar is satisfied by the vendor radar usage typed by the aliased RadarModule_def, at the matching nesting level inside the carried payload."
    },
    {
      "oem_element": "UavSensorSpec::uav::eoCamera",
      "supplier_element": "RadarVendor::payload::gimbal",
      "mapping_type": "allocation",
      "rationale": "The spec's eoCamera usage typed by Camera is satisfied by the vendor gimbal usage typed by the aliased GimbalCamera_def, in the same position within the payload structure."
    }
  ],
  "unmatched": [
    "RadarVendor::RadarModule_def::massKg",
    "UavSensorSpec::uav",
    "RadarVendor::payload"
  ]
}
```