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

    allocation usvAllocateVessel allocate ShipLinkIcd::usv to VendorRadioPack::vessel;
    allocation usvRadioAllocateVesselRadioUnit allocate ShipLinkIcd::usv.radio to VendorRadioPack::vessel.radioUnit;
    allocation commandShipAllocateTerminal allocate ShipLinkIcd::commandShip to VendorRadioPack::terminal;
}
```

```json
{
  "mappings": [
    {
      "oem_element": "ShipLinkIcd::LinkPort",
      "supplier_element": "VendorRadioPack::DataLink",
      "mapping_type": "alias",
      "rationale": "Both port definitions type the ship data-link bearer traffic; the ICD LinkPort is carried by the vendor DataLink port."
    },
    {
      "oem_element": "ShipLinkIcd::HealthPort",
      "supplier_element": "VendorRadioPack::StatusOut",
      "mapping_type": "alias",
      "rationale": "The ICD health reporting port corresponds to the vendor status output, which exposes radio health/availability."
    },
    {
      "oem_element": "ShipLinkIcd::Radio",
      "supplier_element": "VendorRadioPack::RadioUnit",
      "mapping_type": "alias",
      "rationale": "Same role: the onboard radio part definition, with matching link and status ports and a rate attribute."
    },
    {
      "oem_element": "ShipLinkIcd::Radio::toShore",
      "supplier_element": "VendorRadioPack::RadioUnit::dataOut",
      "mapping_type": "alias",
      "rationale": "Confirmed by the baselines' connections: toShore pairs with dataOut on the link to the ship terminal."
    },
    {
      "oem_element": "ShipLinkIcd::Radio::health",
      "supplier_element": "VendorRadioPack::RadioUnit::status",
      "mapping_type": "alias",
      "rationale": "Radio health reporting usage maps to the vendor status port usage of the same type pairing."
    },
    {
      "oem_element": "ShipLinkIcd::Radio::uplinkMbps",
      "supplier_element": "VendorRadioPack::RadioUnit::linkRateMbps",
      "mapping_type": "alias",
      "rationale": "Both are Real attributes measuring the radio link data rate in Mbps on the same part definition."
    },
    {
      "oem_element": "ShipLinkIcd::CommandShip",
      "supplier_element": "VendorRadioPack::ShipTerminal",
      "mapping_type": "alias",
      "rationale": "Ship-side link terminus: the ICD command ship part definition corresponds to the vendor ship terminal."
    },
    {
      "oem_element": "ShipLinkIcd::CommandShip::fromUsv",
      "supplier_element": "VendorRadioPack::ShipTerminal::linkA",
      "mapping_type": "alias",
      "rationale": "Confirmed by the connect statements: the USV-facing LinkPort is the vendor linkA DataLink port."
    },
    {
      "oem_element": "ShipLinkIcd::CommandShip::fromUav",
      "supplier_element": "VendorRadioPack::ShipTerminal::linkB",
      "mapping_type": "alias",
      "rationale": "Remaining ship-side DataLink port; after linkA is taken by fromUsv, linkB is the terminal's second inbound link usage."
    },
    {
      "oem_element": "ShipLinkIcd::usv",
      "supplier_element": "VendorRadioPack::vessel",
      "mapping_type": "allocation",
      "rationale": "Usage-level alignment: the ICD USV part usage is realised by the vendor vessel part usage."
    },
    {
      "oem_element": "ShipLinkIcd::usv.radio",
      "supplier_element": "VendorRadioPack::vessel.radioUnit",
      "mapping_type": "allocation",
      "rationale": "Nested part usage path: the USV's radio usage is realised by the vessel's radioUnit usage."
    },
    {
      "oem_element": "ShipLinkIcd::commandShip",
      "supplier_element": "VendorRadioPack::terminal",
      "mapping_type": "allocation",
      "rationale": "Usage-level alignment: the ICD command ship part usage is realised by the vendor ship terminal usage."
    }
  ],
  "unmatched": [
    "VendorRadioPack::ControlIn",
    "VendorRadioPack::RadioUnit::control",
    "VendorRadioPack::RadioUnit::txPowerW"
  ]
}
```