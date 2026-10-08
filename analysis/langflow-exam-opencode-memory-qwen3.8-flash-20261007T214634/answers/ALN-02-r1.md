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

    allocation usvToVessel allocate ShipLinkIcd::usv to VendorRadioPack::vessel;
    allocation radioToRadioUnit allocate ShipLinkIcd::usv.radio to VendorRadioPack::vessel.radioUnit;
    allocation commandShipToTerminal allocate ShipLinkIcd::commandShip to VendorRadioPack::terminal;
}
```

```json
{
  "mappings": [
    {"oem_element": "ShipLinkIcd::LinkPort", "supplier_element": "VendorRadioPack::DataLink", "mapping_type": "alias", "rationale": "Both are the port type for the ship data link carried by the radio; the ICD calls it LinkPort, the vendor DataLink."},
    {"oem_element": "ShipLinkIcd::HealthPort", "supplier_element": "VendorRadioPack::StatusOut", "mapping_type": "alias", "rationale": "Both are the port type by which the radio exposes its health/status to the ship."},
    {"oem_element": "ShipLinkIcd::Radio", "supplier_element": "VendorRadioPack::RadioUnit", "mapping_type": "alias", "rationale": "The radio part definition in the ICD is the vendor's RadioUnit: same element of the link, different naming."},
    {"oem_element": "ShipLinkIcd::Radio::toShore", "supplier_element": "VendorRadioPack::RadioUnit::dataOut", "mapping_type": "alias", "rationale": "The radio's outbound link port; in both models it is the link-end that connects to the receiving terminal side (toShore -> fromUsv, dataOut -> linkA)."},
    {"oem_element": "ShipLinkIcd::Radio::health", "supplier_element": "VendorRadioPack::RadioUnit::status", "mapping_type": "alias", "rationale": "The radio's health/status port, typed by the aliased LinkPort-side HealthPort/StatusOut pair."},
    {"oem_element": "ShipLinkIcd::Radio::uplinkMbps", "supplier_element": "VendorRadioPack::RadioUnit::linkRateMbps", "mapping_type": "alias", "rationale": "Same quantity: the link data rate in Mbps of the radio. The ICD names it for the uplink direction, the vendor for the link rate."},
    {"oem_element": "ShipLinkIcd::CommandShip", "supplier_element": "VendorRadioPack::ShipTerminal", "mapping_type": "alias", "rationale": "Definition of the receiving end of the ship data link: the ICD models it as the command ship, the vendor pack as its ship terminal with two incoming link ports."},
    {"oem_element": "ShipLinkIcd::CommandShip::fromUsv", "supplier_element": "VendorRadioPack::ShipTerminal::linkA", "mapping_type": "alias", "rationale": "Identified by the mirrored connect statements: fromUsv is the far end of usv.radio.toShore, linkA is the far end of vessel.radioUnit.dataOut."},
    {"oem_element": "ShipLinkIcd::CommandShip::fromUav", "supplier_element": "VendorRadioPack::ShipTerminal::linkB", "mapping_type": "alias", "rationale": "Second incoming LinkPort/DataLink at the receiving end; the 2-for-2 port structure of the link endpoint matches."},
    {"oem_element": "ShipLinkIcd::usv", "supplier_element": "VendorRadioPack::vessel", "mapping_type": "allocation", "rationale": "Part usage of the platform carrying the radio: the ICD's usv usage corresponds to the vendor's vessel usage."},
    {"oem_element": "ShipLinkIcd::usv.radio", "supplier_element": "VendorRadioPack::vessel.radioUnit", "mapping_type": "allocation", "rationale": "The radio usage installed in the platform usage; the nested connect paths of both models correspond element-for-element."},
    {"oem_element": "ShipLinkIcd::commandShip", "supplier_element": "VendorRadioPack::terminal", "mapping_type": "allocation", "rationale": "Usage of the link receiving end: the ICD's commandShip usage is realized by the vendor's terminal usage of ShipTerminal."}
  ],
  "unmatched": [
    "VendorRadioPack::ControlIn",
    "VendorRadioPack::RadioUnit::control",
    "VendorRadioPack::RadioUnit::txPowerW"
  ]
}
```