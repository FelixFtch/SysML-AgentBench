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

    allocation allocUsv allocate UsvPayloadSpec::usv to OptronicsKit::kit;
    allocation allocEoCamera allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
    allocation allocProcessor allocate UsvPayloadSpec::usv.processor to OptronicsKit::kit.recorder;
}
```

```json
{
  "mappings": [
    {
      "oem_element": "UsvPayloadSpec::ImageryPort",
      "supplier_element": "OptronicsKit::VideoOut",
      "mapping_type": "alias",
      "rationale": "Both port definitions type the video/imagery interface carried between the camera and the downstream consumer; the supplier's VideoOut is the kit realization of the spec's ImageryPort."
    },
    {
      "oem_element": "UsvPayloadSpec::Camera",
      "supplier_element": "OptronicsKit::EoCameraUnit",
      "mapping_type": "alias",
      "rationale": "The electro-optical camera payload part definition: one imagery output port plus a power-draw attribute in both models."
    },
    {
      "oem_element": "UsvPayloadSpec::Processor",
      "supplier_element": "OptronicsKit::VideoSink",
      "mapping_type": "alias",
      "rationale": "The downstream element that consumes the imagery stream through a single input port of the same port type."
    },
    {
      "oem_element": "UsvPayloadSpec::Camera::imagery",
      "supplier_element": "OptronicsKit::EoCameraUnit::videoOut",
      "mapping_type": "alias",
      "rationale": "Camera output imagery port usage maps to the camera unit's video output port usage; both are typed by the aliased port def."
    },
    {
      "oem_element": "UsvPayloadSpec::Processor::imageryIn",
      "supplier_element": "OptronicsKit::VideoSink::videoIn",
      "mapping_type": "alias",
      "rationale": "Sink-side input imagery port usage maps to the video sink's input port usage; both typed by the aliased port def."
    },
    {
      "oem_element": "UsvPayloadSpec::Camera::drawW",
      "supplier_element": "OptronicsKit::EoCameraUnit::powerDrawW",
      "mapping_type": "alias",
      "rationale": "Both are Real attributes expressing total camera payload power draw in watts; same name meaning and unit."
    },
    {
      "oem_element": "UsvPayloadSpec::usv",
      "supplier_element": "OptronicsKit::kit",
      "mapping_type": "allocation",
      "rationale": "Top-level part usages: the spec's USV assembly is satisfied by the supplier's delivered kit assembly."
    },
    {
      "oem_element": "UsvPayloadSpec::usv.eoCamera",
      "supplier_element": "OptronicsKit::kit.cameraUnit",
      "mapping_type": "allocation",
      "rationale": "EO camera part usage in the USV is satisfied by the kit's camera unit part usage (their definitions are aliased)."
    },
    {
      "oem_element": "UsvPayloadSpec::usv.processor",
      "supplier_element": "OptronicsKit::kit.recorder",
      "mapping_type": "allocation",
      "rationale": "Imagery-consuming part usage in the USV is satisfied by the kit's video sink/recorder part usage (their definitions are aliased)."
    }
  ],
  "unmatched": [
    "OptronicsKit::EoCameraUnit::heaterW"
  ]
}
```