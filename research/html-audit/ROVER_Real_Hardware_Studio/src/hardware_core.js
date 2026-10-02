'use strict';
/* Official published facts are not measured robot performance. All operational
   budgets and the base/tray/battery catalogue remain explicit design assumptions. */
const HardwareData = RoverCore.freeze({
 version:'rover-hardware-catalog/1', reviewedOn:'2026-09-15',
 sources:[
  {id:'HW-NX',title:'NVIDIA · Jetson Orin NX Series Modules datasheet',url:'https://developer.nvidia.com/downloads/jetson-orin-nx-module-series-data-sheet',location:'Overview pp.1–3; Module drawing',scope:'16GB module CPU/GPU/memory, 69.6×45mm, external storage, module power modes. Carrier and whole-system input are NOT specified by these facts.'},
  {id:'HW-PI',title:'Raspberry Pi · Raspberry Pi 5 product specification',url:'https://www.raspberrypi.com/products/raspberry-pi-5/',location:'Specification',scope:'BCM2712, A76 2.4GHz, RAM variants, USB/Ethernet/PCIe. PSU capacity is not average load.'},
  {id:'HW-PI-MECH',title:'Raspberry Pi 5 · official mechanical drawing',url:'https://pip.raspberrypi.com/documents/RP-008347-DS-1-raspberry-pi-5-mechanical-drawing.pdf',location:'single sheet',scope:'85×56mm reference board outline. Drawing explicitly excludes production data/tolerances and some components.'},
  {id:'HW-PI-USB',title:'Raspberry Pi documentation · USB current and fan budget',url:'https://www.raspberrypi.com/documentation/computers/raspberry-pi.html',location:'Universal Serial Bus → Raspberry Pi 5',scope:'600mA peripheral limit with ordinary 3A supply, 1.6A with detected 5V5A supply; budget shared with fan.'},
  {id:'HW-D435',title:'RealSense · D435i technical specification',url:'https://www.realsenseai.com/cn/products/d435i/',location:'深度参数 / RGB / 物理参数',scope:'Stereo depth, 87×58° depth FOV, ideal .3–3m, depth up to1280×720, up to90fps in supported modes (not necessarily together), RGB1920×1080@30, USB-C3.1Gen1,90×25×25mm, IMU.'},
  {id:'HW-RS-ROS',title:'RealSense · ROS wrapper',url:'https://github.com/realsenseai/realsense-ros',location:'README and device/stream configuration',scope:'Driver/stream integration reference; actual target OS, firmware, stream combinations and throughput remain untested.'},
  {id:'HW-LIVOX',title:'Livox · Mid-360S specifications',url:'https://www.livoxtech.com/mid-360s/specs',location:'Basic specs / notes 2,4,5,8',scope:'360° by -7..52°,200kpoints/s,10Hztypical,100BASE-TX,ICM40609,9–27V,6.5W; selfheating peak14W;65×65×60mm265g.40m@10%100klx;100m is cutoff not guaranteed detection.'},
  {id:'HW-LIVOX-SUPPORT',title:'Livox · Mid-360S support & downloads',url:'https://www.livoxtech.com/support/mid-360s',location:'downloads',scope:'Use exact S variant, protocol, SDK/driver release and firmware. User spelling LIVO360s is only an unconfirmed alias.'},
  {id:'HW-LIVOX-ROS',title:'Livox · livox_ros_driver2',url:'https://github.com/Livox-SDK/livox_ros_driver2',location:'Supported lidar list; transfer formats',scope:'Public repository includes Mid360s material in indexed documentation; retrieved README snapshots differed. Pin/verify a Mid360s-capable version before deployment; no live driver tested here.'},
  {id:'HW-PC2SCAN',title:'ROS perception · pointcloud_to_laserscan',url:'https://github.com/ros-perception/pointcloud_to_laserscan',location:'PointCloudToLaserScanNode',scope:'Converts PointCloud2 to LaserScan under configured height/frame/angle conditions; not universally interchangeable with a native scanner.'},
  {id:'HW-SLAM',title:'SLAM Toolbox · 2D mapping and localization',url:'https://github.com/SteveMacenski/slam_toolbox',location:'API / subscriptions / transforms',scope:'LaserScan and transforms for chosen 2D route; motion estimation and TF must be provided and validated separately.'}
 ],
 compute:{
  nx16:{name:'Jetson Orin NX 16GB',short:'Orin NX 16GB',form:'module_plus_unselected_carrier',ram_GB:16,cpu:'8× Arm Cortex-A78AE',gpu:'1024 CUDA cores / 32 Tensor cores',memory:'16GB 128-bit LPDDR5',boardFootprint_mm:[69.6,45],cudaHardware:true,modulePowerModes_W:[10,15,25,40],storage:'External NVMe; carrier/SSD not selected',source:['HW-NX'],defaults:{computeA_W:12,computeB_W:24}},
  pi5_8:{name:'Raspberry Pi 5 · 8GB',short:'Pi 5 · 8GB',form:'single_board',ram_GB:8,cpu:'4× Cortex-A76 @2.4GHz',gpu:'VideoCore VII; no NVIDIA CUDA GPU',memory:'LPDDR4X-4267',boardFootprint_mm:[85,56],cudaHardware:false,usb3HostPorts:2,ethernet:'Gigabit Ethernet',storage:'microSD; PCIe2.0×1 NVMe requires HAT/adapter',source:['HW-PI','HW-PI-MECH','HW-PI-USB'],defaults:{computeA_W:7,computeB_W:11}},
  pi5_16:{name:'Raspberry Pi 5 · 16GB',short:'Pi 5 · 16GB',form:'single_board',ram_GB:16,cpu:'4× Cortex-A76 @2.4GHz',gpu:'VideoCore VII; no NVIDIA CUDA GPU',memory:'LPDDR4X-4267',boardFootprint_mm:[85,56],cudaHardware:false,usb3HostPorts:2,ethernet:'Gigabit Ethernet',storage:'microSD; PCIe2.0×1 NVMe requires HAT/adapter',source:['HW-PI','HW-PI-MECH','HW-PI-USB'],defaults:{computeA_W:7,computeB_W:11}}
 },
 camera:{id:'D435I',name:'RealSense D435i',physicalId:'RS-D435I-01',body_mm:[90,25,25],depthFov_deg:[87,58],idealDepthRange_m:[.3,3],depthMaxResolution:[1280,720],depthMaxFps:90,rgbPublishedMode:[1920,1080,30],depthShutter:'global',rgbShutter:'rolling',usb:'USB-C 3.1 Gen1',imu:'built-in accelerometer + gyroscope',source:['HW-D435','HW-RS-ROS'],notes:'Maximum depth resolution and maximum frame rate are separate limits. Stream combination must be enumerated on real device. 4W is an editable power reservation, not a vendor rating.'},
 lidar:{id:'MID360S',name:'Livox Mid-360S',requestedAlias:'LIVO360s',aliasIdentity:'UNCONFIRMED_USER_SPELLING; this demo explicitly selects official Mid-360S',body_mm:[65,65,60],mass_g:265,horizontalFov_deg:360,verticalFov_deg:[-7,52],pointRate_per_s:200000,typicalFrame_Hz:10,link:'100BASE-TX Ethernet',imu:'ICM40609',supply_V:[9,27],publishedPower_W:6.5,coldSelfHeatPeak_W:14,rangeTypical_m:40,rangeConditions:'10% reflectivity at100klx',cutoff_m:100,source:['HW-LIVOX','HW-LIVOX-SUPPORT','HW-LIVOX-ROS']}
});
function hardwareDefaults(computeId='nx16'){
 const p=HardwareData.compute[computeId];if(!p)throw Error('Unknown compute profile');
 return {computeId,...p.defaults,drive_W:10,other_W:1,cameraReservation_W:4,conversionEfficiency:.9,lidarSupply_V:12,pointcloudAdapter:true,usbMode:'usb3',piSupply:'5a',usbOther_A:.15,fan_A:.15,visionRuntime:'portable',depthProfile:[1280,720,30],depthUseMax_m:3,jetsonCarrier:'NOT_SELECTED',firmware:'NOT_PINNED',osImage:'TO_BE_VALIDATED'};
}
let HW=hardwareDefaults();
const HardwareCore=(()=>{
 const C=RoverCore,orig={config:C.config,checks:C.checks,model:C.model,sysml:C.sysml,alignment:C.alignment};
 const num=n=>Number(Number(n).toFixed(6));
 function snapshot(){return C.clone(HW);}
 function plan(h=HW){const baseDevice=h.drive_W+h.computeA_W+HardwareData.lidar.publishedPower_W+h.other_W;
 return {baseDevice_W:num(baseDevice),baseBattery_W:num(baseDevice/h.conversionEfficiency),defaultIncrementBattery_W:num((h.computeB_W-h.computeA_W+h.cameraReservation_W)/h.conversionEfficiency),cameraUsbReservation_A:num(h.cameraReservation_W/5),sources:{lidar:'HW-LIVOX published reference power, not actual average',allOtherPower:'AUTHOR_EDITABLE_DESIGN_ALLOWANCES',efficiency:'AUTHOR_ASSUMPTION'},scope:'Device-side loads excluding downstream camera in host allowance; divide by aggregate DC efficiency ONCE. Base/tray/battery remain synthetic. No added mass/temperature model.'};}
 C.config=function(id,deltaW){const c=orig.config(id,0),h=snapshot(),p=plan(h);const add=deltaW===undefined?p.defaultIncrementBattery_W:deltaW;if(!Number.isFinite(add)||add<0||add>500)throw Error('Invalid hardware workload');c.basePower_W=p.baseBattery_W;c.visionIncrement_W=c.vision?add:0;c.power_W=num(c.basePower_W+c.visionIncrement_W);c.hardware=h;c.hardwareFacts={compute:C.clone(HardwareData.compute[h.computeId]),camera:C.clone(HardwareData.camera),lidar:C.clone(HardwareData.lidar)};c.powerPlan={...p,effectiveIncrementBattery_W:c.visionIncrement_W,overrideIncrement:Math.abs(add-p.defaultIncrementBattery_W)>1e-4,computeDeviceAllowance_W:c.vision?h.computeB_W:h.computeA_W};return c;};
 C.checks=function(c,adapter=true){const r=orig.checks(c,adapter),h=c.hardware,p=c.hardwareFacts.compute,add=(id,name,ok,actual,required,scope)=>r.checks.push({id,requirement:'INTERFACE-DESIGN',name,status:ok?'PASS':'FAIL',actual,required,scope});
 add('K-PCLOUD','三维点云到二维扫描职责',h.pointcloudAdapter,'Mid-360S → driver → PointCloud2 → '+(h.pointcloudAdapter?'projection → LaserScan':'direct, incompatible'),'explicit projection for selected 2D route','Checks declared graph choice; not execution or calibrated slicing');
 add('K-LIDAR-V','雷达输入电压范围',h.lidarSupply_V>=9&&h.lidarSupply_V<=27,h.lidarSupply_V,'9…27 V DC','Nominal design value vs published range; no surge/cold-start test');
 if(c.vision){add('K-USB-LINK','所选D435i图像链路',h.usbMode==='usb3',h.usbMode,'USB3 path for planned high-resolution profile','USB2 may support other profiles; no runtime link/profile enumeration');add('K-CUDA','视觉运行时硬件前提',h.visionRuntime!=='cuda_only'||p.cudaHardware,h.visionRuntime+' / '+p.gpu,'CUDA GPU only if CUDA-only runtime selected','Presence only; build, throughput and algorithm performance untested');}
 if(p.form==='single_board'){const limit=h.piSupply==='5a'?1.6:.6,required=num(h.usbOther_A+h.fan_A+(c.vision?plan(h).cameraUsbReservation_A:0));add('K-PI-USB','Pi5外设/风扇供电预算',required<=limit,required+' A',limit+' A aggregate','Camera current derived from editable reservation, not measured draw. 5A mode assumes firmware detection; all USB ports + fan share budget.');}
 r.unresolvedHardware=[{id:'U-DRIVER',status:'NOT_RUN',detail:'Mid-360S-capable SDK/driver and RealSense firmware/wrapper versions must be pinned and tested; no installed driver has run.'},{id:'U-PROFILE',status:'NOT_RUN',detail:'Depth1280×720@30 is a planned mode; RGB and IMU simultaneous stream negotiation is not tested.'},{id:'U-TF',status:'UNKNOWN',detail:'IMU clocks, extrinsics, odometry and transform ownership require integration verification. Two built-in IMUs are not plug-and-play fusion.'},{id:'U-PERFORMANCE',status:'NOT_RUN',detail:'Real navigation, inference speed, thermal throttling, endurance and stopping remain untested.'}];if(p.form==='module_plus_unselected_carrier')r.unresolvedHardware.unshift({id:'U-CARRIER',status:'UNKNOWN',detail:'Orin NX16 module selected, carrier unspecified: external input voltage, connector count, USB power, storage and cooling are NOT established.'});
 r.notEstablished={...r.notEstablished,hardwareFacts:'PUBLISHED_SPECS_NOT_MEASURED',carrier:p.form==='single_board'?'NOT_APPLICABLE':'NOT_SELECTED',softwareCompatibility:'NOT_RUN',depthStreamConcurrency:'NOT_RUN'};
 r.powerPlan=C.clone(c.powerPlan);r.hardwareFingerprint=C.checksum(h);r.assumptions=[c.powerPlan.scope,'Published component facts are cited; all host workload/camera current reservations are design assumptions.','Jetson power modes and Pi PSU capacity are NOT whole-system average consumption.','Source facts do not prove system compatibility or safety.','Same authored data generates graph and SysML; actual parser NOT RUN.'];return r;};
 C.model=function(c,adapter=true){const g=orig.model(c,adapter),h=c.hardware,p=c.hardwareFacts.compute;
 const patch=(id,label,data,tags=[])=>{const n=g.nodes.find(x=>x.id===id);if(n){n.label=label;n.data=data;n.tags=[...n.tags,...tags];return n;}};
 const add=(id,label,kind,data,tags=[])=>g.nodes.push({id,label,kind,path:`Rover_${c.id}::${id}`,file:`Rover_${c.id}.sysml`,revision:c.id,data,tags});const edge=(from,to,type)=>g.edges.push({from,to,type});
 patch('rover.lidar','Livox Mid-360S',{model:'Mid-360S',physicalId:'LIVOX-S-01',output:'Ethernet/UDP point packets',pointRate_per_s:200000,typicalFrame_Hz:10,supply_V:[9,27],publishedPower_W:6.5,body_mm:[65,65,60],sourceRefs:['HW-LIVOX'],sourceStatus:'PUBLISHED_FACT'},['MID-360S','点云','PointCloud2','以太网']);
 patch('rover.lidar.imu','ICM40609 · 雷达内含',{physicalId:'LIVOX-S-01/IMU',chip:'ICM40609',includedIn:'LIVOX-S-01',use:'driver output for estimator, not direct SLAM Toolbox input',calibration:'UNKNOWN',sourceRefs:['HW-LIVOX']},['ICM40609']);
 patch('rover.navigation','本地二维导航',{route:'LaserScan-based mapping/localization + local navigation',input:'LaserScan + odometry/TF',output:'BodyVelocity',requiresInternet:false,deployedOn:'rover.compute',execution:'NOT_RUN',sourceRefs:['HW-SLAM']});
 patch('rover.meanLoadAtBattery_W','电池侧平均功耗',{base_W:c.basePower_W,added_W:c.visionIncrement_W,total_W:c.power_W,plan:c.powerPlan,provenance:'MIXED_PUBLISHED_REFERENCE_AND_ASSUMPTIONS'});
 add('rover.compute',p.short,'part',{selection:h.computeId,ram_GB:p.ram_GB,cpu:p.cpu,gpu:p.gpu,form:p.form,meanDeviceBudget_W:c.powerPlan.computeDeviceAllowance_W,powerBudgetProvenance:'AUTHOR_ASSUMPTION_NOT_TDP',storage:p.storage,sourceRefs:p.source},['Jetson','Orin','树莓派','Raspberry','Pi5','主控','计算','CUDA','电源','功耗']);
 if(p.form!=='single_board'){add('rover.compute.module','Orin NX16 · 模块','part',{physicalId:'NX16-MODULE-01',ram_GB:16,footprint_mm:[69.6,45],sourceRefs:['HW-NX'],powerModes_W:[10,15,25,40]},['Orin','主控','模块']);add('rover.compute.carrier','载板 · 型号待确认','part',{selection:'NOT_SELECTED',externalInput_V:null,usbCurrent_A:null,boardOutline_mm:null,sourceStatus:'UNKNOWN_NOT_MANUFACTURER_FACT',illustration_mm:[100,80]},['载板','USB','供电']);edge('rover.compute','rover.compute.module','includes');edge('rover.compute','rover.compute.carrier','requires');}
 add('rover.livoxDriver','Livox ROS Driver 2','part',{target:'Mid-360S',output:'PointCloud2 + IMU',transport:'100BASE-TX / UDP',version:'PIN_S_CAPABLE_RELEASE',deployedOn:'rover.compute',execution:'NOT_RUN',sourceRefs:['HW-LIVOX-ROS']},['驱动','雷达','MID-360S','PointCloud2']);
 if(h.pointcloudAdapter)add('rover.cloudProjection','点云→二维扫描','part',{implementation:'pointcloud_to_laserscan',input:'PointCloud2',output:'LaserScan',heightSlice_m:null,targetFrame:null,configuration:'MUST_CONFIGURE_AND_VALIDATE',deployedOn:'rover.compute',sourceRefs:['HW-PC2SCAN']},['点云','扫描','适配','PointCloud2']);
 add('rover.stateEstimator','状态估计 / TF职责','part',{imuInput:'Livox driver IMU',otherInput:'wheel odometry',cameraImuInput:'NOT_FUSED',extrinsics:'UNVERIFIED',deployedOn:'rover.compute'},['IMU','时钟','坐标','TF']);
 g.edges=g.edges.filter(e=>!(e.from==='rover.lidar'&&e.to==='rover.navigation')&&!(e.from==='rover.lidar.imu'&&e.to==='rover.navigation'));
 edge('rover','rover.compute','contains');edge('rover','rover.livoxDriver','contains');edge('rover.lidar','rover.livoxDriver','EthernetUDP');edge('rover.lidar','rover.compute','Ethernet100BASE-TX');edge('rover.livoxDriver','rover.stateEstimator','ImuSample');edge('rover.stateEstimator','rover.navigation','TF_and_odometry');edge('rover','rover.stateEstimator','contains');edge('rover.compute','rover.meanLoadAtBattery_W','included_host_allowance');
 if(h.pointcloudAdapter){edge('rover','rover.cloudProjection','contains');edge('rover.livoxDriver','rover.cloudProjection','PointCloud2');edge('rover.cloudProjection','rover.navigation','LaserScan');}else edge('rover.livoxDriver','rover.navigation','INCOMPATIBLE_PointCloud2_to_LaserScan');
 for(const id of ['rover.navigation','rover.commandAdapter','rover.livoxDriver','rover.cloudProjection','rover.stateEstimator'])if(g.nodes.some(n=>n.id===id))edge(id,'rover.compute','deployedOn');
 if(c.vision){patch('rover.camera','RealSense D435i',{physicalId:'RS-D435I-01',depthTechnology:'stereo/global shutter',rgbShutter:'rolling',usb:'USB-C3.1Gen1',depthFov_deg:[87,58],body_mm:[90,25,25],depthProfileProposed:h.depthProfile,depthRangePolicy_m:[.3,h.depthUseMax_m],powerReservation_W:h.cameraReservation_W,sourceRefs:['HW-D435','HW-RS-ROS'],concurrency:'NOT_RUN'},['D435i','USB','深度']);
 add('rover.camera.imu','D435i · 内置IMU','part',{physicalId:'RS-D435I-01/IMU',includedIn:'RS-D435I-01',distinctPhysicalDevice:true,statisticalIndependence:"NOT_ASSESSED",fusion:'NOT_CONFIGURED',sourceRefs:['HW-D435']},['D435i','IMU']);
 add('rover.realsenseDriver','RealSense ROS驱动','part',{input:'USB3 device streams',output:'RGBDFrame + CameraInfo + IMU',deployedOn:'rover.compute',version:'NOT_PINNED',sourceRefs:['HW-RS-ROS']},['D435i','USB','驱动']);
 patch('rover.visionProcessor','本地视觉处理',{deployedOn:'rover.compute',requiresInternet:false,runtime:h.visionRuntime,execution:'NOT_RUN'},['CUDA']);patch('rover.imageRecorder','本地记录任务',{deployedOn:'rover.compute',requiresInternet:false,storage:'NOT_SELECTED',execution:'NOT_RUN'});
 g.edges=g.edges.filter(e=>!(e.from==='rover.camera'&&['rover.visionProcessor','rover.imageRecorder'].includes(e.to)));
 edge('rover.camera','rover.camera.imu','includes');edge('rover','rover.realsenseDriver','contains');edge('rover.camera','rover.compute',h.usbMode==='usb3'?'USB3':'USB2_SELECTED');edge('rover.camera','rover.realsenseDriver','USBDeviceStream');edge('rover.realsenseDriver','rover.visionProcessor','RGBDFrame');edge('rover.realsenseDriver','rover.imageRecorder','RGBDFrame');
 for(const id of ['rover.realsenseDriver','rover.visionProcessor','rover.imageRecorder'])edge(id,'rover.compute','deployedOn');}
 g.schema='rover.hardware.graph/1';g.fingerprint=C.checksum({config:c,adapter});g.sourceCatalogRevision=HardwareData.version;g.hardwareEvidence=C.checks(c,adapter).unresolvedHardware;return g;};
 const hwCode=`// REAL PRODUCT NAMES / PUBLISHED FACTS + EXPLICIT DESIGN ABSTRACTIONS.
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
}`;
 const sources={...C.supplierCodes,'HardwareOffers.sysml':hwCode};
 sources['PerceptionOffer.sysml']=`// READ ONLY: named product facts. No hardware or parser test claimed.\npackage PerceptionOffer {\n private import HardwareOffers::*;\n part def OfferedLidar :> Mid360S;\n part def OfferedDepthCamera :> D435i;\n}\n`;
 C.supplierCodes=C.freeze(sources);
 C.sysml=function(c,adapter=true){const h=c.hardware,p=c.hardwareFacts.compute;let text=orig.sysml(c,adapter).replace('private import SoftwareOffer::*;','private import SoftwareOffer::*;\n    private import HardwareOffers::*;');
 text=text.replace('part lidar : LidarChoice;',`part lidar : LidarChoice;\n        part compute : ${h.computeId==='nx16'?'JetsonAssembly':h.computeId==='pi5_16'?'RaspberryPi5_16':'RaspberryPi5_8'};\n        part livoxDriver : LivoxDriver;\n        part stateEstimator : StateEstimator;${h.pointcloudAdapter?'\n        part cloudProjection : CloudProjection;':''}\n        doc /* Navigation and drivers DEPLOYED on compute; software nodes are not extra boards. */`);
 text=text.replace('connect lidar.output to navigation.scanIn;',`connect lidar.packets to livoxDriver.packetIn;${h.pointcloudAdapter?'\n        connect livoxDriver.cloudOut to cloudProjection.cloudIn;\n        connect cloudProjection.scanOut to navigation.scanIn;':'\n        // INCOMPATIBLE: PointCloud2 is not LaserScan. No invented compatible connector.'}`);
 text=text.replace('connect lidar.imu.output to navigation.imuIn;','connect livoxDriver.imuOut to stateEstimator.imuIn;\n        // State estimator to navigation TF/odometry deployment still needs full model detail.');
 if(c.vision){text=text.replace('part camera : OfferedDepthCamera;','part camera : OfferedDepthCamera;\n        part realsenseDriver : RealSenseDriver;');text=text.replace('connect camera.frameOut to visionProcessor.frameIn;','connect camera.usbStream to realsenseDriver.usbIn;\n        connect realsenseDriver.frameOut to visionProcessor.frameIn;');text=text.replace('connect camera.frameOut to imageRecorder.frameIn;','connect realsenseDriver.frameOut to imageRecorder.frameIn;');}
 text=text.replace('part rover {',`part rover {\n        attribute plannedLidarSupply_V : Real = ${h.lidarSupply_V};\n        attribute assumedComputeInput_W : Real = ${c.powerPlan.computeDeviceAllowance_W};\n        attribute assumedCameraReserve_W : Real = ${c.vision?h.cameraReservation_W:0};\n        attribute assumedDcEfficiency : Real = ${h.conversionEfficiency};\n        doc /* These four parameters are design assumptions, not manufacturer measured load. */`);
 return `// Hardware profile ${p.name}; Livox Mid-360S; ${c.vision?'RealSense D435i':'no D435i in A'}\n// ${HardwareData.version}; sources checked ${HardwareData.reviewedOn}.\n// GUI graph is authored data, NOT a parser result. Import ALL companion model files.\n`+text;};
 C.alignment=function(adapter=true){return [
 {id:'M-01',source:'HardwareOffers::LivoxDriver.cloudOut',target:'LocalNavigation.scanIn',sourceType:'PointCloud2 (3D)',targetType:'LaserScan (2D)',proposedTag:'RequireModification',decision:HW.pointcloudAdapter?'选择点云投影适配职责；切片高度、TF和障碍表达须实测。不能只改字段名。':'BLOCK：直接把三维点云连到二维扫描接口。',sourceUnchanged:true},
 orig.alignment(adapter)[1],
 {id:'M-03',source:'Mid360S.imu + D435i.imu',target:'state estimation inputs',sourceType:'two physical built-in IMUs',targetType:'time/calibration contract',proposedTag:'RequireComplement',decision:'Livox ICM40609 与D435i惯性单元分别登记。未自动融合，不重复采购；有两个IMU不证明冗余。',sourceUnchanged:true},
 orig.alignment(adapter)[3],
 {id:'M-05',source:'D435i USB-C3.1Gen1',target:HardwareData.compute[HW.computeId].name,sourceType:'USB peripheral',targetType:'host + driver + power budget',proposedTag:'RequireComplement',decision:HW.computeId==='nx16'?'NX是模块：载板、USB主机连接器和端口电流未确认；不能把模块参数当外部XT30输入。':'Pi5有USB3主机口；供电模式决定USB/风扇总预算，仍须枚举实际相机profile。',sourceUnchanged:true},
 {id:'M-06',source:'vision runtime requirement',target:HardwareData.compute[HW.computeId].gpu,sourceType:HW.visionRuntime,targetType:'compute backend',proposedTag:HW.visionRuntime==='cuda_only'&&HW.computeId!=='nx16'?'FullyUnmatched':'RequireComplement',decision:'只检查CUDA硬件前提；可移植CPU路径的速度、内存和软件构建仍未运行。',sourceUnchanged:true}
 ];};
 return {snapshot,plan,original:orig};
})();
