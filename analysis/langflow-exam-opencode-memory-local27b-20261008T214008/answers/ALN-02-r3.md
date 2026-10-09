```sysml
package AlignLink {
    private import ShipLinkIcd::*;
    private import VendorRadioPack::*;
    alias Radio for VendorRadioPack::RadioUnit;
    alias LinkPort for VendorRadioPack::DataLink;
    alias HealthPort for VendorRadioPack::StatusOut;
    alias CommandShip for VendorRadioPack::ShipTerminal;
    alias uplinkMbps for VendorRadioPack::RadioUnit::linkRateMbps;
    alias toShore for VendorRadioPack::RadioUnit::dataOut;
    alias health for VendorRadioPack::RadioUnit::status;
    alias fromUsv for VendorRadioPack::ShipTerminal::linkA;
    allocation radio allocate ShipLinkIcd::usv.radio to VendorRadioPack::vessel.radioUnit;
    allocation link allocate ShipLinkIcd::commandShip.fromUsv to VendorRadioPack::terminal.linkA;
}
```

```json
{
  "mappings": [
    {"oem_element": "ShipLinkIcd::Radio", "supplier_element": "VendorRadioPack::RadioUnit", "mapping_type": "alias", "rationale": "Both define the radio part; RadioUnit carries the same uplink data and status roles."},
    {"oem_element": "ShipLinkIcd::LinkPort", "supplier_element": "VendorRadioPack::DataLink", "mapping_type": "alias", "rationale": "Both are the data link port type used for the uplink to the ship terminal."},
    {"oem_element": "ShipLinkIcd::HealthPort", "supplier_element": "VendorRadioPack::StatusOut", "mapping_type": "alias", "rationale": "Both are status/health reporting port types on the radio."},
    {"oem_element": "ShipLinkIcd::CommandShip", "supplier_element": "VendorRadioPack::ShipTerminal", "mapping_type": "alias", "rationale": "Both define the ship-side terminal part that receives the uplink."},
    {"oem_element": "ShipLinkIcd::Radio::uplinkMbps", "supplier_element": "VendorRadioPack::RadioUnit::linkRateMbps", "mapping_type": "alias", "rationale": "Both are the uplink link rate attribute in Mbps on the radio."},
    {"oem_element": "ShipLinkIcd::Radio::toShore", "supplier_element": "VendorRadioPack::RadioUnit::dataOut", "mapping_type": "alias", "rationale": "Both are the radio data output port toward the ship terminal."},
    {"oem_element": "ShipLinkIcd::Radio::health", "supplier_element": "VendorRadioPack::RadioUnit::status", "mapping_type": "alias", "rationale": "Both are the radio status/health output port."},
    {"oem_element": "ShipLinkIcd::CommandShip::fromUsv", "supplier_element": "VendorRadioPack::ShipTerminal::linkA", "mapping_type": "alias", "rationale": "Both are the terminal input port receiving the USV uplink (the connected link)."},
    {"oem_element": "ShipLinkIcd::usv.radio", "supplier_element": "VendorRadioPack::vessel.radioUnit", "mapping_type": "allocation", "rationale": "Both are the radio part usage inside the vessel."},
    {"oem_element": "ShipLinkIcd::commandShip.fromUsv", "supplier_element": "VendorRadioPack::terminal.linkA", "mapping_type": "allocation", "rationale": "Both are the terminal-side usage of the USV uplink port in the connected instances."}
  ],
  "unmatched": [
    "ShipLinkIcd::CommandShip::fromUav",
    "ShipLinkIcd::usv",
    "ShipLinkIcd::commandShip",
    "VendorRadioPack::ControlIn",
    "VendorRadioPack::RadioUnit::control",
    "VendorRadioPack::RadioUnit::txPowerW",
    "VendorRadioPack::ShipTerminal::linkB",
    "VendorRadioPack::vessel",
    "VendorRadioPack::terminal"
  ]
}
```