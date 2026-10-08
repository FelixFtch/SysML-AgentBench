```sysml
package AlignCamera {
    private import UsvPayloadSpec::*;
    private import OptronicsKit::*;
    alias ImageryPort for OptronicsKit::VideoOut;
    alias Camera for OptronicsKit::EoCameraUnit;
    alias Processor for OptronicsKit::VideoSink;
    alias usv for OptronicsKit::kit;
    alias imagery for OptronicsKit::EoCameraUnit::videoOut;
    alias drawW for OptronicsKit::EoCameraUnit::powerDrawW;
    alias imageryIn for OptronicsKit::VideoSink::videoIn;
    allocation eoCamera allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
    allocation processor allocate UsvPayloadSpec::usv.processor to OptronicsKit::kit.recorder;
}
```

```json
{
  "mappings": [
    {"oem_element": "UsvPayloadSpec::ImageryPort", "supplier_element": "OptronicsKit::VideoOut", "mapping_type": "alias", "rationale": "Both are port definitions for the imagery/video signal interface."},
    {"oem_element": "UsvPayloadSpec::Camera", "supplier_element": "OptronicsKit::EoCameraUnit", "mapping_type": "alias", "rationale": "Both are part definitions for the electro-optical camera unit."},
    {"oem_element": "UsvPayloadSpec::Processor", "supplier_element": "OptronicsKit::VideoSink", "mapping_type": "alias", "rationale": "Both are part definitions for the component that receives the imagery stream."},
    {"oem_element": "UsvPayloadSpec::usv", "supplier_element": "OptronicsKit::kit", "mapping_type": "alias", "rationale": "Both are part definitions assembling the camera with the imagery sink."},
    {"oem_element": "UsvPayloadSpec::Camera::imagery", "supplier_element": "OptronicsKit::EoCameraUnit::videoOut", "mapping_type": "alias", "rationale": "Camera-side imagery output port usage on both camera definitions."},
    {"oem_element": "UsvPayloadSpec::Camera::drawW", "supplier_element": "OptronicsKit::EoCameraUnit::powerDrawW", "mapping_type": "alias", "rationale": "Power draw attribute of the camera unit in both models."},
    {"oem_element": "UsvPayloadSpec::Processor::imageryIn", "supplier_element": "OptronicsKit::VideoSink::videoIn", "mapping_type": "alias", "rationale": "Imagery input port usage on the sink/processor definition in both models."},
    {"oem_element": "UsvPayloadSpec::usv.eoCamera", "supplier_element": "OptronicsKit::kit.cameraUnit", "mapping_type": "allocation", "rationale": "Spec camera part usage corresponds to the supplier kit's camera unit part usage."},
    {"oem_element": "UsvPayloadSpec::usv.processor", "supplier_element": "OptronicsKit::kit.recorder", "mapping_type": "allocation", "rationale": "Spec processor part usage corresponds to the supplier kit's recorder part usage."}
  ],
  "unmatched": [
    "OptronicsKit::EoCameraUnit::heaterW"
  ]
}
```