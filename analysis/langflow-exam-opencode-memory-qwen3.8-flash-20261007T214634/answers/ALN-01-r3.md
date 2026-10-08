```sysml
package AlignCamera {
    private import UsvPayloadSpec::*;
    private import OptronicsKit::*;

    alias ImageryPort for OptronicsKit::VideoOut;
    alias Camera for OptronicsKit::EoCameraUnit;
    alias imagery for OptronicsKit::EoCameraUnit::videoOut;
    alias drawW for OptronicsKit::EoCameraUnit::powerDrawW;
    alias Processor for OptronicsKit::VideoSink;
    alias imageryIn for OptronicsKit::VideoSink::videoIn;

    allocation platformAlloc allocate UsvPayloadSpec::usv to OptronicsKit::kit;
    allocation cameraAlloc allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
    allocation recorderAlloc allocate UsvPayloadSpec::usv.processor to OptronicsKit::kit.recorder;
}
```
```json
{
  "mappings": [
    {
      "oem_element": "UsvPayloadSpec::ImageryPort",
      "supplier_element": "OptronicsKit::VideoOut",
      "mapping_type": "alias",
      "rationale": "Both are port definitions for the camera's video/imagery stream; the supplier VideoOut is the kit's realization of the specified ImageryPort."
    },
    {
      "oem_element": "UsvPayloadSpec::Camera",
      "supplier_element": "OptronicsKit::EoCameraUnit",
      "mapping_type": "alias",
      "rationale": "The specified EO camera part definition corresponds to the supplier's EoCameraUnit part definition."
    },
    {
      "oem_element": "UsvPayloadSpec::Camera::imagery",
      "supplier_element": "OptronicsKit::EoCameraUnit::videoOut",
      "mapping_type": "alias",
      "rationale": "Feature-to-feature: the camera's imagery output port is realized by the kit unit's videoOut port; both carry the stream typed by the aliased port definition."
    },
    {
      "oem_element": "UsvPayloadSpec::Camera::drawW",
      "supplier_element": "OptronicsKit::EoCameraUnit::powerDrawW",
      "mapping_type": "alias",
      "rationale": "Both attributes express the camera's electrical power draw in watts; the supplier powerDrawW is the kit's value of the specified drawW."
    },
    {
      "oem_element": "UsvPayloadSpec::Processor",
      "supplier_element": "OptronicsKit::VideoSink",
      "mapping_type": "alias",
      "rationale": "The specified downstream imagery-consuming part definition corresponds to the supplier's VideoSink part definition."
    },
    {
      "oem_element": "UsvPayloadSpec::Processor::imageryIn",
      "supplier_element": "OptronicsKit::VideoSink::videoIn",
      "mapping_type": "alias",
      "rationale": "Feature-to-feature: the processor's imagery input port is realized by the sink's videoIn port."
    },
    {
      "oem_element": "UsvPayloadSpec::usv",
      "supplier_element": "OptronicsKit::kit",
      "mapping_type": "allocation",
      "rationale": "Usage-to-usage: the top-level USV payload assembly usage is allocated to the supplier's kit assembly usage."
    },
    {
      "oem_element": "UsvPayloadSpec::usv.eoCamera",
      "supplier_element": "OptronicsKit::kit.cameraUnit",
      "mapping_type": "allocation",
      "rationale": "The specified EO camera part usage is satisfied by the kit's cameraUnit part usage."
    },
    {
      "oem_element": "UsvPayloadSpec::usv.processor",
      "supplier_element": "OptronicsKit::kit.recorder",
      "mapping_type": "allocation",
      "rationale": "The specified processor part usage is satisfied by the kit's recorder (VideoSink) part usage."
    }
  ],
  "unmatched": [
    "OptronicsKit::EoCameraUnit::heaterW"
  ]
}
```