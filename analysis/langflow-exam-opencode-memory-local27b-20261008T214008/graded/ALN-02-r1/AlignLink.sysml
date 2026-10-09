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
