package SharingLinkSupplier {
    doc /* SYNTHETIC FIXTURE. Not RTX or real supplier data. One uplink; replication takes place ashore. */
    private import ScalarValues::*;
    item def SharedFrame {
        attribute sequenceNumber : Integer;
        attribute timestampMs : Integer;
        attribute payloadBytes : Integer;
        attribute profile : String;
    }
    port def SharedDataPort {
        out item observation : SharedFrame;
    }
    part def UplinkModem {
        port fromProcessor : ~SharedDataPort;
        port toShore : SharedDataPort;
    }
    part def ShoreRelay {
        port fromPlatform : ~SharedDataPort;
        port toShoreSubscriber : SharedDataPort;
        port toPeerSubscriber : SharedDataPort;
    }
    part def Subscriber {
        port receive : ~SharedDataPort;
    }
}
