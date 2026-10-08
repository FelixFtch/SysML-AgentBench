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
    allocation usv allocate ShipLinkIcd::usv to VendorRadioPack::vessel;
    allocation usvRadio allocate ShipLinkIcd::usv.radio to VendorRadioPack::vessel.radioUnit;
    allocation commandShip allocate ShipLinkIcd::commandShip to VendorRadioPack::terminal;
}
```

```json
{
  "mappings": [
    {
      "oem_element": "ShipLinkIcd::LinkPort",
      "supplier_element": "VendorRadioPack::DataLink",
      "mapping_type": "alias",
      "rationale": "Specification link interface definition corresponds to the vendor's data link port definition."
    },
    {
      "oem_element": "ShipLinkIcd::HealthPort",
      "supplier_element": "VendorRadioPack::StatusOut",
      "mapping_type": "alias",
      "rationale": "Specification health reporting port definition corresponds to the vendor's status output port definition."
    },
    {
      "oem_element": "ShipLinkIcd::Radio",
      "supplier_element": "VendorRadioPack::RadioUnit",
      "mapping_type": "alias",
      "rationale": "Specification radio part definition corresponds to the vendor's radio unit part definition."
    },
    {
      "oem_element": "ShipLinkIcd::CommandShip",
      "supplier_element": "VendorRadioPack::ShipTerminal",
      "mapping_type": "alias",
      "rationale": "Specification command ship part definition corresponds to the vendor's ship terminal part definition."
    },
    {
      "oem_element": "ShipLinkIcd::Radio::toShore",
      "supplier_element": "VendorRadioPack::RadioUnit::dataOut",
      "mapping_type": "alias",
      "rationale": "Shore uplink port on the radio corresponds to the vendor's data out port."
    },
    {
      "oem_element": "ShipLinkIcd::Radio::health",
      "supplier_element": "VendorRadioPack::RadioUnit::status",
      "mapping_type": "alias",
      "rationale": "Radio health port corresponds to the vendor's status port."
    },
    {
      "oem_element": "ShipLinkIcd::Radio::uplinkMbps",
      "supplier_element": "VendorRadioPack::RadioUnit::linkRateMbps",
      "mapping_type": "alias",
      "rationale": "Specification uplink rate attribute in Mbps corresponds to the vendor's link rate attribute in Mbps."
    },
    {
      "oem_element": "ShipLinkIcd::CommandShip::fromUsv",
      "supplier_element": "VendorRadioPack::ShipTerminal::linkA",
      "mapping_type": "alias",
      "rationale": "Command ship intake port from the USV corresponds to the vendor's first data link on the terminal."
    },
    {
      "oem_element": "ShipLinkIcd::CommandShip::fromUav",
      "supplier_element": "VendorRadioPack::ShipTerminal::linkB",
      "mapping_type": "alias",
      "rationale": "Command ship intake port from the UAV corresponds to the vendor's second data link on the terminal."
    },
    {
      "oem_element": "ShipLinkIcd::usv",
      "supplier_element": "VendorRadioPack::vessel",
      "mapping_type": "allocation",
      "rationale": "Specification USV part usage corresponds to the vendor's vessel part usage."
    },
    {
      "oem_element": "ShipLinkIcd::usv.radio",
      "supplier_element": "VendorRadioPack::vessel.radioUnit",
      "mapping_type": "allocation",
      "rationale": "Radio part usage on the USV corresponds to the radio unit part usage on the vessel."
    },
    {
      "oem_element": "ShipLinkIcd::commandShip",
      "supplier_element": "VendorRadioPack::terminal",
      "mapping_type": "allocation",
      "rationale": "Specification command ship part usage corresponds to the vendor's ship terminal part usage."
    }
  ],
  "unmatched": [
    "ShipLinkIcd::Radio::health",
    "VendorRadioPack::ControlIn",
    "VendorRadioPack::RadioUnit::control",
    "VendorRadioPack::RadioUnit::txPowerW"
  ]
}
```