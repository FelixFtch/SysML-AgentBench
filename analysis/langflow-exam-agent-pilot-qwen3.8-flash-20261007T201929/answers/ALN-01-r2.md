```sysml
package AlignCamera {
    private import UsvPayloadSpec::*;
    private import OptronicsKit::*;

    alias ImageryPort for OptronicsKit::VideoOut;
    alias Camera for OptronicsKit::EoCameraUnit;
    alias Processor for OptronicsKit::VideoSink;

    alias drawW for OptronicsKit::EoCameraUnit::powerDrawW;
    alias imagery for OptronicsKit::EoCameraUnit::videoOut;
    alias imageryIn for OptronicsKit::VideoSink::videoIn;

    allocation alignTop      allocate UsvPayloadSpec::usv          to OptronicsKit::kit;
    allocation alignCamera   allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
    allocation alignProcessr allocate UsvPayloadSpec::usv.processor to OptronicsKit::kit.recorder;
}
```

```json
{
  "mappings": [
    {"oem_element": "UsvPayloadSpec::ImageryPort", "supplier_element": "OptronicsKit::VideoOut", "mapping_type": "alias", "rationale": "Both are port definitions typed by the parts' video/imagery interface; the supplier's VideoOut is the kit-level name for the same imagery port type."},
    {"oem_element": "UsvPayloadSpec::Camera", "supplier_element": "OptronicsKit::EoCameraUnit", "mapping_type": "alias", "rationale": "Same role: electro-optical camera payload part definition exposing one imagery/video output port and a power-draw attribute."},
    {"oem_element": "UsvPayloadSpec::Processor", "supplier_element": "OptronicsKit::VideoSink", "mapping_type": "alias", "rationale": "Same role: downstream part definition that consumes the camera's video/imagery stream on a single input port."},
    {"oem_element": "UsvPayloadSpec::Camera::drawW", "supplier_element": "OptronicsKit::EoCameraUnit::powerDrawW", "mapping_type": "alias", "rationale": "Both are Real attributes expressing the camera unit's electrical power draw; names differ only in abbreviation."},
    {"oem_element": "UsvPayloadSpec::Camera::imagery", "supplier_element": "OptronicsKit::EoCameraUnit::videoOut", "mapping_type": "alias", "rationale": "Corresponding output port usages of the camera part definitions, typed by the aliased ImageryPort/VideoOut port definitions."},
    {"oem_element": "UsvPayloadSpec::Processor::imageryIn", "supplier_element": "OptronicsKit::VideoSink::videoIn", "mapping_type": "alias", "rationale": "Corresponding input port usages of the consuming part definitions, typed by the same aliased port definition."},
    {"oem_element": "UsvPayloadSpec::usv", "supplier_element": "OptronicsKit::kit", "mapping_type": "allocation", "rationale": "Top-level part usages: the OEM vehicle payload assembly is realised by the supplier kit assembly."},
    {"oem_element": "UsvPayloadSpec::usv.eoCamera", "supplier_element": "OptronicsKit::kit.cameraUnit", "mapping_type": "allocation", "rationale": "Usage-level pair: the specified EO camera part usage is fulfilled by the supplier's camera unit part usage of the aliased definitions."},
    {"oem_element": "UsvPayloadSpec::usv.processor", "supplier_element": "OptronicsKit::kit.recorder", "mapping_type": "allocation", "rationale": "Usage-level pair: the specified imagery processor part usage is fulfilled by the supplier's video sink/recorder part usage."}
  ],
  "unmatched": [
    "OptronicsKit::EoCameraUnit::heaterW"
  ]
}
```