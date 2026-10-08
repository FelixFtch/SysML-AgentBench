```sysml
package AlignLink {
    private import ShipLinkIcd::*;
    private import VendorRadioPack::*;

    // Definitions and typed features: specification short name -> supplier qualified name
    alias LinkPort for VendorRadioPack::DataLink;
    alias HealthPort for VendorRadioPack::StatusOut;
    alias Radio for VendorRadioPack::RadioUnit;
    alias toShore for VendorRadioPack::RadioUnit::dataOut;
    alias health for VendorRadioPack::RadioUnit::status;
    alias uplinkMbps for VendorRadioPack::RadioUnit::linkRateMbps;
    alias CommandShip for VendorRadioPack::ShipTerminal;
    alias fromUsv for VendorRadioPack::ShipTerminal::linkA;
    alias fromUav for VendorRadioPack::ShipTerminal::linkB;

    // Part usage mappings
    allocation usvToVessel allocate ShipLinkIcd::usv to VendorRadioPack::vessel;
    allocation usvRadioToVesselRadioUnit allocate ShipLinkIcd::usv.radio to VendorRadioPack::vessel.radioUnit;
    allocation commandShipToTerminal allocate ShipLinkIcd::commandShip to VendorRadioPack::terminal;
}
```

```json
{
  "mappings": [
    {"oem_element": "ShipLinkIcd::LinkPort", "supplier_element": "VendorRadioPack::DataLink", "mapping_type": "alias", "rationale": "Both are the payload data link port type carried by the radio and the ship terminal."},
    {"oem_element": "ShipLinkIcd::HealthPort", "supplier_element": "VendorRadioPack::StatusOut", "mapping_type": "alias", "rationale": "Both expose radio health/status out of the radio; only direction of the status data differs in naming, function is the same."},
    {"oem_element": "ShipLinkIcd::Radio", "supplier_element": "VendorRadioPack::RadioUnit", "mapping_type": "alias", "rationale": "The OEM ship data link radio definition is realised by the vendor radio unit definition."},
    {"oem_element": "ShipLinkIcd::Radio::toShore", "supplier_element": "VendorRadioPack::RadioUnit::dataOut", "mapping_type": "alias", "rationale": "Outbound data-link port of the radio towards the ship/shore terminal; it is the port the vendor connects to the terminal link in its own model."},
    {"oem_element": "ShipLinkIcd::Radio::health", "supplier_element": "VendorRadioPack::RadioUnit::status", "mapping_type": "alias", "rationale": "Same health/status reporting port on the radio, typed by the corresponding status port definition."},
    {"oem_element": "ShipLinkIcd::Radio::uplinkMbps", "supplier_element": "VendorRadioPack::RadioUnit::linkRateMbps", "mapping_type": "alias", "rationale": "Same quantity: link rate expressed in Mbps, Real valued; the OEM names it uplink, the vendor names it generically."},
    {"oem_element": "ShipLinkIcd::CommandShip", "supplier_element": "VendorRadioPack::ShipTerminal", "mapping_type": "alias", "rationale": "The ship-side endpoint that terminates the link connections; OEM command ship corresponds to the vendor ship terminal."},
    {"oem_element": "ShipLinkIcd::CommandShip::fromUsv", "supplier_element": "VendorRadioPack::ShipTerminal::linkA", "mapping_type": "alias", "rationale": "Both are the terminal data link port joined to the USV radio data output (each model connects this port to the radio's outbound link)."},
    {"oem_element": "ShipLinkIcd::CommandShip::fromUav", "supplier_element": "VendorRadioPack::ShipTerminal::linkB", "mapping_type": "alias", "rationale": "Both are the second inbound DataLink/LinkPort on the ship side; the terminal provides exactly the two link ports the ship needs."},
    {"oem_element": "ShipLinkIcd::usv", "supplier_element": "VendorRadioPack::vessel", "mapping_type": "allocation", "rationale": "Part usage of the platform carrying the radio; allocated instance-to-instance, not type-to-type."},
    {"oem_element": "ShipLinkIcd::usv.radio", "supplier_element": "VendorRadioPack::vessel.radioUnit", "mapping_type": "allocation", "rationale": "The nested radio usage of the USV is filled by the vendor radio unit usage nested in the vessel."},
    {"oem_element": "ShipLinkIcd::commandShip", "supplier_element": "VendorRadioPack::terminal", "mapping_type": "allocation", "rationale": "The ship usage is allocated to the vendor ship terminal usage."}
  ],
  "unmatched": [
    "VendorRadioPack::ControlIn",
    "VendorRadioPack::RadioUnit::control",
    "VendorRadioPack::RadioUnit::txPowerW"
  ]
}
```