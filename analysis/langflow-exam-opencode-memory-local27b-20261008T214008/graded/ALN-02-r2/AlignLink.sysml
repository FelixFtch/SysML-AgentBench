package AlignLink {
    private import ShipLinkIcd::*;
    private import VendorRadioPack::*;
    alias LinkPort for VendorRadioPack::DataLink;
    alias HealthPort for VendorRadioPack::StatusOut;
    alias Radio for VendorRadioPack::RadioUnit;
    alias CommandShip for VendorRadioPack::ShipTerminal;
    alias uplinkMbps for VendorRadioPack::RadioUnit::linkRateMbps;
    allocation usvRadioToVesselRadioUnit allocate ShipLinkIcd::usv.radio to VendorRadioPack::vessel.radioUnit;
    allocation toShoreDataOutToLinkA allocate ShipLinkIcd::usv.radio.toShore to VendorRadioPack::vessel.radioUnit.dataOut;
    allocation fromUsvToLinkA allocate ShipLinkIcd::commandShip.fromUsv to VendorRadioPack::terminal.linkA;
}
