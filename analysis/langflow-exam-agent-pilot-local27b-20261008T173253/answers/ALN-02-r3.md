```sysml
package AlignLink {
    private import ShipLinkIcd::*;
    private import VendorRadioPack::*;
    alias LinkPort for VendorRadioPack::DataLink;
    alias HealthPort for VendorRadioPack::StatusOut;
    alias Radio for VendorRadioPack::RadioUnit;
    alias toShore for VendorRadioPack::RadioUnit::dataOut;
    alias health for VendorRadioPack::RadioUnit::status;
    alias uplinkMbps for VendorRadioPack::RadioUnit::linkRateMbps;
    alias CommandShip for VendorRadioPack::ShipTerminal;
    alias fromUsv for VendorRadioPack::ShipTerminal::linkA;
    alias fromUav for VendorRadioPack::ShipTerminal::linkB;
    allocation usvToVessel allocate ShipLinkIcd::usv to VendorRadioPack::vessel;
    allocation radioToRadioUnit allocate ShipLinkIcd::usv.radio to VendorRadioPack::vessel.radioUnit;
    allocation commandShipToTerminal allocate ShipLinkIcd::commandShip to VendorRadioPack::terminal;
}
```

```json
{
  "mappings": [
    {"oem_element": "ShipLinkIcd::LinkPort", "supplier_element": "VendorRadioPack::DataLink", "mapping_type": "alias", "rationale": "Both are the data-link port definition used for the shore/terminal link."},
    {"oem_element": "ShipLinkIcd::HealthPort", "supplier_element": "VendorRadioPack::StatusOut", "mapping_type": "alias", "rationale": "Both are the health/status output port definition on the radio."},
    {"oem_element": "ShipLinkIcd::Radio", "supplier_element": "VendorRadioPack::RadioUnit", "mapping_type": "alias", "rationale": "Both define the shipborne radio equipment."},
    {"oem_element": "ShipLinkIcd::Radio::toShore", "supplier_element": "VendorRadioPack::RadioUnit::dataOut", "mapping_type": "alias", "rationale": "Both are the radio data port connected to the shore/terminal link (usv.radio.toShore to commandShip.fromUsv matches vessel.radioUnit.dataOut to terminal.linkA)."},
    {"oem_element": "ShipLinkIcd::Radio::health", "supplier_element": "VendorRadioPack::RadioUnit::status", "mapping_type": "alias", "rationale": "Both are the radio health/status port."},
    {"oem_element": "ShipLinkIcd::Radio::uplinkMbps", "supplier_element": "VendorRadioPack::RadioUnit::linkRateMbps", "mapping_type": "alias", "rationale": "Both are the Real-valued link rate in Mbps attribute."},
    {"oem_element": "ShipLinkIcd::CommandShip", "supplier_element": "VendorRadioPack::ShipTerminal", "mapping_type": "alias", "rationale": "Both define the shore/terminal side with two data-link ports."},
    {"oem_element": "ShipLinkIcd::CommandShip::fromUsv", "supplier_element": "VendorRadioPack::ShipTerminal::linkA", "mapping_type": "alias", "rationale": "Both are the terminal link port connected to the radio in each model."},
    {"oem_element": "ShipLinkIcd::CommandShip::fromUav", "supplier_element": "VendorRadioPack::ShipTerminal::linkB", "mapping_type": "alias", "rationale": "Both are the second data-link port on the terminal, the only remaining counterpart."},
    {"oem_element": "ShipLinkIcd::usv", "supplier_element": "VendorRadioPack::vessel", "mapping_type": "allocation", "rationale": "Both are the vessel-level part usage containing the radio."},
    {"oem_element": "ShipLinkIcd::usv.radio", "supplier_element": "VendorRadioPack::vessel.radioUnit", "mapping_type": "allocation", "rationale": "Both are the radio part usage inside the vessel."},
    {"oem_element": "ShipLinkIcd::commandShip", "supplier_element": "VendorRadioPack::terminal", "mapping_type": "allocation", "rationale": "Both are the terminal/shore-side part usage."}
  ],
  "unmatched": [
    "VendorRadioPack::ControlIn",
    "VendorRadioPack::RadioUnit::control",
    "VendorRadioPack::RadioUnit::txPowerW"
  ]
}
```