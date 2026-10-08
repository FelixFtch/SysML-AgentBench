```sysml
package AlignCamera {
    public import UsvPayloadSpec::*;
    public import OptronicsKit::*;

    alias Camera for OptronicsKit::EoCameraUnit;
    alias Processor for OptronicsKit::VideoSink;
    alias ImageryPort for OptronicsKit::VideoOut;

    alias imagery for OptronicsKit::EoCameraUnit::videoOut;
    alias imageryIn for OptronicsKit::VideoSink::videoIn;
    alias drawW for OptronicsKit::EoCameraUnit::powerDrawW;

    allocation usvToKit allocate UsvPayloadSpec::usv to OptronicsKit::kit;
    allocation eoCameraToCameraUnit allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
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
      "rationale": "Both part definitions describe the electro-optical camera payload carrying one imagery/video output port and a power-draw attribute."
    },
    {
      "oem_element": "UsvPayloadSpec::Processor",
      "supplier_element": "OptronicsKit::VideoSink",
      "mapping_type": "alias",
      "rationale": "Both part definitions play the downstream consumer role with a single inbound imagery/video port."
    },
    {
      "oem_element": "UsvPayloadSpec::ImageryPort",
      "supplier_element": "OptronicsKit::VideoOut",
      "mapping_type": "alias",
      "rationale": "The specification imagery port and the kit video output port are the same one-way imagery/video interface used on both the source and the sink side."
    },
    {
      "oem_element": "UsvPayloadSpec::Camera::imagery",
      "supplier_element": "OptronicsKit::EoCameraUnit::videoOut",
      "mapping_type": "alias",
      "rationale": "Camera-side outbound imagery port feature corresponds to the kit camera unit's outbound video port feature."
    },
    {
      "oem_element": "UsvPayloadSpec::Processor::imageryIn",
      "supplier_element": "OptronicsKit::VideoSink::videoIn",
      "mapping_type": "alias",
      "rationale": "Sink-side inbound imagery port feature corresponds to the kit video sink's inbound video port feature."
    },
    {
      "oem_element": "UsvPayloadSpec::Camera::drawW",
      "supplier_element": "OptronicsKit::EoCameraUnit::powerDrawW",
      "mapping_type": "alias",
      "rationale": "Both are Real attributes of the camera unit expressing the same quantity, camera electrical power draw in watts."
    },
    {
      "oem_element": "UsvPayloadSpec::usv",
      "supplier_element": "OptronicsKit::kit",
      "mapping_type": "allocation",
      "rationale": "The specification top-level assembly usage is fulfilled by the supplier kit usage, which encloses the matching camera and sink part usages."
    },
    {
      "oem_element": "UsvPayloadSpec::usv.eoCamera",
      "supplier_element": "OptronicsKit::kit.cameraUnit",
      "mapping_type": "allocation",
      "rationale": "The required EO camera part usage is allocated to the supplier kit's camera unit part usage."
    },
    {
      "oem_element": "UsvPayloadSpec::usv.processor",
      "supplier_element": "OptronicsKit::kit.recorder",
      "mapping_type": "allocation",
      "rationale": "The required imagery-consuming processor part usage is allocated to the supplier kit's recorder part usage."
    }
  ],
  "unmatched": [
    "OptronicsKit::EoCameraUnit::heaterW"
  ]
}
```