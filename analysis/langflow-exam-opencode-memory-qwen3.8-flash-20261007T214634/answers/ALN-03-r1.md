```sysml
package AlignRadar {
    private import UavSensorSpec::*;
    private import RadarVendor::*;

    alias SearchRadar for RadarVendor::RadarModule_def;
    alias Camera for RadarVendor::GimbalCamera_def;
    alias rangeKm for RadarVendor::RadarModule_def::maxRangeKm;

    allocation uavAllocation allocate UavSensorSpec::uav to RadarVendor::payload;
    allocation searchRadarAllocation allocate UavSensorSpec::uav.searchRadar to RadarVendor::payload.radar;
    allocation eoCameraAllocation allocate UavSensorSpec::uav.eoCamera to RadarVendor::payload.gimbal;
}
```

```json
{
  "mappings": [
    {
      "oem_element": "UavSensorSpec::SearchRadar",
      "supplier_element": "RadarVendor::RadarModule_def",
      "mapping_type": "alias",
      "rationale": "Both are radar sensor part definitions for the UAV's search payload; the supplier module is the vendor realization of the specified radar."
    },
    {
      "oem_element": "UavSensorSpec::SearchRadar::rangeKm",
      "supplier_element": "RadarVendor::RadarModule_def::maxRangeKm",
      "mapping_type": "alias",
      "rationale": "Both attributes express the radar's range in kilometres (Real); the vendor's maxRangeKm is the supplier's statement of the specified rangeKm parameter."
    },
    {
      "oem_element": "UavSensorSpec::Camera",
      "supplier_element": "RadarVendor::GimbalCamera_def",
      "mapping_type": "alias",
      "rationale": "Both are EO camera part definitions; the supplier's gimbal camera is the vendor's implementation of the specified camera."
    },
    {
      "oem_element": "UavSensorSpec::uav",
      "supplier_element": "RadarVendor::payload",
      "mapping_type": "allocation",
      "rationale": "The specification's top-level container usage holding the two sensor parts corresponds to the supplier's payload usage holding the same two modules; the sensor pair is the whole extent of both usages."
    },
    {
      "oem_element": "UavSensorSpec::uav.searchRadar",
      "supplier_element": "RadarVendor::payload.radar",
      "mapping_type": "allocation",
      "rationale": "The specified search radar usage is satisfied by the supplier's radar module usage typed by the aliased RadarModule_def."
    },
    {
      "oem_element": "UavSensorSpec::uav.eoCamera",
      "supplier_element": "RadarVendor::payload.gimbal",
      "mapping_type": "allocation",
      "rationale": "The specified EO camera usage is satisfied by the supplier's gimbal camera usage typed by the aliased GimbalCamera_def."
    }
  ],
  "unmatched": [
    "RadarVendor::RadarModule_def::massKg"
  ]
}
```