package AlignLink {
    private import ShipLinkIcd::*;
    private import VendorRadioPack::*;
    alias Radio for VendorRadioPack::RadioUnit;
    alias LinkPort for VendorRadioPack::DataLink;
    alias HealthPort for VendorRadioPack::StatusOut;
    alias CommandShip for VendorRadioPack::ShipTerminal;
    alias uplinkMbps for VendorRadioPack::RadioUnit::linkRateMbps;
    alias toShore for VendorRadioPack::RadioUnit::dataOut;
    alias health for VendorRadioPack::RadioUnit::status;
    alias fromUsv for VendorRadioPack::ShipTerminal::linkA;
    allocation radio allocate ShipLinkIcd::usv.radio to VendorRadioPack::vessel.radioUnit;
    allocation link allocate ShipLinkIcd::commandShip.fromUsv to VendorRadioPack::terminal.linkA;
}
