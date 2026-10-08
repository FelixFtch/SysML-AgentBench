```sysml
package AlignCamera {
    private import UsvPayloadSpec::*;
    private import OptronicsKit::*;

    alias Camera for OptronicsKit::EoCameraUnit;
    alias Processor for OptronicsKit::VideoSink;
    alias ImageryPort for OptronicsKit::VideoOut;
    alias imagery for OptronicsKit::EoCameraUnit::videoOut;
    alias imageryIn for OptronicsKit::VideoSink::videoIn;
    alias drawW for OptronicsKit::EoCameraUnit::powerDrawW;

    allocation usvToKit allocate UsvPayloadSpec::usv to OptronicsKit::kit;
    allocation cameraToUnit allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
    allocation processorToRecorder allocate UsvPayloadSpec::usv.processor to OptronicsKit::kit.recorder;
}
```

```json
{
  "mappings": [
    {
      "oem_element": "UsvPayloadSpec::Camera",
      "supplier_element": "OptronicsKit::EoCameraUnit",
      "mapping_type": "alias",
      "rationale": "Both are the electro-optical camera payload definition; the supplier unit is the kit realization of the specified camera."
    },
    {
      "oem_element": "UsvPayloadSpec::Processor",
      "supplier_element": "OptronicsKit::VideoSink",
      "mapping_type": "alias",
      "rationale": "The spec processor is the consumer/end of the imagery stream, which in the kit is the video sink that receives videoIn."
    },
    {
      "oem_element": "UsvPayloadSpec::ImageryPort",
      "supplier_element": "OptronicsKit::VideoOut",
      "mapping_type": "alias",
      "rationale": "Same single imagery/video data port type: the spec port def is typed by the kit VideoOut port def on both ends of the connection."
    },
    {
      "oem_element": "UsvPayloadSpec::Camera::imagery",
      "supplier_element": "OptronicsKit::EoCameraUnit::videoOut",
      "mapping_type": "alias",
      "rationale": "Camera output imagery port usage maps one-to-one to the supplier camera unit's video output port usage."
    },
    {
      "oem_element": "UsvPayloadSpec::Processor::imageryIn",
      "supplier_element": "OptronicsKit::VideoSink::videoIn",
      "mapping_type": "alias",
      "rationale": "Inbound imagery port of the processor is the same feature as the video sink's inbound port; both are the far end of the camera-to-processor link."
    },
    {
      "oem_element": "UsvPayloadSpec::Camera::drawW",
      "supplier_element": "OptronicsKit::EoCameraUnit::powerDrawW",
      "mapping_type": "alias",
      "rationale": "Same quantity, camera electrical power draw in watts (Real); names differ only by style."
    },
    {
      "oem_element": "UsvPayloadSpec::usv",
      "supplier_element": "OptronicsKit::kit",
      "mapping_type": "allocation",
      "rationale": "The spec assembly usage that holds the payload parts is allocated to the supplier kit assembly usage."
    },
    {
      "oem_element": "UsvPayloadSpec::usv.eoCamera",
      "supplier_element": "OptronicsKit::kit.cameraUnit",
      "mapping_type": "allocation",
      "rationale": "The required EO camera part instance is satisfied by the kit's cameraUnit instance of EoCameraUnit."
    },
    {
      "oem_element": "UsvPayloadSpec::usv.processor",
      "supplier_element": "OptronicsKit::kit.recorder",
      "mapping_type": "allocation",
      "rationale": "The imagery-consuming processor instance is satisfied by the kit's recorder instance of VideoSink."
    }
  ],
  "unmatched": [
    "OptronicsKit::EoCameraUnit::heaterW",
    "OptronicsKit::kit::connect cameraUnit.videoOut to recorder.videoIn",
    "UsvPayloadSpec::usv::connect eoCamera.imagery to processor.imageryIn"
  ]
}
```