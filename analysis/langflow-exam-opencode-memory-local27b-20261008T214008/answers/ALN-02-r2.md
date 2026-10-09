```sysml
package AlignLink {
    private import ShipLinkIcd::*;
    private import VendorRadioPack::*;
    alias LinkPort for VendorRadioPack::DataLink;
    alias HealthPort for VendorRadioPack::StatusOut;
    alias Radio for VendorRadioPack::RadioUnit;
    alias CommandShip for VendorRadioPack::ShipTerminal;
    alias uplinkMbps for VendorRadioPack::RadioUnit::linkRateMbps;
    allocation usvRadioToVesselRadioUnit allocate ShipLinkIcd::usv.radio to VendorRadioPack::vessel.radioUnit;
    allocation toShoreDataOutToLinkA allocate ShipLinkIcd::usv.radio.toShore to VendorRadioPack::vessel.radioUnit.dataOut;
    allocation fromUsvToLinkA allocate ShipLinkIcd::commandShip.fromUsv to VendorRadioPack::terminal.linkA;
}
```

```json
{
  "mappings": [
    {"oem_element": "ShipLinkIcd::LinkPort", "supplier_element": "VendorRadioPack::DataLink", "mapping_type": "alias", "rationale": "Both are the ship data link port definition connecting USV radio to the command terminal."},
    {"oem_element": "ShipLinkIcd::HealthPort", "supplier_element": "VendorRadioPack::StatusOut", "mapping_type": "alias", "rationale": "Both are the radio status/health output port definition."},
    {"oem_element": "ShipLinkIcd::Radio", "supplier_element": "VendorRadioPack::RadioUnit", "mapping_type": "alias", "rationale": "Both are the radio part definition on the USV/vessel end of the link."},
    {"oem_element": "ShipLinkIcd::CommandShip", "supplier_element": "VendorRadioPack::ShipTerminal", "mapping_type": "alias", "rationale": "Both are the ship command terminal part definition receiving the data link."},
    {"oem_element": "ShipLinkIcd::Radio::uplinkMbps", "supplier_element": "VendorRadioPack::RadioUnit::linkRateMbps", "mapping_type": "alias", "rationale": "Both are the radio link rate attribute in Mbps."},
    {"oem_element": "ShipLinkIcd::usv.radio", "supplier_element": "VendorRadioPack::vessel.radioUnit", "mapping_type": "allocation", "rationale": "Both are the radio part usage on the USV/vessel instance."},
    {"oem_element": "ShipLinkIcd::usv.radio.toShore", "supplier_element": "VendorRadioPack::vessel.radioUnit.dataOut", "mapping_type": "allocation", "rationale": "Both are the radio's outbound data link port usage toward the ship terminal."},
    {"oem_element": "ShipLinkIcd::commandShip.fromUsv", "supplier_element": "VendorRadioPack::terminal.linkA", "mapping_type": "allocation", "rationale": "Both are the terminal's inbound link port usage receiving the USV connection."}
  ],
  "unmatched": [
    "ShipLinkIcd::Radio::health",
    "ShipLinkIcd::CommandShip::fromUav",
    "VendorRadioPack::ControlIn",
    "VendorRadioPack::RadioUnit::control",
    "VendorRadioPack::RadioUnit::txPowerW",
    "VendorRadioPack::ShipTerminal::linkB"
  ]
}
```