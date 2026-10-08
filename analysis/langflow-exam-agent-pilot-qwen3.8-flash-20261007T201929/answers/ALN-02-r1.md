```sysml
package AlignLink {
    private import ShipLinkIcd::*;
    private import VendorRadioPack::*;

    // Definitions: specification short names aliased to supplier qualified names
    alias LinkPort for VendorRadioPack::DataLink;
    alias HealthPort for VendorRadioPack::StatusOut;
    alias Radio for VendorRadioPack::RadioUnit;
    alias CommandShip for VendorRadioPack::ShipTerminal;

    // Features of the matched definitions
    alias toShore for VendorRadioPack::RadioUnit::dataOut;
    alias health for VendorRadioPack::RadioUnit::status;
    alias uplinkMbps for VendorRadioPack::RadioUnit::linkRateMbps;
    alias fromUsv for VendorRadioPack::ShipTerminal::linkA;
    alias fromUav for VendorRadioPack::ShipTerminal::linkB;

    // Part usages mapped by allocation
    allocation usvToVessel allocate ShipLinkIcd::usv to VendorRadioPack::vessel;
    allocation radioToRadioUnit allocate ShipLinkIcd::usv.radio to VendorRadioPack::vessel.radioUnit;
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
      "rationale": "Both port definitions type the payload data link between a radio and a ship-side endpoint; same role, so the ICD name is aliased to the supplier port definition."
    },
    {
      "oem_element": "ShipLinkIcd::HealthPort",
      "supplier_element": "VendorRadioPack::StatusOut",
      "mapping_type": "alias",
      "rationale": "The ICD health/monitoring port corresponds to the vendor's outbound status port; both carry radio health/status information out of the radio."
    },
    {
      "oem_element": "ShipLinkIcd::Radio",
      "supplier_element": "VendorRadioPack::RadioUnit",
      "mapping_type": "alias",
      "rationale": "Same concept at the same level of decomposition: the ship data-link radio part definition, with matching link port, health/status port and rate attribute."
    },
    {
      "oem_element": "ShipLinkIcd::CommandShip",
      "supplier_element": "VendorRadioPack::ShipTerminal",
      "mapping_type": "alias",
      "rationale": "The ICD command-ship endpoint that receives links from the USV and UAV corresponds to the vendor ship terminal offering two data-link connections."
    },
    {
      "oem_element": "ShipLinkIcd::Radio::toShore",
      "supplier_element": "VendorRadioPack::RadioUnit::dataOut",
      "mapping_type": "alias",
      "rationale": "The radio's shore/command-facing data port is the vendor radio unit's outward data-link port; same direction and same port type after the LinkPort/DataLink alias."
    },
    {
      "oem_element": "ShipLinkIcd::Radio::health",
      "supplier_element": "VendorRadioPack::RadioUnit::status",
      "mapping_type": "alias",
      "rationale": "The radio's health exposure port is the vendor status output port of the same radio unit definition."
    },
    {
      "oem_element": "ShipLinkIcd::Radio::uplinkMbps",
      "supplier_element": "VendorRadioPack::RadioUnit::linkRateMbps",
      "mapping_type": "alias",
      "rationale": "Both are Real data-rate attributes of the radio expressed in Mbps; the vendor's link rate is the supplier's figure of merit for the ICD uplink rate."
    },
    {
      "oem_element": "ShipLinkIcd::CommandShip::fromUsv",
      "supplier_element": "VendorRadioPack::ShipTerminal::linkA",
      "mapping_type": "alias",
      "rationale": "The ship-side link terminated from the USV corresponds to the terminal's first data-link connection, linkA, which the vendor packs to the radio unit's dataOut."
    },
    {
      "oem_element": "ShipLinkIcd::CommandShip::fromUav",
      "supplier_element": "VendorRadioPack::ShipTerminal::linkB",
      "mapping_type": "alias",
      "rationale": "The ship-side link terminated from the UAV corresponds to the terminal's second data-link connection, linkB."
    },
    {
      "oem_element": "ShipLinkIcd::usv",
      "supplier_element": "VendorRadioPack::vessel",
      "mapping_type": "allocation",
      "rationale": "The ICD usage of the vehicle that carries the radio is satisfied by the vendor usage of the vessel that carries the radio unit."
    },
    {
      "oem_element": "ShipLinkIcd::usv.radio",
      "supplier_element": "VendorRadioPack::vessel.radioUnit",
      "mapping_type": "allocation",
      "rationale": "The radio part usage nested in the USV is satisfied by the vendor's radio unit usage nested in the vessel; the containing allocation and the Radio/RadioUnit alias agree."
    },
    {
      "oem_element": "ShipLinkIcd::commandShip",
      "supplier_element": "VendorRadioPack::terminal",
      "mapping_type": "allocation",
      "rationale": "The ICD command-ship endpoint usage is satisfied by the vendor ship terminal usage, matching the connected pair toShore/linkA on both sides."
    }
  ],
  "unmatched": [
    "VendorRadioPack::ControlIn",
    "VendorRadioPack::RadioUnit::control",
    "VendorRadioPack::RadioUnit::txPowerW"
  ]
}
```