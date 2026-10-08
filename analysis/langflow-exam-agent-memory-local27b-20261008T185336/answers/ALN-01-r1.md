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
    allocation usvKit allocate UsvPayloadSpec::usv to OptronicsKit::kit;
    allocation eoCameraUnit allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
    allocation recorder allocate UsvPayloadSpec::usv.processor to OptronicsKit::kit.recorder;
}
```

```json
{
  "mappings": [
    {"oem_element": "UsvPayloadSpec::ImageryPort", "supplier_element": "OptronicsKit::VideoOut", "mapping_type": "alias", "rationale": "Both are the port definition for the EO imagery video interface."},
    {"oem_element": "UsvPayloadSpec::Camera", "supplier_element": "OptronicsKit::EoCameraUnit", "mapping_type": "alias", "rationale": "The specification's camera part definition corresponds to the supplier's EO camera unit definition."},
    {"oem_element": "UsvPayloadSpec::Processor", "supplier_element": "OptronicsKit::VideoSink", "mapping_type": "alias", "rationale": "The specification's processor part definition corresponds to the supplier's video sink definition."},
    {"oem_element": "UsvPayloadSpec::Camera::imagery", "supplier_element": "OptronicsKit::EoCameraUnit::videoOut", "mapping_type": "alias", "rationale": "Both are the camera's outgoing imagery/video port."},
    {"oem_element": "UsvPayloadSpec::Camera::drawW", "supplier_element": "OptronicsKit::EoCameraUnit::powerDrawW", "mapping_type": "alias", "rationale": "Both are the camera's power draw attribute in watts."},
    {"oem_element": "UsvPayloadSpec::Processor::imageryIn", "supplier_element": "OptronicsKit::VideoSink::videoIn", "mapping_type": "alias", "rationale": "Both are the sink's incoming imagery/video port."},
    {"oem_element": "UsvPayloadSpec::usv", "supplier_element": "OptronicsKit::kit", "mapping_type": "allocation", "rationale": "The specification's platform-level payload assembly corresponds to the supplier's kit assembly."},
    {"oem_element": "UsvPayloadSpec::usv.eoCamera", "supplier_element": "OptronicsKit::kit.cameraUnit", "mapping_type": "allocation", "rationale": "The spec's camera instance in the USV payload is realized by the supplier's camera unit instance."},
    {"oem_element": "UsvPayloadSpec::usv.processor", "supplier_element": "OptronicsKit::kit.recorder", "mapping_type": "allocation", "rationale": "The spec's processor instance is realized by the supplier's video sink/recorder instance."}
  ],
  "unmatched": ["OptronicsKit::EoCameraUnit::heaterW"]
}
```