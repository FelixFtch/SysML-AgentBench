package DesignA {
    private import ScalarValues::*;

    requirement def R1 {
        doc /* R1: The vessel total power draw shall not exceed the vessel power limit of 60 W. */
    }
    requirement def R2 {
        doc /* R2: The visible camera shall draw 28 W. */
    }
    requirement def R3 {
        doc /* R3: The edge computer shall draw 14 W. */
    }
    requirement def R4 {
        doc /* R4: The infrared camera shall draw 12 W. */
    }
    requirement def R5 {
        doc /* R5: Imagery shall be recorded locally at a data rate of 12 Mbps. */
    }
    requirement def R6 {
        doc /* R6: Recorded imagery shall be retained for 8 hours. */
    }
    requirement def R7 {
        doc /* R7: The system shall provide 256 GB of storage for local recording. */
    }
    requirement def R8 {
        doc /* R8: Imagery shall be uploaded to shore at 12 Mbps. */
    }
    requirement def R9 {
        doc /* R9: The uplink capacity to shore shall be 20 Mbps. */
    }

    port def DataPort;
    port def PowerPort;

    part def VisibleCamera {
        port dataOut : DataPort;
        port powerIn : PowerPort;
    }
    part def InfraredCamera {
        port dataOut : DataPort;
        port powerIn : PowerPort;
    }
    part def EdgeComputer {
        port dataIn1 : DataPort;
        port dataIn2 : DataPort;
        port dataOut : DataPort;
        port powerIn : PowerPort;
    }
    part def Uplink {
        port dataIn : DataPort;
        port powerIn : PowerPort;
    }

    part vessel {
        attribute powerLimitW : Real = 60;
        attribute dataRateMbps : Real = 12;
        attribute retentionHours : Real = 8;
        attribute storageGB : Real = 256;
        attribute uploadMbps : Real = 12;
        attribute uplinkMbps : Real = 20;

        part visibleCamera : VisibleCamera {
            attribute drawW : Real = 28;
        }
        part infraredCamera : InfraredCamera {
            attribute drawW : Real = 12;
        }
        part edgeComputer : EdgeComputer {
            attribute drawW : Real = 14;
        }
        part uplink : Uplink;

        connect visibleCamera.dataOut to edgeComputer.dataIn1;
        connect infraredCamera.dataOut to edgeComputer.dataIn2;
        connect edgeComputer.dataOut to uplink.dataIn;
    }
}
