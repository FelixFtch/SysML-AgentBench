package NASA_CFE_Imported {
    private import ScalarValues::*;
    doc /* Public NASA cFE requirement text import. Not RTX requirements.
        No design satisfaction or executable verification is asserted.
        Semantic mapping and new-project applicability remain pending. */

    requirement def ImportedCFERequirement {
        attribute sourceRequirementId : String;
        attribute sourceCommit : String;
        attribute sourceArtifactHash : String;
        attribute sourceLocation : String;
        attribute interpretationStatus : String;
    }

    requirement cSB4301 : ImportedCFERequirement {
        doc /* SB: Create Pipe
            Upon receipt of a Request to create a Pipe, the cFE shall create a Pipe with the Request-specified Pipe Depth and the Request-specified name.
            
            Rationale: Run time creation of Pipes supports the cFE goals of easy Application integration and system reconfiguration.
        */
        attribute :>> sourceRequirementId = "cSB4301";
        attribute :>> sourceCommit = "7d283938c9af5bd6e439f3fc307e61b0c7799640";
        attribute :>> sourceArtifactHash = "a882610cd282660c1dc457ee8b4d128f567811767d100812987833a1e1089017";
        attribute :>> sourceLocation = "CSV records 425";
        attribute :>> interpretationStatus = "TEXT_IMPORTED_SEMANTIC_MAPPING_PENDING";
    }

    requirement cSB4303 : ImportedCFERequirement {
        doc /* SB: Subscribe To Message
            Upon receipt of a Request to Subscribe to an SB message, the cFE shall establish a route using the Request-specified Message ID, the Request-specified Pipe ID, the Request-specified MsgId-to-Pipe limit and the Request-specified QoS.
            
            Rationale: Run time subscription supports the cFE goals of easy system integration and run time reconfigurations.
        */
        attribute :>> sourceRequirementId = "cSB4303";
        attribute :>> sourceCommit = "7d283938c9af5bd6e439f3fc307e61b0c7799640";
        attribute :>> sourceArtifactHash = "a882610cd282660c1dc457ee8b4d128f567811767d100812987833a1e1089017";
        attribute :>> sourceLocation = "CSV records 429";
        attribute :>> interpretationStatus = "TEXT_IMPORTED_SEMANTIC_MAPPING_PENDING";
    }

    requirement cSB4305 : ImportedCFERequirement {
        doc /* SB: Send Message
            Upon receipt of a Request to send an SB Message, the cFE shall route the SB Message to the Pipes of all Applications that have Subscribed to the SB Message.
            
            Rationale: This form of message passing, supports one-to-one, one-to-many, and many-to-one (all desired by branch members) in a flexible, low overhead manner.  It has been common for telemetry packets to be sent to many destinations, such as a real-time telemetry.
        */
        attribute :>> sourceRequirementId = "cSB4305";
        attribute :>> sourceCommit = "7d283938c9af5bd6e439f3fc307e61b0c7799640";
        attribute :>> sourceArtifactHash = "a882610cd282660c1dc457ee8b4d128f567811767d100812987833a1e1089017";
        attribute :>> sourceLocation = "CSV records 433";
        attribute :>> interpretationStatus = "TEXT_IMPORTED_SEMANTIC_MAPPING_PENDING";
    }

    requirement cSB4305_3 : ImportedCFERequirement {
        doc /* SB: Send Message - Pipe Overflow
            If routing a Message to an Application's Pipe results in a Pipe Overflow, the cFE shall abort the send to that pipe, issue an event, increment the Pipe Overflow error counter, and continue sending to the remaining pipes.
            
            Rationale: The ground needs to know if a message cannot be routed to its destination. A Pipe Overflow occurs when the SB attempts to write to a Pipe that is completely full of SB messages. The number of messages a Pipe is capable of storing is defined by a platform configuration parameter.
        */
        attribute :>> sourceRequirementId = "cSB4305.3";
        attribute :>> sourceCommit = "7d283938c9af5bd6e439f3fc307e61b0c7799640";
        attribute :>> sourceArtifactHash = "a882610cd282660c1dc457ee8b4d128f567811767d100812987833a1e1089017";
        attribute :>> sourceLocation = "CSV records 436";
        attribute :>> interpretationStatus = "TEXT_IMPORTED_SEMANTIC_MAPPING_PENDING";
    }

    requirement cSB4305_6 : ImportedCFERequirement {
        doc /* SB: Send Message - Max Size
            If the SB Message is greater than the `<MISSION_DEFINED>` maximum message size then the cFE shall not send the message, issue an event message and increment the message send error counter.
            
            Rationale: The cFE should not make any assumptions about why the message was too big and just not send it.
        */
        attribute :>> sourceRequirementId = "cSB4305.6";
        attribute :>> sourceCommit = "7d283938c9af5bd6e439f3fc307e61b0c7799640";
        attribute :>> sourceArtifactHash = "a882610cd282660c1dc457ee8b4d128f567811767d100812987833a1e1089017";
        attribute :>> sourceLocation = "CSV records 439";
        attribute :>> interpretationStatus = "TEXT_IMPORTED_SEMANTIC_MAPPING_PENDING";
    }

    requirement cSB4307 : ImportedCFERequirement {
        doc /* SB: Receive Message With Timeout
            Upon receipt of a Request to receive a SB Message from a Pipe with a pending timeout, the cFE shall suspend execution of the Application until a SB Message is present on the Pipe or the timeout has expired.
            
            Rationale: A receive Request with a suspension timeout provides a blocking method of retrieving SB messages. This is useful for data driven Applications and has been used on all heritage missions with a SB. The timeout is useful for fault recovery for Applications that always expect data to arrive or to allow periodic processing for Applications that are not purely data driven. If a SB Message is queued on the Pipe then the SB Message will be provided to the Application and the Application’s execution will not be suspended. Tasks that process telemetry packets often receive many types of packets from different sources.  There should be a mechanism that allows a task to wait for many different types of messages simultaneously.  Heritage implementations of SB do this by directing the messages into one queue (or several queues, to implement priority levels).
        */
        attribute :>> sourceRequirementId = "cSB4307";
        attribute :>> sourceCommit = "7d283938c9af5bd6e439f3fc307e61b0c7799640";
        attribute :>> sourceArtifactHash = "a882610cd282660c1dc457ee8b4d128f567811767d100812987833a1e1089017";
        attribute :>> sourceLocation = "CSV records 443";
        attribute :>> interpretationStatus = "TEXT_IMPORTED_SEMANTIC_MAPPING_PENDING";
    }

    requirement cSB4332 : ImportedCFERequirement {
        doc /* SB: Subscribe to Message With Defaults
            Upon receipt of a Request, the cFE shall establish a route for the requested message ID on the requested pipe, using the '<MISSION_DEFINED>' default quality of service and message limit.
            
            Rationale: Subscription management.
        */
        attribute :>> sourceRequirementId = "cSB4332";
        attribute :>> sourceCommit = "7d283938c9af5bd6e439f3fc307e61b0c7799640";
        attribute :>> sourceArtifactHash = "a882610cd282660c1dc457ee8b4d128f567811767d100812987833a1e1089017";
        attribute :>> sourceLocation = "CSV records 467";
        attribute :>> interpretationStatus = "TEXT_IMPORTED_SEMANTIC_MAPPING_PENDING";
    }

    requirement cSB4328 : ImportedCFERequirement {
        doc /* SB: Validate Checksum
            Upon receipt of a Request, the cFE shall provide the checksum validation result of the requested message.
            
            Rationale: Message management utility.
        */
        attribute :>> sourceRequirementId = "cSB4328";
        attribute :>> sourceCommit = "7d283938c9af5bd6e439f3fc307e61b0c7799640";
        attribute :>> sourceArtifactHash = "a882610cd282660c1dc457ee8b4d128f567811767d100812987833a1e1089017";
        attribute :>> sourceLocation = "CSV records 461";
        attribute :>> interpretationStatus = "TEXT_IMPORTED_SEMANTIC_MAPPING_PENDING";
    }

}
