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
