```sysml
package AlignLink {
    private import ShipLinkIcd::*;
    private import VendorRadioPack::*;

    alias LinkPort for VendorRadioPack::DataLink;
    alias HealthPort for VendorRadioPack::StatusOut;
    alias Radio for VendorRadioPack::RadioUnit;
    alias CommandShip for VendorRadioPack::ShipTerminal;

    alias toShore for VendorRadioPack::RadioUnit::dataOut;
    alias health for VendorRadioPack::RadioUnit::status;
    alias uplinkMbps for VendorRadioPack::RadioUnit::linkRateMbps;
    alias fromUsv for VendorRadioPack::ShipTerminal::linkA;

    allocation usv_alloc allocate ShipLinkIcd::usv to VendorRadioPack::vessel;
    allocation radio_alloc allocate ShipLinkIcd::usv.radio to VendorRadioPack::vessel.radioUnit;
    allocation commandShip_alloc allocate ShipLinkIcd::commandShip to VendorRadioPack::terminal;
}
```

```json
{
  "mappings": [
    {"oem_element": "ShipLinkIcd::LinkPort", "supplier_element": "VendorRadioPack::DataLink", "mapping_type": "alias", "rationale": "Both port definitions type the payload ship data link carried over the radio path; same role in the connect statements."},
    {"oem_element": "ShipLinkIcd::HealthPort", "supplier_element": "VendorRadioPack::StatusOut", "rationale": "Both port definitions carry radio health/status information out of the radio, one-directional monitoring.", "mapping_type": "alias"},
    {"oem_element": "ShipLinkIcd::Radio", "supplier_element": "VendorRadioPack::RadioUnit", "mapping_type": "alias", "rationale": "Same function: the shipborne radio that owns the link port, the health/status port and a Mbps link-rate attribute."},
    {"oem_element": "ShipLinkIcd::CommandShip", "supplier_element": "VendorRadioPack::ShipTerminal", "mapping_type": "alias", "rationale": "Ship-side endpoint that terminates the incoming data links from the vehicle radio."},
    {"oem_element": "ShipLinkIcd::Radio::toShore", "supplier_element": "VendorRadioPack::RadioUnit::dataOut", "mapping_type": "alias", "rationale": "Outbound DataLink-typed port of the radio; each is the end used in its package's connect to the ship-side port."},
    {"oem_element": "ShipLinkIcd::Radio::health", "supplier_element": "VendorRadioPack::RadioUnit::status", "mapping_type": "alias", "rationale": "Health/status port exposed by the radio, typed by the matched health/status port definition."},
    {"oem_element": "ShipLinkIcd::Radio::uplinkMbps", "supplier_element": "VendorRadioPack::RadioUnit::linkRateMbps", "mapping_type": "alias", "rationale": "Same Real-valued link-rate quantity in megabits per second; no numeric limit is asserted by either model."},
    {"oem_element": "ShipLinkIcd::CommandShip::fromUsv", "supplier_element": "VendorRadioPack::ShipTerminal::linkA", "mapping_type": "alias", "rationale": "Inbound link port from the USV radio; linkA is the terminal port connected to the vehicle radio dataOut in the vendor model."},
    {"oem_element": "ShipLinkIcd::usv", "supplier_element": "VendorRadioPack::vessel", "mapping_type": "allocation", "rationale": "The specification's vehicle usage hosting the radio corresponds to the vendor's vessel usage hosting the RadioUnit."},
    {"oem_element": "ShipLinkIcd::usv::radio", "supplier_element": "VendorRadioPack::vessel::radioUnit", "mapping_type": "allocation", "rationale": "The radio part usage on the vehicle is supplied by the vendor RadioUnit usage on the vessel."},
    {"oem_element": "ShipLinkIcd::commandShip", "supplier_element": "VendorRadioPack::terminal", "mapping_type": "allocation", "rationale": "The ship-side usage instantiated from CommandShip corresponds to the vendor terminal usage instantiated from ShipTerminal."}
  ],
  "unmatched": [
    "ShipLinkIcd::CommandShip::fromUav",
    "VendorRadioPack::ControlIn",
    "VendorRadioPack::RadioUnit::control",
    "VendorRadioPack::ShipTerminal::linkB",
    "VendorRadioPack::RadioUnit::txPowerW"
  ]
}
```