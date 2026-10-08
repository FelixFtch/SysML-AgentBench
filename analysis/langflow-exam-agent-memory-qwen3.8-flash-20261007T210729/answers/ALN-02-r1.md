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
    alias fromUav for VendorRadioPack::ShipTerminal::linkB;

    allocation allocUsv allocate ShipLinkIcd::usv to VendorRadioPack::vessel;
    allocation allocRadio allocate ShipLinkIcd::usv.radio to VendorRadioPack::vessel.radioUnit;
    allocation allocCommandShip allocate ShipLinkIcd::commandShip to VendorRadioPack::terminal;
}
```

```json
{
  "mappings": [
    {
      "oem_element": "ShipLinkIcd::LinkPort",
      "supplier_element": "VendorRadioPack::DataLink",
      "mapping_type": "alias",
      "rationale": "Both port definitions type the user data link carried between the vehicle radio and the ship terminal; same role in the connection."
    },
    {
      "oem_element": "ShipLinkIcd::HealthPort",
      "supplier_element": "VendorRadioPack::StatusOut",
      "mapping_type": "alias",
      "rationale": "The ICD health/monitoring port corresponds to the vendor's status output port; both expose radio health outward only."
    },
    {
      "oem_element": "ShipLinkIcd::Radio",
      "supplier_element": "VendorRadioPack::RadioUnit",
      "mapping_type": "alias",
      "rationale": "Same component definition: the ship data link radio fitted on the vehicle."
    },
    {
      "oem_element": "ShipLinkIcd::CommandShip",
      "supplier_element": "VendorRadioPack::ShipTerminal",
      "mapping_type": "alias",
      "rationale": "Same component definition: the shore/ship-side terminal that terminates the link paths."
    },
    {
      "oem_element": "ShipLinkIcd::Radio::toShore",
      "supplier_element": "VendorRadioPack::RadioUnit::dataOut",
      "mapping_type": "alias",
      "rationale": "The radio's link port toward the ship is the vendor's dataOut link port; both are typed by the data-link port definition and both ends of the ICD connection."
    },
    {
      "oem_element": "ShipLinkIcd::Radio::health",
      "supplier_element": "VendorRadioPack::RadioUnit::status",
      "mapping_type": "alias",
      "rationale": "Radio health attribute port of the ICD equals the vendor status port."
    },
    {
      "oem_element": "ShipLinkIcd::Radio::uplinkMbps",
      "supplier_element": "VendorRadioPack::RadioUnit::linkRateMbps",
      "mapping_type": "alias",
      "rationale": "Both are Real attributes in Mbps describing the radio link rate; the ICD names the uplink direction, the vendor the negotiated link rate."
    },
    {
      "oem_element": "ShipLinkIcd::CommandShip::fromUsv",
      "supplier_element": "VendorRadioPack::ShipTerminal::linkA",
      "mapping_type": "alias",
      "rationale": "Terminal link instance that carries the USV path: in both models it is the end connected to the vehicle radio data port."
    },
    {
      "oem_element": "ShipLinkIcd::CommandShip::fromUav",
      "supplier_element": "VendorRadioPack::ShipTerminal::linkB",
      "mapping_type": "alias",
      "rationale": "The second DataLink port on the terminal corresponds to the ICD's second inbound link port from the other vehicle."
    },
    {
      "oem_element": "ShipLinkIcd::usv",
      "supplier_element": "VendorRadioPack::vessel",
      "mapping_type": "allocation",
      "rationale": "The ICD vehicle usage is realised by the vendor's vessel usage, the part that carries the radio unit."
    },
    {
      "oem_element": "ShipLinkIcd::usv.radio",
      "supplier_element": "VendorRadioPack::vessel.radioUnit",
      "mapping_type": "allocation",
      "rationale": "The radio usage inside the vehicle is satisfied by the vendor radioUnit usage, of the aliased RadioUnit definition."
    },
    {
      "oem_element": "ShipLinkIcd::commandShip",
      "supplier_element": "VendorRadioPack::terminal",
      "mapping_type": "allocation",
      "rationale": "The ICD ship usage is realised by the vendor terminal usage, the far end of the link connection."
    }
  ],
  "unmatched": [
    "VendorRadioPack::ControlIn",
    "VendorRadioPack::RadioUnit::control",
    "VendorRadioPack::RadioUnit::txPowerW",
    "ShipLinkIcd::usv.radio.toShore -> ShipLinkIcd::commandShip.fromUsv (connection statement, no vendor-side counterpart declared here)"
  ]
}
```