```sysml
package AlignCamera {
    public import UsvPayloadSpec::*;
    public import OptronicsKit::*;
    alias Camera for OptronicsKit::EoCameraUnit;
    alias Processor for OptronicsKit::VideoSink;
    alias ImageryPort for OptronicsKit::VideoOut;
    allocation camera allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
    allocation processor allocate UsvPayloadSpec::usv.processor to OptronicsKit::kit.recorder;
}
```

```json
{
  "mappings": [
    {
      "oem_element": "Camera",
      "supplier_element": "OptronicsKit::EoCameraUnit",
      "mapping_type": "alias",
      "rationale": "Part definitions with matching imagery/video output port and power draw semantics."
    },
    {
      "oem_element": "Processor",
      "supplier_element": "OptronicsKit::VideoSink",
      "mapping_type": "alias",
      "rationale": "Part definitions consuming the imagery/video stream."
    },
    {
      "oem_element": "ImageryPort",
      "supplier_element": "OptronicsKit::VideoOut",
      "mapping_type": "alias",
      "rationale": "Port definitions describing the imagery/video output interface."
    },
    {
      "oem_element": "UsvPayloadSpec::usv.eoCamera",
      "supplier_element": "OptronicsKit::kit.cameraUnit",
      "mapping_type": "allocation",
      "rationale": "Camera part usage allocated to supplier camera unit part usage."
    },
    {
      "oem_element": "UsvPayloadSpec::usv.processor",
      "supplier_element": "OptronicsKit::kit.recorder",
      "mapping_type": "allocation",
      "rationale": "Processor part usage allocated to supplier recorder part usage."
    }
  ],
  "unmatched": [
    "UsvPayloadSpec::drawW",
    "OptronicsKit::powerDrawW",
    "OptronicsKit::heaterW",
    "UsvPayloadSpec::usv",
    "OptronicsKit::kit"
  ]
}
```