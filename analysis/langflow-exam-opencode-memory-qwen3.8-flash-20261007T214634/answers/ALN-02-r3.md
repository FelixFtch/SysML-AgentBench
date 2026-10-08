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
    allocation usvToVessel allocate ShipLinkIcd::usv to VendorRadioPack::vessel;
    allocation radioToUnit allocate ShipLinkIcd::usv.radio to VendorRadioPack::vessel.radioUnit;
    allocation commandShipToTerminal allocate ShipLinkIcd::commandShip to VendorRadioPack::terminal;
}
```

```json
{
  "mappings": [
    {
      "oem_element": "ShipLinkIcd::LinkPort",
      "supplier_element": "VendorRadioPack::DataLink",
      "mapping_type": "alias",
      "rationale": "Both are definitions of a data-link port."
    },
    {
      "oem_element": "ShipLinkIcd::HealthPort",
      "supplier_element": "VendorRadioPack::StatusOut",
      "mapping_type": "alias",
      "rationale": "Both represent a health or status output port."
    },
    {
      "oem_element": "ShipLinkIcd::Radio",
      "supplier_element": "VendorRadioPack::RadioUnit",
      "mapping_type": "alias",
      "rationale": "Both define the radio part in the data-link architecture."
    },
    {
      "oem_element": "ShipLinkIcd::CommandShip",
      "supplier_element": "VendorRadioPack::ShipTerminal",
      "mapping_type": "alias",
      "rationale": "Both define the receiving ship-side link endpoint with two incoming link ports."
    },
    {
      "oem_element": "ShipLinkIcd::Radio::toShore",
      "supplier_element": "VendorRadioPack::RadioUnit::dataOut",
      "mapping_type": "alias",
      "rationale": "Both are the outgoing radio link port toward the ship endpoint."
    },
    {
      "oem_element": "ShipLinkIcd::Radio::health",
      "supplier_element": "VendorRadioPack::RadioUnit::status",
      "mapping_type": "alias",
      "rationale": "Both are the radio health or status output feature."
    },
    {
      "oem_element": "ShipLinkIcd::Radio::uplinkMbps",
      "supplier_element": "VendorRadioPack::RadioUnit::linkRateMbps",
      "mapping_type": "alias",
      "rationale": "Both are megabits-per-second link rate attributes for the radio."
    },
    {
      "oem_element": "ShipLinkIcd::CommandShip::fromUsv",
      "supplier_element": "VendorRadioPack::ShipTerminal::linkA",
      "mapping_type": "alias",
      "rationale": "Both are ship-side incoming data-link ports connected to the radio data output."
    },
    {
      "oem_element": "ShipLinkIcd::CommandShip::fromUav",
      "supplier_element": "VendorRadioPack::ShipTerminal::linkB",
      "mapping_type": "alias",
      "rationale": "Both are the second ship-side incoming data-link ports."
    },
    {
      "oem_element": "ShipLinkIcd::usv",
      "supplier_element": "VendorRadioPack::vessel",
      "mapping_type": "allocation",
      "rationale": "The specification USV usage corresponds to the vendor vessel usage."
    },
    {
      "oem_element": "ShipLinkIcd::usv.radio",
      "supplier_element": "VendorRadioPack::vessel.radioUnit",
      "mapping_type": "allocation",
      "rationale": "The radio part usage on the USV corresponds to the radioUnit part usage on the vessel."
    },
    {
      "oem_element": "ShipLinkIcd::commandShip",
      "supplier_element": "VendorRadioPack::terminal",
      "mapping_type": "allocation",
      "rationale": "The command ship usage corresponds to the vendor ship terminal usage."
    }
  ],
  "unmatched": [
    "VendorRadioPack::ControlIn",
    "VendorRadioPack::RadioUnit::control",
    "VendorRadioPack::RadioUnit::txPowerW"
  ]
}
```