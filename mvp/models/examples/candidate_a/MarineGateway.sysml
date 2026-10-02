package MarineGateway {
    doc /* SYNTHETIC ENGINEERING FIXTURE. Not RTX data or hardware measurements.
        Case: candidate_a. Source configuration: MARINE-01-A.
        A satisfy relationship represents design intent, not successful verification. */
    private import ScalarValues::*;
    private import ISQ::*;
    private import SI::*;
    private import PayloadSupplier::*;
    private import SharingLinkSupplier::*;

    action def AcquireObservations;
    action def ProcessObservations;
    action def RecordOriginalData;
    action def ShareObservations;
    action def GenerateP2Preview;

    part def AcquisitionNode {
        port fromAlpha : ~ObservationPort;
        port fromBeta : ~ObservationPort;
        port toProcessor : ObservationPort;
        perform action acquire : AcquireObservations;
    }
    part def ProcessingNode {
        port fromAcquisition : ~ObservationPort;
        port rawToRecorder : ObservationPort;
        port dataToModem : SharedDataPort;
        perform action process : ProcessObservations;
        perform action share : ShareObservations;
    }
    part def PreviewProcessor {
        port fromProcessor : ~SharedDataPort;
        port toModem : SharedDataPort;
        perform action preview : GenerateP2Preview;
    }
    part def Recorder {
        port rawInput : ~ObservationPort;
        attribute capacityGB : Real;
        perform action record : RecordOriginalData;
    }
    part def Gateway {
        attribute configurationId : String;
        attribute dataRateMbps : Real;
        attribute retentionHours : Real;
        attribute storageGB : Real;
        attribute usableFraction : Real;
        attribute linkMbps : Real;
        attribute networkFactor : Real;
        attribute uploadRateMbps : Real;
        attribute previewMbps : Real;
        attribute totalPowerW : Real;
        attribute powerLimitW : Real;
        attribute previewApproved : Boolean;
        attribute uploadPolicy : String;
        attribute dataRateUnit : String = "Mbit/s (decimal)";
        attribute capacityUnit : String = "GB (decimal)";
        attribute powerCondition : String = "synthetic steady observation; total node input including payloads and losses";
        attribute totalPower : PowerValue = totalPowerW * 1[W];
        attribute powerLimit : PowerValue = powerLimitW * 1[W];
        attribute retentionTime : TimeValue = retentionHours * 3600[s];

        part payloadAlpha : ObservationPayload {
            attribute :>> sourceId = "PAYLOAD-ALPHA";
        }
        part payloadBeta : ObservationPayload {
            attribute :>> sourceId = "PAYLOAD-BETA";
        }
        part acquisition : AcquisitionNode;
        part processor : ProcessingNode;
        part recorder : Recorder {
            attribute :>> capacityGB = Gateway::storageGB;
        }
        part modem : UplinkModem;
        part previewProcessor : PreviewProcessor;
        part shoreRelay : ShoreRelay {
            doc /* Outside the node power boundary. Replicates one received uplink to two subscribers. */
        }
        part shoreSubscriber : Subscriber;
        part peerSubscriber : Subscriber;
        connection payloadAConnection connect payloadAlpha.observationOut to acquisition.fromAlpha;
        connection payloadBConnection connect payloadBeta.observationOut to acquisition.fromBeta;
        connection acquisitionConnection connect acquisition.toProcessor to processor.fromAcquisition;
        connection recordingConnection connect processor.rawToRecorder to recorder.rawInput;
        connection processingConnection connect processor.dataToModem to previewProcessor.fromProcessor;
        connection previewConnection connect previewProcessor.toModem to modem.fromProcessor;
        connection uplinkConnection connect modem.toShore to shoreRelay.fromPlatform;
        connection shoreConnection connect shoreRelay.toShoreSubscriber to shoreSubscriber.receive;
        connection peerConnection connect shoreRelay.toPeerSubscriber to peerSubscriber.receive;
    }

    part gateway : Gateway {
        attribute :>> configurationId = "MARINE-01-A";
        attribute :>> dataRateMbps = 18;
        attribute :>> retentionHours = 8;
        attribute :>> storageGB = 128;
        attribute :>> usableFraction = 0.8;
        attribute :>> linkMbps = 8;
        attribute :>> networkFactor = 1.2;
        attribute :>> uploadRateMbps = 2;
        attribute :>> previewMbps = 2;
        attribute :>> totalPowerW = 54;
        attribute :>> powerLimitW = 60;
        attribute :>> previewApproved = true;
        attribute :>> uploadPolicy = "P2_APPROVED";
    }

    requirement def StorageRetentionRequirement {
        subject node : Gateway;
        doc /* R-STORE-001/002: retain all raw data for 8 hours in decimal GB.
            0.45 converts Mbit/s times hours to decimal GB. Network overhead is excluded. */
        require constraint {
            node.storageGB * node.usableFraction >= node.dataRateMbps * node.retentionHours * 0.45
        }
    }
    requirement def PowerBudgetRequirement {
        subject node : Gateway;
        doc /* R-POWER-001: declared node input must not exceed 60 W. Budget, not measurement. */
        require constraint { node.totalPower <= node.powerLimit }
    }
    requirement def FullUploadRequirement {
        subject node : Gateway;
        doc /* R-UPLOAD-001: preserve the original full real-time upload requirement unless explicitly replaced. */
        require constraint { node.uploadRateMbps == node.dataRateMbps }
        require constraint { node.uploadRateMbps * node.networkFactor <= node.linkMbps }
    }
    requirement def PreviewUploadRequirement {
        subject node : Gateway;
        doc /* R-UPLOAD-P2: proposed replacement requires explicit approval; P2 quality and latency are not verified here. */
        require constraint { node.previewApproved }
        require constraint { node.uploadRateMbps == node.previewMbps }
        require constraint { node.uploadRateMbps * node.networkFactor <= node.linkMbps }
    }
    requirement <'R-STORE-001'> storageRequirement : StorageRetentionRequirement;
    requirement <'R-POWER-001'> powerRequirement : PowerBudgetRequirement;
    requirement <'R-UPLOAD-P2'> uploadRequirement : PreviewUploadRequirement;

    part designContext {
        ref candidate :> gateway;
        satisfy storageRequirement by candidate;
        satisfy powerRequirement by candidate;
        satisfy uploadRequirement by candidate;
    }
    verification def StorageBudgetAnalysis {
        subject testNode : Gateway;
        objective { verify storageRequirement; }
        doc /* Analysis specification only. The separate budget run records the actual verdict and input revision. */
    }
    verification def PowerBudgetAnalysis {
        subject testNode : Gateway;
        objective { verify powerRequirement; }
    }
    verification def UplinkBudgetAnalysis {
        subject testNode : Gateway;
        objective { verify uploadRequirement; }
    }
}
