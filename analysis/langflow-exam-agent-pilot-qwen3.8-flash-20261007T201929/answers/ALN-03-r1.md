```sysml
package AlignRadar {
    private import UavSensorSpec::*;
    private import RadarVendor::*;

    alias SearchRadar for RadarVendor::RadarModule_def;
    alias Camera for RadarVendor::GimbalCamera_def;
    alias rangeKm for RadarVendor::RadarModule_def::maxRangeKm;

    allocation uav_to_payload allocate UavSensorSpec::uav to RadarVendor::payload;
    allocation searchRadar_to_radar allocate UavSensorSpec::uav.searchRadar to RadarVendor::payload.radar;
    allocation eoCamera_to_gimbal allocate UavSensorSpec::uav.eoCamera to RadarVendor::payload.gimbal;
}
```

```json
{
  "mappings": [
    {
      "oem_element": "UavSensorSpec::SearchRadar",
      "supplier_element": "RadarVendor::RadarModule_def",
      "mapping_type": "alias",
      "rationale": "Both definitions describe the UAV's search radar payload module; the supplier part definition is the realization of the specified radar definition."
    },
    {
      "oem_element": "UavSensorSpec::Camera",
      "supplier_element": "RadarVendor::GimbalCamera_def",
      "mapping_type": "alias",
      "rationale": "The specified electro-optical camera definition corresponds to the supplier's gimbal-stabilised camera definition, which is the supplier's camera product."
    },
    {
      "oem_element": "UavSensorSpec::SearchRadar::rangeKm",
      "supplier_element": "RadarVendor::RadarModule_def::maxRangeKm",
      "mapping_type": "alias",
      "rationale": "Both attributes express the radar's range figure in kilometres, so the specified rangeKm attribute is taken to be the supplier's stated maximum range parameter."
    },
    {
      "oem_element": "UavSensorSpec::uav",
      "supplier_element": "RadarVendor::payload",
      "mapping_type": "allocation",
      "rationale": "The specified uav part usage, which carries the sensor set, is satisfied by the supplier payload part usage that carries the same radar and camera children."
    },
    {
      "oem_element": "UavSensorSpec::uav.searchRadar",
      "supplier_element": "RadarVendor::payload.radar",
      "mapping_type": "allocation",
      "rationale": "The specified radar usage (typed by SearchRadar) is allocated to the supplier radar usage typed by RadarModule_def, the two definitions being aliased to each other."
    },
    {
      "oem_element": "UavSensorSpec::uav.eoCamera",
      "supplier_element": "RadarVendor::payload.gimbal",
      "mapping_type": "allocation",
      "rationale": "The specified camera usage (typed by Camera) is allocated to the supplier camera usage typed by GimbalCamera_def, the two definitions being aliased to each other."
    }
  ],
  "unmatched": [
    "RadarVendor::RadarModule_def::massKg"
  ]
}
```