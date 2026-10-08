```sysml
package AlignCamera {
    private import UsvPayloadSpec::*;
    private import OptronicsKit::*;
    alias ImageryPort for OptronicsKit::VideoOut;
    alias Camera for OptronicsKit::EoCameraUnit;
    alias Processor for OptronicsKit::VideoSink;
    alias imagery for OptronicsKit::EoCameraUnit::videoOut;
    alias drawW for OptronicsKit::EoCameraUnit::powerDrawW;
    alias imageryIn for OptronicsKit::VideoSink::videoIn;
    allocation usv allocate UsvPayloadSpec::usv to OptronicsKit::kit;
    allocation eoCamera allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
    allocation processor allocate UsvPayloadSpec::usv.processor to OptronicsKit::kit.recorder;
}
```

```json
{
  "mappings": [
    {"oem_element": "UsvPayloadSpec::ImageryPort", "supplier_element": "OptronicsKit::VideoOut", "mapping_type": "alias", "rationale": "Both are the port definition carrying the imagery/video stream between camera and processor."},
    {"oem_element": "UsvPayloadSpec::Camera", "supplier_element": "OptronicsKit::EoCameraUnit", "mapping_type": "alias", "rationale": "Electro-optical camera unit definition with imagery port and power draw attribute."},
    {"oem_element": "UsvPayloadSpec::Processor", "supplier_element": "OptronicsKit::VideoSink", "mapping_type": "alias", "rationale": "Downstream imagery-consuming unit definition with a single imagery input port."},
    {"oem_element": "UsvPayloadSpec::Camera::imagery", "supplier_element": "OptronicsKit::EoCameraUnit::videoOut", "mapping_type": "alias", "rationale": "Camera-side imagery output port in both models."},
    {"oem_element": "UsvPayloadSpec::Camera::drawW", "supplier_element": "OptronicsKit::EoCameraUnit::powerDrawW", "mapping_type": "alias", "rationale": "Real-valued power draw attribute of the camera unit."},
    {"oem_element": "UsvPayloadSpec::Processor::imageryIn", "supplier_element": "OptronicsKit::VideoSink::videoIn", "mapping_type": "alias", "rationale": "Imagery input port of the processing/sink unit."},
    {"oem_element": "UsvPayloadSpec::usv", "supplier_element": "OptronicsKit::kit", "mapping_type": "allocation", "rationale": "Top-level assembly usage: the USV payload assembly corresponds to the supplier kit assembly."},
    {"oem_element": "UsvPayloadSpec::usv.eoCamera", "supplier_element": "OptronicsKit::kit.cameraUnit", "mapping_type": "allocation", "rationale": "Camera instance usage in the assembly."},
    {"oem_element": "UsvPayloadSpec::usv.processor", "supplier_element": "OptronicsKit::kit.recorder", "mapping_type": "allocation", "rationale": "Processor instance usage in the assembly."}
  ],
  "unmatched": [
    "OptronicsKit::EoCameraUnit::heaterW"
  ]
}
```