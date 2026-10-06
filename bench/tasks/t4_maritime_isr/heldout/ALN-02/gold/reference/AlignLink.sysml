package AlignLink {
    public import ShipLinkIcd::*;
    private import VendorRadioPack::*;
    alias Radio for VendorRadioPack::RadioUnit;
    alias LinkPort for VendorRadioPack::DataLink;
    alias HealthPort for VendorRadioPack::StatusOut;
    alias toShore for VendorRadioPack::RadioUnit::dataOut;
    alias health for VendorRadioPack::RadioUnit::status;
    alias uplinkMbps for VendorRadioPack::RadioUnit::linkRateMbps;
    alias CommandShip for VendorRadioPack::ShipTerminal;
    allocation radioToUnit allocate ShipLinkIcd::usv.radio to VendorRadioPack::vessel.radioUnit;
    allocation shipToTerminal allocate ShipLinkIcd::commandShip to VendorRadioPack::terminal;
}
