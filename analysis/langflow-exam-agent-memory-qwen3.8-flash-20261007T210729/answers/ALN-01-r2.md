```sysml
package AlignCamera {
    private import UsvPayloadSpec::*;
    private import OptronicsKit::*;

    alias ImageryPort for OptronicsKit::VideoOut;
    alias Camera for OptronicsKit::EoCameraUnit;
    alias Processor for OptronicsKit::VideoSink;

    alias imagery for OptronicsKit::EoCameraUnit::videoOut;
    alias imageryIn for OptronicsKit::VideoSink::videoIn;
    alias drawW for OptronicsKit::EoCameraUnit::powerDrawW;

    allocation cameraAllocation allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
    allocation processorAllocation allocate UsvPayloadSpec::usv.processor to OptronicsKit::kit.recorder;
}
```

```json
{
  "mappings": [
    {
      "oem_element": "UsvPayloadSpec::ImageryPort",
      "supplier_element": "OptronicsKit::VideoOut",
      "mapping_type": "alias",
      "rationale": "Both are port definitions typed by the camera video/imagery interface; the spec's ImageryPort is carried by exactly the same ports the supplier uses on its camera and sink."
    },
    {
      "oem_element": "UsvPayloadSpec::Camera",
      "supplier_element": "OptronicsKit::EoCameraUnit",
      "mapping_type": "alias",
      "rationale": "The specified EO camera part definition is realised by the supplier's EO camera unit: both own one imagery/video output port and a power-draw attribute."
    },
    {
      "oem_element": "UsvPayloadSpec::Processor",
      "supplier_element": "OptronicsKit::VideoSink",
      "mapping_type": "alias",
      "rationale": "The spec's imagery consumer, bearing a single ImageryPort-typed input, corresponds to the supplier's video sink, which bears a single VideoOut-typed input."
    },
    {
      "oem_element": "UsvPayloadSpec::Camera::imagery",
      "supplier_element": "OptronicsKit::EoCameraUnit::videoOut",
      "mapping_type": "alias",
      "rationale": "Feature-to-feature map: the camera's imagery port usage is the supplier camera unit's video output port usage, same port type after the ImageryPort/VideoOut alias."
    },
    {
      "oem_element": "UsvPayloadSpec::Processor::imageryIn",
      "supplier_element": "OptronicsKit::VideoSink::videoIn",
      "mapping_type": "alias",
      "rationale": "Feature-to-feature map: the consumer-side imagery input of the spec processor is the supplier video sink's video input."
    },
    {
      "oem_element": "UsvPayloadSpec::Camera::drawW",
      "supplier_element": "OptronicsKit::EoCameraUnit::powerDrawW",
      "mapping_type": "alias",
      "rationale": "Both are Real attributes expressing the camera's electrical power draw in watts; same meaning, different name."
    },
    {
      "oem_element": "UsvPayloadSpec::usv::eoCamera",
      "supplier_element": "OptronicsKit::kit::cameraUnit",
      "mapping_type": "allocation",
      "rationale": "The specified EO camera part usage is allocated to the supplier kit's camera unit usage of the aliased camera definition."
    },
    {
      "oem_element": "UsvPayloadSpec::usv::processor",
      "supplier_element": "OptronicsKit::kit::recorder",
      "mapping_type": "allocation",
      "rationale": "The specified imagery consumer usage is allocated to the supplier kit's recorder usage, which fulfils the VideoSink/Processor definition."
    }
  ],
  "unmatched": [
    "OptronicsKit::EoCameraUnit::heaterW",
    "UsvPayloadSpec::usv",
    "OptronicsKit::kit"
  ]
}
```