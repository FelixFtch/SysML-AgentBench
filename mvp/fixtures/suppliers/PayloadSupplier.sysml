package PayloadSupplier {
    doc /* SYNTHETIC FIXTURE. Not RTX or real supplier data. ICD revision PAYLOAD-ICD-R1. */
    private import ScalarValues::*;
    item def ObservationFrame {
        attribute sequenceNumber : Integer;
        attribute timestampMs : Integer;
        attribute payloadBytes : Integer;
    }
    port def ObservationPort {
        out item observation : ObservationFrame;
    }
    part def ObservationPayload {
        port observationOut : ObservationPort;
        attribute sourceId : String;
    }
}
