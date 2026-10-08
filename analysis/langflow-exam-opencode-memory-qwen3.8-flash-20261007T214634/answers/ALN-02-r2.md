```sysml
package AlignLink {
    private import ShipLinkIcd::*;
    private import VendorRadioPack::*;
    alias LinkPort for VendorRadioPack::DataLink;
    alias HealthPort for VendorRadioPack::StatusOut;
    alias Radio for VendorRadioPack::RadioUnit;
    alias CommandShip for VendorRadioPack::ShipTerminal;
    alias uplinkMbps for VendorRadioPack::RadioUnit::linkRateMbps;
    alias toShore for VendorRadioPack::RadioUnit::dataOut;
    alias health for VendorRadioPack::RadioUnit::status;
    allocation usvToVessel allocate ShipLinkIcd::usv to VendorRadioPack::vessel;
    allocation usvRadioToVesselRadioUnit allocate ShipLinkIcd::usv.radio to VendorRadioPack::vessel.radioUnit;
    allocation commandShipToTerminal allocate ShipLinkIcd::commandShip to VendorRadioPack::terminal;
}
```

```json
{
  "mappings": [
    {"oem_element": "ShipLinkIcd::LinkPort", "supplier_element": "VendorRadioPack::DataLink", "mapping_type": "alias", "rationale": "Both port definitions type the radio data-link interface; every LinkPort usage in the ICD corresponds to a DataLink usage in the pack."},
    {"oem_element": "ShipLinkIcd::HealthPort", "supplier_element": "VendorRadioPack::StatusOut", "mapping_type": "alias", "rationale": "Both port definitions carry the radio's health/status reporting out of the unit; one-to-one by type and role."},
    {"oem_element": "ShipLinkIcd::Radio", "supplier_element": "VendorRadioPack::RadioUnit", "mapping_type": "alias", "rationale": "The ICD radio definition and the vendor radio unit are the same onboard link device with matching port/attribute structure."},
    {"oem_element": "ShipLinkIcd::CommandShip", "supplier_element": "VendorRadioPack::ShipTerminal", "mapping_type": "alias", "rationale": "Both definitions model the ship-side terminal that terminates the radio's data link; they play the same architecture role."},
    {"oem_element": "ShipLinkIcd::Radio::uplinkMbps", "supplier_element": "VendorRadioPack::RadioUnit::linkRateMbps", "rationale": "Same quantity: the radio's link rate in Mbps; units and purpose match exactly.", "mapping_type": "alias"},
    {"oem_element": "ShipLinkIcd::Radio::toShore", "supplier_element": "VendorRadioPack::RadioUnit::dataOut", "mapping_type": "alias", "rationale": "One-to-one: each is the radio's only outbound LinkPort/DataLink usage and is the endpoint of the radio-to-ship connection in its own model."},
    {"oem_element": "ShipLinkIcd::Radio::health", "supplier_element": "VendorRadioPack::RadioUnit::status", "mapping_type": "alias", "rationale": "One-to-one: each is the radio's only health/status port, typed by the aliased HealthPort/StatusOut definitions."},
    {"oem_element": "ShipLinkIcd::usv", "supplier_element": "VendorRadioPack::vessel", "mapping_type": "allocation", "rationale": "The platform part usage that hosts the radio: ICD's usv corresponds to the vendor pack's vessel."},
    {"oem_element": "ShipLinkIcd::usv.radio", "supplier_element": "VendorRadioPack::vessel.radioUnit", "mapping_type": "allocation", "rationale": "The radio part usage on the host platform; both instantiate the aliased Radio/RadioUnit definitions at the same structural path."},
    {"oem_element": "ShipLinkIcd::commandShip", "supplier_element": "VendorRadioPack::terminal", "mapping_type": "allocation", "rationale": "The ship-side terminal part usage; both instantiate the aliased CommandShip/ShipTerminal definitions."}
  ],
  "unmatched": [
    "ShipLinkIcd::CommandShip::fromUsv",
    "ShipLinkIcd::CommandShip::fromUav",
    "VendorRadioPack::ShipTerminal::linkA",
    "VendorRadioPack::ShipTerminal::linkB",
    "VendorRadioPack::ControlIn",
    "VendorRadioPack::RadioUnit::control",
    "VendorRadioPack::RadioUnit::txPowerW"
  ]
}
```