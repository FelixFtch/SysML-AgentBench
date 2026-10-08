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

    allocation usv_alloc allocate ShipLinkIcd::usv to VendorRadioPack::vessel;
    allocation radio_alloc allocate ShipLinkIcd::usv.radio to VendorRadioPack::vessel.radioUnit;
    allocation commandShip_alloc allocate ShipLinkIcd::commandShip to VendorRadioPack::terminal;
}
