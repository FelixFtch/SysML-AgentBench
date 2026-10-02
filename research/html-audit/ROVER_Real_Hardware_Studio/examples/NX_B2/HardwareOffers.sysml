// REAL PRODUCT NAMES / PUBLISHED FACTS + EXPLICIT DESIGN ABSTRACTIONS.
// Authored draft. Parser NOT RUN. See hardware_catalog.json for per-field sources.
package HardwareOffers {
    private import ScalarValues::*;
    private import RoverLibrary::*;
    item def LivoxEthernetPackets;
    item def PointCloud2Data;
    item def USBDeviceStream;
    port def LivoxPacketPort { out item packet : LivoxEthernetPackets; }
    port def PointCloudPort { out item cloud : PointCloud2Data; }
    port def USBDevicePort { out item stream : USBDeviceStream; }
    part def ComputeHost { attribute memory_GB : Integer; attribute cudaHardware : Boolean; }
    part def JetsonOrinNX16Module {
        attribute memory_GB : Integer = 16;
        attribute length_mm : Real = 69.6;
        attribute width_mm : Real = 45.0;
        doc /* HW-NX: MODULE, not carrier. External supply & USB budget depend on carrier. */
    }
    part def UnselectedCarrier { doc /* UNKNOWN: part number, external input, USB current, SSD, cooling. */ }
    part def JetsonAssembly :> ComputeHost {
        attribute :>> memory_GB = 16;
        attribute :>> cudaHardware = true;
        part module : JetsonOrinNX16Module;
        part carrier : UnselectedCarrier;
    }
    part def RaspberryPi5_8 :> ComputeHost {
        attribute :>> memory_GB = 8;
        attribute :>> cudaHardware = false;
        attribute boardLength_mm : Real = 85.0;
        attribute boardWidth_mm : Real = 56.0;
        doc /* HW-PI: BCM2712, 4xA76 2.4GHz, two USB3, Gigabit Ethernet. */
    }
    part def RaspberryPi5_16 :> RaspberryPi5_8 { attribute :>> memory_GB = 16; }
    part def Mid360S {
        attribute minSupply_V : Real = 9.0;
        attribute maxSupply_V : Real = 27.0;
        attribute referencePower_W : Real = 6.5;
        attribute coldSelfHeatPeak_W : Real = 14.0;
        attribute nominalPointRate_per_s : Real = 200000.0;
        attribute typicalFrame_Hz : Real = 10.0;
        attribute length_mm : Real = 65.0;
        attribute width_mm : Real = 65.0;
        attribute height_mm : Real = 60.0;
        port packets : LivoxPacketPort;
        part imu : Imu;
        doc /* HW-LIVOX: ICM40609 inside; raw data is not LaserScan. */
    }
    part def LivoxDriver {
        port packetIn : ~LivoxPacketPort;
        port cloudOut : PointCloudPort;
        port imuOut : ImuPort;
        doc /* SDK/firmware and S-capable driver revision must be verified. */
    }
    part def CloudProjection {
        port cloudIn : ~PointCloudPort;
        port scanOut : ScanPort;
        doc /* pointcloud_to_laserscan obligation; frame and height slice NOT calibrated. */
    }
    part def StateEstimator { port imuIn : ~ImuPort; doc /* Wheel odom and TF configuration pending. */ }
    part def D435i {
        attribute length_mm : Real = 90.0;
        attribute depth_mm : Real = 25.0;
        attribute height_mm : Real = 25.0;
        attribute depthFovHorizontal_deg : Real = 87.0;
        attribute depthFovVertical_deg : Real = 58.0;
        port usbStream : USBDevicePort;
        part imu : Imu;
        doc /* HW-D435: depth global shutter; RGB rolling. Host required. */
    }
    part def RealSenseDriver {
        port usbIn : ~USBDevicePort;
        port frameOut : ImagePort;
        port imuOut : ImuPort;
        doc /* Driver interpretation of USB streams; no physical USB wire is modeled here. */
    }
}