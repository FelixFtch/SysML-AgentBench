package AlignLink {
    private import ShipLinkIcd::*;
    private import VendorRadioPack::*;
    alias LinkPort for VendorRadioPack::DataLink;
    alias HealthPort for VendorRadioPack::StatusOut;
    alias Radio for VendorRadioPack::RadioUnit;
    alias CommandShip for VendorRadioPack::ShipTerminal;
    alias uplinkMbps for VendorRadioPack::RadioUnit::linkRateMbps;
    alias toShore for VendorRadioPack::RadioUnit::dataOut;
    alias health for VendorRadioPack::RadioUnit::status;
    allocation usvToVessel allocate ShipLinkIcd::usv to VendorRadioPack::vessel;
    allocation usvRadioToVesselRadioUnit allocate ShipLinkIcd::usv.radio to VendorRadioPack::vessel.radioUnit;
    allocation commandShipToTerminal allocate ShipLinkIcd::commandShip to VendorRadioPack::terminal;
}
