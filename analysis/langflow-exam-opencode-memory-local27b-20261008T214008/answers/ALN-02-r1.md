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
    allocation usvRadio allocate ShipLinkIcd::usv.radio to VendorRadioPack::vessel.radioUnit;
    allocation commandShip allocate ShipLinkIcd::commandShip to VendorRadioPack::terminal;
    allocation usv allocate ShipLinkIcd::usv to VendorRadioPack::vessel;
}
```

```json
{
  "mappings": [
    {
      "oem_element": "ShipLinkIcd::LinkPort",
      "supplier_element": "VendorRadioPack::DataLink",
      "mapping_type": "alias",
      "rationale": "Specification link port and vendor data link port both represent the ship-to-vessel data link interface type."
    },
    {
      "oem_element": "ShipLinkIcd::HealthPort",
      "supplier_element": "VendorRadioPack::StatusOut",
      "mapping_type": "alias",
      "rationale": "Specification health port and vendor status output port both expose radio health/status information."
    },
    {
      "oem_element": "ShipLinkIcd::Radio",
      "supplier_element": "VendorRadioPack::RadioUnit",
      "mapping_type": "alias",
      "rationale": "Specification radio part definition and vendor radio unit part definition represent the same radio hardware concept."
    },
    {
      "oem_element": "ShipLinkIcd::CommandShip",
      "supplier_element": "VendorRadioPack::ShipTerminal",
      "mapping_type": "alias",
      "rationale": "Specification command ship part definition and vendor ship terminal part definition represent the shore/ship terminal concept."
    },
    {
      "oem_element": "ShipLinkIcd::toShore",
      "supplier_element": "VendorRadioPack::RadioUnit::dataOut",
      "mapping_type": "alias",
      "rationale": "Specification to-shore port and vendor data output port both represent the radio's data link to the ship terminal."
    },
    {
      "oem_element": "ShipLinkIcd::health",
      "supplier_element": "VendorRadioPack::RadioUnit::status",
      "mapping_type": "alias",
      "rationale": "Specification health port and vendor status port both represent radio health/status on the radio unit."
    },
    {
      "oem_element": "ShipLinkIcd::uplinkMbps",
      "supplier_element": "VendorRadioPack::RadioUnit::linkRateMbps",
      "mapping_type": "alias",
      "rationale": "Specification uplink rate attribute and vendor link rate attribute both express radio link throughput in Mbps."
    },
    {
      "oem_element": "ShipLinkIcd::fromUsv",
      "supplier_element": "VendorRadioPack::ShipTerminal::linkA",
      "mapping_type": "alias",
      "rationale": "Specification from-USV port and vendor linkA both represent the terminal link receiving data from the USV radio."
    },
    {
      "oem_element": "ShipLinkIcd::usv.radio",
      "supplier_element": "VendorRadioPack::vessel.radioUnit",
      "mapping_type": "allocation",
      "rationale": "Specification USV radio part usage and vendor vessel radio unit part usage occupy the same radio role on the vessel."
    },
    {
      "oem_element": "ShipLinkIcd::commandShip",
      "supplier_element": "VendorRadioPack::terminal",
      "mapping_type": "allocation",
      "rationale": "Specification command ship terminal usage and vendor ship terminal usage occupy the same terminal role."
    },
    {
      "oem_element": "ShipLinkIcd::usv",
      "supplier_element": "VendorRadioPack::vessel",
      "mapping_type": "allocation",
      "rationale": "Specification USV context part and vendor vessel context part represent the same maritime host platform."
    }
  ],
  "unmatched": [
    "ShipLinkIcd::CommandShip::fromUav",
    "VendorRadioPack::ControlIn",
    "VendorRadioPack::RadioUnit::control",
    "VendorRadioPack::RadioUnit::txPowerW",
    "VendorRadioPack::ShipTerminal::linkB"
  ]
}
```