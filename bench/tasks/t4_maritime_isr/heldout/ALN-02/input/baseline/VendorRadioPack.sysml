package VendorRadioPack {
    private import ScalarValues::*;
    port def DataLink;
    port def StatusOut;
    port def ControlIn;
    part def RadioUnit {
        port dataOut : DataLink;
        port status : StatusOut;
        port control : ControlIn;
        attribute linkRateMbps : Real;
        attribute txPowerW : Real;
    }
    part def ShipTerminal {
        port linkA : DataLink;
        port linkB : DataLink;
    }
    part vessel {
        part radioUnit : RadioUnit;
    }
    part terminal : ShipTerminal;
    connect vessel.radioUnit.dataOut to terminal.linkA;
}
