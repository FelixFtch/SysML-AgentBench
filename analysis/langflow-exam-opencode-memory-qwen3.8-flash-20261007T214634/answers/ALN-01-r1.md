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

    allocation allocateUsvToKit allocate UsvPayloadSpec::usv to OptronicsKit::kit;
    allocation allocateEoCameraToCameraUnit allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
    allocation allocateProcessorToRecorder allocate UsvPayloadSpec::usv.processor to OptronicsKit::kit.recorder;
}
```

```json
{
  "mappings": [
    {
      "oem_element": "UsvPayloadSpec::ImageryPort",
      "supplier_element": "OptronicsKit::VideoOut",
      "mapping_type": "alias",
      "rationale": "Both port definitions type the single imagery/video link between the camera and its consumer; same structural role in both models."
    },
    {
      "oem_element": "UsvPayloadSpec::Camera",
      "supplier_element": "OptronicsKit::EoCameraUnit",
      "mapping_type": "alias",
      "rationale": "The specification camera part definition corresponds to the supplier electro-optical camera unit; each exposes one outbound imagery/video port and a power-draw attribute."
    },
    {
      "oem_element": "UsvPayloadSpec::Processor",
      "supplier_element": "OptronicsKit::VideoSink",
      "mapping_type": "alias",
      "rationale": "The imagery/video consumer definition: it owns the inbound port of the same port type and is the sink end of the camera-to-consumer connection in both models."
    },
    {
      "oem_element": "UsvPayloadSpec::Camera::imagery",
      "supplier_element": "OptronicsKit::EoCameraUnit::videoOut",
      "mapping_type": "alias",
      "rationale": "Feature-to-feature: the camera's outbound imagery port usage maps to the supplier unit's outbound video port usage of the aliased port definition."
    },
    {
      "oem_element": "UsvPayloadSpec::Processor::imageryIn",
      "supplier_element": "OptronicsKit::VideoSink::videoIn",
      "mapping_type": "alias",
      "rationale": "Feature-to-feature: the inbound imagery port usage on the consumer maps to the supplier sink's inbound video port usage."
    },
    {
      "oem_element": "UsvPayloadSpec::Camera::drawW",
      "supplier_element": "OptronicsKit::EoCameraUnit::powerDrawW",
      "mapping_type": "alias",
      "rationale": "Both are Real attributes of the camera definition expressing unit power draw in watts; same meaning and type."
    },
    {
      "oem_element": "UsvPayloadSpec::usv",
      "supplier_element": "OptronicsKit::kit",
      "mapping_type": "allocation",
      "rationale": "Root assembly usages: each is the top-level composition containing exactly the camera usage, the consumer usage, and the camera-to-consumer connection."
    },
    {
      "oem_element": "UsvPayloadSpec::usv.eoCamera",
      "supplier_element": "OptronicsKit::kit.cameraUnit",
      "mapping_type": "allocation",
      "rationale": "Usage-to-usage: the specification's EO camera part usage (typed by Camera) is satisfied by the supplier's cameraUnit part usage (typed by the aliased EoCameraUnit)."
    },
    {
      "oem_element": "UsvPayloadSpec::usv.processor",
      "supplier_element": "OptronicsKit::kit.recorder",
      "mapping_type": "allocation",
      "rationale": "Usage-to-usage: the specification's imagery consumer part usage is satisfied by the supplier recorder usage (typed by the aliased VideoSink), the sink end of the corresponding connection."
    }
  ],
  "unmatched": [
    "OptronicsKit::EoCameraUnit::heaterW"
  ]
}
```