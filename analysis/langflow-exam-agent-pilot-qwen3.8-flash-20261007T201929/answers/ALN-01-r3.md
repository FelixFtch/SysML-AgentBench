```sysml
package AlignCamera {
    private import UsvPayloadSpec::*;
    private import OptronicsKit::*;

    // Definition / feature level correspondences (specification short name -> supplier qualified name)
    alias ImageryPort for OptronicsKit::VideoOut;
    alias Camera for OptronicsKit::EoCameraUnit;
    alias Processor for OptronicsKit::VideoSink;
    alias imagery for OptronicsKit::EoCameraUnit::videoOut;
    alias imageryIn for OptronicsKit::VideoSink::videoIn;
    alias drawW for OptronicsKit::EoCameraUnit::powerDrawW;

    // Usage level correspondences (fully qualified dotted usage paths)
    allocation usvToKit allocate UsvPayloadSpec::usv to OptronicsKit::kit;
    allocation eoCameraToCameraUnit allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
    allocation processorToRecorder allocate UsvPayloadSpec::usv.processor to OptronicsKit::kit.recorder;
}
```

```json
{
  "mappings": [
    {
      "oem_element": "UsvPayloadSpec::ImageryPort",
      "supplier_element": "OptronicsKit::VideoOut",
      "mapping_type": "alias",
      "rationale": "Both are port definitions typing the single outbound imagery/video stream of the camera and its inbound counterpart; the OEM imagery interface is realized by the supplier video output interface."
    },
    {
      "oem_element": "UsvPayloadSpec::Camera",
      "supplier_element": "OptronicsKit::EoCameraUnit",
      "mapping_type": "alias",
      "rationale": "The specified electro-optical camera part definition is realized by the supplier EO camera unit part definition (same role: imager with a video port and a power-draw attribute)."
    },
    {
      "oem_element": "UsvPayloadSpec::Processor",
      "supplier_element": "OptronicsKit::VideoSink",
      "mapping_type": "alias",
      "rationale": "The OEM consumer that accepts the imagery stream corresponds to the supplier video sink, which likewise only terminates the inbound video stream."
    },
    {
      "oem_element": "UsvPayloadSpec::Camera::imagery",
      "supplier_element": "OptronicsKit::EoCameraUnit::videoOut",
      "mapping_type": "alias",
      "rationale": "Camera-side port usage of the imagery/video type; the OEM outflow port is the supplier's videoOut port usage."
    },
    {
      "oem_element": "UsvPayloadSpec::Processor::imageryIn",
      "supplier_element": "OptronicsKit::VideoSink::videoIn",
      "mapping_type": "alias",
      "rationale": "Sink-side port usage receiving the stream; OEM imageryIn matches the supplier videoIn port usage."
    },
    {
      "oem_element": "UsvPayloadSpec::Camera::drawW",
      "supplier_element": "OptronicsKit::EoCameraUnit::powerDrawW",
      "mapping_type": "alias",
      "rationale": "Same semantics and same unit (W): total camera power draw. No numeric limit exists on either side, so nothing is constrained by the mapping."
    },
    {
      "oem_element": "UsvPayloadSpec::usv",
      "supplier_element": "OptronicsKit::kit",
      "mapping_type": "allocation",
      "rationale": "The top-level OEM payload assembly usage is satisfied by the supplier kit assembly usage."
    },
    {
      "oem_element": "UsvPayloadSpec::usv.eoCamera",
      "supplier_element": "OptronicsKit::kit.cameraUnit",
      "mapping_type": "allocation",
      "rationale": "The EO camera part usage in the USV payload is allocated to the supplier's camera unit part usage in the kit."
    },
    {
      "oem_element": "UsvPayloadSpec::usv.processor",
      "supplier_element": "OptronicsKit::kit.recorder",
      "mapping_type": "allocation",
      "rationale": "The imagery-consuming part usage in the USV payload is allocated to the supplier recorder part usage, which plays the same sink role in the kit connection."
    }
  ],
  "unmatched": [
    "OptronicsKit::EoCameraUnit::heaterW"
  ]
}
```