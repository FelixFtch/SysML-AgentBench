```sysml
package AlignRadar {
    alias SearchRadar for RadarVendor::RadarModule_def;
    alias Camera for RadarVendor::GimbalCamera_def;
    alias rangeKm for RadarVendor::RadarModule_def::maxRangeKm;

    allocation searchRadar allocate UavSensorSpec::uav.searchRadar to RadarVendor::payload.radar;
    allocation eoCamera allocate UavSensorSpec::uav.eoCamera to RadarVendor::payload.gimbal;
}
```

```json
{"mappings": [{"oem_element": "UavSensorSpec::SearchRadar", "supplier_element": "RadarVendor::RadarModule_def", "mapping_type": "alias", "rationale": "Specification radar definition corresponds to supplier radar module definition."}, {"oem_element": "UavSensorSpec::Camera", "supplier_element": "RadarVendor::GimbalCamera_def", "mapping_type": "alias", "rationale": "Specification camera definition corresponds to supplier gimbal camera definition."}, {"oem_element": "UavSensorSpec::SearchRadar::rangeKm", "supplier_element": "RadarVendor::RadarModule_def::maxRangeKm", "mapping_type": "alias", "rationale": "Specification range attribute corresponds to supplier max range attribute."}, {"oem_element": "UavSensorSpec::uav.searchRadar", "supplier_element": "RadarVendor::payload.radar", "mapping_type": "allocation", "rationale": "Specification search radar usage is allocated to supplier radar module usage."}, {"oem_element": "UavSensorSpec::uav.eoCamera", "supplier_element": "RadarVendor::payload.gimbal", "mapping_type": "allocation", "rationale": "Specification electro-optical camera usage is allocated to supplier gimbal camera usage."}], "unmatched": ["UavSensorSpec::uav", "UavSensorSpec::uav.eoCamera", "RadarVendor::payload", "RadarVendor::RadarModule_def::massKg"]}
```