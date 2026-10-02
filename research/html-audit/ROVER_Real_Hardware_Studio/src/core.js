'use strict';
/* Deterministic teaching-domain core. No model API, SysML parser, embeddings,
   physical simulator or vendor hardware validation is implemented here. */
const RoverCore = (() => {
  const clone = x => JSON.parse(JSON.stringify(x));
  const freeze = x => {Object.freeze(x); Object.values(x).forEach(v=>{if(v&&typeof v==='object'&&!Object.isFrozen(v))freeze(v);});return x;};
  const PAPER_SOURCES = freeze([
    {id:'NPS',color:'nps',title:'Leveraging Generative AI to Build, Modify, and Query MBSE Models',authors:'Ryan Longshore · Ryan Bell · Raymond Madachy',file:'SYM-AM-24-138(1).pdf',pages:'幻灯片 8、10、12–15（PDF 共19页）',url:'https://dair.nps.edu/bitstream/123456789/5237/1/SYM-AM-24-138.pdf',supported:'SSE-SM 配置建模指令、领域知识、SysML 规范/记法和模板；自行车案例按文字建立模型、增加踏板和承载需求。',transfer:'我们将这种建立/修改方法用于需求模型、模拟供应商模型及小车版本修改。供应商角色划分与小车情境由我们提出。',boundary:'原文是小型案例；这些资料不证明当前 Astra 的 SysML 成功率。本页模型输出为预写模板，不是实际 API 返回。'},
    {id:'CMBSE',color:'cmb',title:'LLM-Assisted Semantic Alignment and Integration in Collaborative Model-Based Systems Engineering Using SysML v2',authors:'Zirui Li · Stephan Husung · Haoze Wang',file:'2508.16181v2(1).pdf',pages:'PDF pp.5–7 · §IV-A/B/D · Fig.1',url:'https://arxiv.org/abs/2508.16181',supported:'七阶段：准备、元素提取、匹配建议、匹配审查、附加包、检查、导出。保留原模型，通过 import/alias/扩展关系做软对齐，并设人工确认。',transfer:'我们保留三份供应商源文件，形成映射JSON与独立集成模型。接口单位适配、去重、版本绑定和数值检查是本项目扩展。',boundary:'alias 仅引用/命名，不等于实现单位转换。原论文部分校验是 LLM 自检；本页独立规则不是 SysML 解析器。本页将确认合并为A/B两道教学审批，不是七阶段逐点复现。'},
    {id:'GRAG',color:'grag',title:'Integrating SysML v2 into a GRAG LLM Pipeline: Design, Implementation and Evaluation',authors:'Elias Bader · Jounes Alexander Gross · Katharina Polanec · Markus Michael Peter · Christian Neureiter',file:'GRAG_SysML_v2(1).pdf',pages:'PDF pp.3–5 · Fig.1 · §IV · Table I',url:'https://github.com/eeeeebader/SysML-v2-GRAG-Pipeline',supported:'模型API JSON-LD → 简化RDF → 节点及一跳邻居 → MiniLM 384维 → FAISS余弦阈值检索 → 重建上下文 → GPT-4.1回答。小样例为电动车。',transfer:'我们将索引用于读取A的电池、负载、托盘及关联需求，帮助变更；批准B后明确重建索引。需求/接口/行为关系需扩展原转换器。',boundary:'本页使用关键词匹配与一跳图展开，不运行MiniLM、FAISS或GPT。图取自教学数据，而非SysML模型API；不称为论文复现或完整影响分析。'},
    {id:'BRIEF',color:'ours',title:'RTRC / UConn · Agentic AI for Systems Engineering Discovery and Design',authors:'用户上传项目书',file:'2706 - RTRC - Agentic AI for Systems Engineering Discovery and Design.docx',pages:'第1页 Statement of Need；第2页 Additional Requirements',url:'',supported:'核心目标是 requirements-to-SysML 的agent探索、比较及证据报告；以多平台海事场景为代表，并要求自然语言需求数据验证。',transfer:'小车是我们选定的方法开发案例；最终替代海事场景需赞助方认可。',boundary:'本页不是RTRC现有工作流的审计，不是已部署产品，也不是完整实验结果。'}
  ]);
  const REQUIREMENTS = freeze([
    {id:'R-01',text:'沿已有室内地图在指定站点间行驶。',owner:'系统',model:'LocalNavigation',check:'职责与连接检查；算法运行尚未验证'},
    {id:'R-02',text:'障碍条件成立时进入停止状态；恢复条件另行审查。',owner:'控制',model:'OperationalStates',check:'只表示行为；无制动/安全认证'},
    {id:'R-03',text:'基本导航和停止处理不依赖互联网。',owner:'软件',model:'LocalNavigation.requiresInternet',check:'本模型子集不分配云端依赖；实测未运行'},
    {id:'R-04',text:'规定工作负载下，估算续航不少于2小时。',owner:'电源',model:'runtimeRequirement / estimatedRuntime_h',check:'0.8 × 额定Wh ÷ 电池侧平均W ≥ 2'},
    {id:'R-05',text:'含附件的整车宽度不超过350 mm。',owner:'机械',model:'roverWidth_mm / BatteryTray',check:'整体包络与固定方向电池仓配合检查'},
    {id:'R-06',text:'可区分待命、导航、停止和故障状态。',owner:'系统',model:'OperationalStates',check:'状态表达；真实控制器执行未验证'}
  ]);
  const CHANGE=freeze({id:'CR-08',requirement:'R-07',text:'增加深度相机、本地处理和图像记录；保持离线导航、2小时续航和350 mm宽度要求。',source:'requirements/change_CR-08.md',provenance:'SYNTHETIC_TEACHING_INPUT',immutableRequirements:['R-03','R-04','R-05']});
  const CATALOG=freeze({provenance:'ALL_SYNTHETIC_NOT_VENDOR_SPECS',energyUsableFraction:0.8,baseBatterySideAverage_W:32,visionIncrementDefault_W:16,batteries:{small:{id:'BAT-96',Wh:96,size_mm:[120,80,45]},large:{id:'BAT-160',Wh:160,size_mm:[140,80,45]}},trays:{original:{id:'TRAY-A',inside_mm:[130,90,50],installedRoverWidth_mm:330},expanded:{id:'TRAY-B',inside_mm:[150,90,50],installedRoverWidth_mm:340}},chassis:{id:'CH-01',wheelRadius_m:0.05,track_m:0.28,included:['MOTOR-L','MOTOR-R','MOTOR-CTRL']},lidar:{id:'LID-01',includes:['IMU-L1'],outputType:'Scan2D'},nav:{id:'NAV-LOCAL',requiresInternet:false,commandType:'BodyVelocity'}});
  function config(id,deltaW=16){if(!['A','B0','B1','B2'].includes(id))throw Error('Unknown candidate');if(!Number.isFinite(deltaW)||deltaW<0||deltaW>100)throw Error('Invalid workload');const vision=id!=='A',battery=clone(CATALOG.batteries[['B1','B2'].includes(id)?'large':'small']),tray=clone(CATALOG.trays[id==='B2'?'expanded':'original']);return {id,requirementRevision:vision?'REQ-B':'REQ-A',vision,battery,tray,basePower_W:32,visionIncrement_W:vision?deltaW:0,power_W:32+(vision?deltaW:0),usableFraction:0.8,minRuntime_h:2,maxWidth_mm:350,requiresInternet:false};}
  function checks(c,adapter=true){const runtime=c.battery.Wh*c.usableFraction/c.power_W;const fits=c.battery.size_mm.every((v,i)=>v<=c.tray.inside_mm[i]);return {candidate:c.id,runtime_h:runtime,usableEnergy_Wh:c.battery.Wh*c.usableFraction,checks:[{id:'K-RUNTIME',requirement:'R-04',name:'续航估算',status:runtime>=c.minRuntime_h?'PASS':'FAIL',actual:runtime,required:c.minRuntime_h,unit:'h',formula:`${c.battery.Wh} Wh × ${c.usableFraction} ÷ ${c.power_W} W`,scope:'Constant battery-side mean load; not measured endurance'}, {id:'K-FIT',requirement:'R-05',name:'电池仓配合',status:fits?'PASS':'FAIL',actual:c.battery.size_mm,required:c.tray.inside_mm,unit:'mm',scope:'Axis-aligned nominal box, fixed orientation; no tolerance/cable/strength test'}, {id:'K-WIDTH',requirement:'R-05',name:'整车宽度',status:c.tray.installedRoverWidth_mm<=c.maxWidth_mm?'PASS':'FAIL',actual:c.tray.installedRoverWidth_mm,required:c.maxWidth_mm,unit:'mm',scope:'Supplied illustrative overall envelope'}, {id:'K-CMD',requirement:'R-01',name:'命令适配职责',status:adapter?'PASS':'FAIL',actual:adapter?'BodyVelocity → DiffDriveAdapter → WheelRPM':'BodyVelocity → WheelRPM, incompatible',scope:'Fixture graph connectivity; not driver implementation'}, {id:'K-LOCAL',requirement:'R-03',name:'无云端依赖分配',status:!c.requiresInternet?'PASS':'FAIL',actual:'No cloud node in bounded fixture',scope:'Model configuration only; no real navigation execution'}],notEstablished:{sysmlParser:'NOT_RUN',requirementsSemanticCoverage:'HUMAN_REVIEW_REQUIRED',brakingSafety:'NOT_RUN',hardwareEndurance:'NOT_RUN',electricalCompatibility:'NOT_CHECKED',mechanicalStrength:'NOT_RUN',cadManufacturability:'NOT_RUN'},assumptions:['All numeric catalog values are synthetic','Mean power is an assumed battery-side value; no second conversion loss deduction','Power increase does not model added-mass drive-load change','Box checks use a fixed declared orientation','Model graphs are authored fixture data, not parsed SysML']};}
  const numericPass=r=>r.checks.every(x=>x.status==='PASS');
  function wheelRpm(v=0.4,w=0.6,r=0.05,b=0.28){if(![v,w,r,b].every(Number.isFinite)||r<=0||b<=0)throw Error('Invalid drive geometry');return {input:{v_mps:v,yaw_rps:w,wheelRadius_m:r,track_m:b},left_rpm:(v-w*b/2)/r*60/(2*Math.PI),right_rpm:(v+w*b/2)/r*60/(2*Math.PI),scope:'Ideal planar differential-drive kinematics; declared directions; no hardware command'};}
  function checksum(x){let h=2166136261;for(const ch of JSON.stringify(x)){h^=ch.charCodeAt(0);h=Math.imul(h,16777619);}return 'demo-fnv-'+(h>>>0).toString(16).padStart(8,'0');}
  const typeCode=`package RoverLibrary {
    private import ScalarValues::*;
    item def Scan2D;
    item def ImuSample;
    item def BodyVelocity { attribute v_mps : Real; attribute yaw_rps : Real; }
    item def WheelRPM { attribute left_rpm : Real; attribute right_rpm : Real; }
    item def RGBDFrame;
    item def LocalObservation;
    port def ScanPort { out item sample : Scan2D; }
    port def ImuPort { out item sample : ImuSample; }
    port def BodyCommandPort { out item command : BodyVelocity; }
    port def WheelCommandPort { out item command : WheelRPM; }
    port def ImagePort { out item frame : RGBDFrame; }
    port def LocalObservationPort { out item observation : LocalObservation; }
    part def Imu { port output : ImuPort; }
    part def Motor;
    part def MotorController { port input : ~WheelCommandPort; }
    part def LidarModule { port output : ScanPort; part imu : Imu; }
    part def DriveBase {
        part motorLeft : Motor; part motorRight : Motor;
        part controller : MotorController;
        port input : ~WheelCommandPort;
        connect input to controller.input;
        attribute wheelRadius_m : Real;
        attribute track_m : Real;
    }
    part def Navigation {
        port scanIn : ~ScanPort;
        port imuIn : ~ImuPort;
        port commandOut : BodyCommandPort;
        attribute requiresInternet : Boolean;
    }
    part def DiffDriveAdapter {
        port bodyIn : ~BodyCommandPort;
        port wheelOut : WheelCommandPort;
        attribute wheelRadius_m : Real;
        attribute track_m : Real;
        doc /* R-01 adapter obligation: declared planar kinematics and signs.
               A model connector does not implement a running motor driver. */
    }
    part def Battery { attribute energy_Wh : Real; attribute length_mm : Real; attribute width_mm : Real; attribute height_mm : Real; }
    part def Tray { attribute insideLength_mm : Real; attribute insideWidth_mm : Real; attribute insideHeight_mm : Real; }
    part def Camera { port frameOut : ImagePort; }
    part def VisionProcessor { port frameIn : ~ImagePort; port resultOut : LocalObservationPort; }
    part def Recorder { port frameIn : ~ImagePort; port observationIn : ~LocalObservationPort; }
}`;
  const supplierCodes=freeze({
    'RoverLibrary.sysml':'// TEACHING DRAFT. Parser NOT RUN. File is a supported-subset proposal, not validated code.\n'+typeCode,
    'PerceptionOffer.sysml':`// SYNTHETIC SUPPLIER OFFER P-01. Read-only in this demo. Parser NOT RUN.
package PerceptionOffer {
    private import RoverLibrary::*;
    part def OfferedLidar :> LidarModule {
        doc /* physical_id LID-01 includes IMU-L1. One physical IMU, not two independent measurements. */
    }
    part def OfferedDepthCamera :> Camera {
        doc /* Optional DEPTH-01. No manufacturer model or detection accuracy is asserted. */
    }
}`,
    'MechatronicsOffer.sysml':`// SYNTHETIC OFFER M-01. Fixed source catalog. Parser NOT RUN.
package MechatronicsOffer {
    private import ScalarValues::*;
    private import RoverLibrary::*;
    part def OfferedChassis :> DriveBase {
        :>> wheelRadius_m = 0.05;
        :>> track_m = 0.28;
        doc /* CH-01 includes MOTOR-L, MOTOR-R, MOTOR-CTRL. Do not purchase/count twice. */
    }
    part def Battery96 :> Battery {
        :>> energy_Wh = 96.0;
        :>> length_mm = 120.0; :>> width_mm = 80.0; :>> height_mm = 45.0;
    }
    part def Battery160 :> Battery {
        :>> energy_Wh = 160.0;
        :>> length_mm = 140.0; :>> width_mm = 80.0; :>> height_mm = 45.0;
    }
    part def OriginalTray :> Tray {
        :>> insideLength_mm = 130.0; :>> insideWidth_mm = 90.0; :>> insideHeight_mm = 50.0;
    }
    part def ExpandedTray :> Tray {
        :>> insideLength_mm = 150.0; :>> insideWidth_mm = 90.0; :>> insideHeight_mm = 50.0;
        doc /* CNC candidate envelope only; strength, tolerances and manufacturing NOT CHECKED. */
    }
}`,
    'SoftwareOffer.sysml':`// SYNTHETIC OFFER S-01. Application proposals, not operational software.
package SoftwareOffer {
    private import RoverLibrary::*;
    part def LocalNavigation :> Navigation {
        :>> requiresInternet = false;
        doc /* Consumes Scan2D and declared IMU input; emits BodyVelocity.
               Controller behavior and physical stopping are not tested. */
    }
    part def LocalVision :> VisionProcessor;
    part def LocalRecorder :> Recorder;
}`
  });
  function sysml(c,adapter=true){return `// ROVER SINGLE-PAGE CASE · candidate ${c.id}
// NOT PARSER-VALIDATED. Template output from browser fixture, NOT an LLM result.
// Import the companion RoverLibrary and supplier files; review with a real tool.
package Rover_${c.id} {
    private import ScalarValues::*;
    private import RoverLibrary::*;
    private import PerceptionOffer::*;
    private import MechatronicsOffer::*;
    private import SoftwareOffer::*;

    // CMBSE-inspired referencing: aliases reference source definitions;
    // they are not unit converters or proof of semantic equivalence.
    alias LidarChoice for PerceptionOffer::OfferedLidar;
    alias ChassisChoice for MechatronicsOffer::OfferedChassis;

    requirement def MapNavigation {
        doc /* R-01: Navigate between specified stations on the supplied indoor map. */
    }
    requirement def LocalStop {
        doc /* R-02: Enter stopping behavior on the approved obstacle condition.
               Obstacle threshold and physical stopping performance need review. */
    }
    requirement def OfflineOperation {
        doc /* R-03: Basic navigation and stopping must not depend on Internet. */
    }
    requirement def RuntimeTarget {
        doc /* R-04: At least 2 h under the declared battery-side mean-load scenario. */
        attribute minimum_h : Real = 2.0;
    }
    requirement def WidthLimit {
        doc /* R-05: Overall width with accessories at most 350 mm. */
        attribute maximum_mm : Real = 350.0;
    }
    requirement def StateVisibility {
        doc /* R-06: Identify idle, navigating, stopped and fault modes. */
    }
${c.vision?`    requirement def OfflineVision {
        doc /* R-07 / CR-08: Add depth imaging, local processing and local recording;
               preserve R-03, R-04 and R-05. Model proposal, not executable driver. */
    }
`:''}
    part rover {
        part lidar : LidarChoice;
        part chassis : ChassisChoice;
        part navigation : LocalNavigation;
        part battery : ${c.battery.id==='BAT-96'?'Battery96':'Battery160'};
        part tray : ${c.tray.id==='TRAY-A'?'OriginalTray':'ExpandedTray'};
${adapter?`        part commandAdapter : DiffDriveAdapter {
            :>> wheelRadius_m = 0.05;
            :>> track_m = 0.28;
        }\n`:''}${c.vision?`        part camera : OfferedDepthCamera;
        part visionProcessor : LocalVision;
        part imageRecorder : LocalRecorder;
`:''}        connect lidar.output to navigation.scanIn;
        connect lidar.imu.output to navigation.imuIn;
${adapter?`        connect navigation.commandOut to commandAdapter.bodyIn;
        connect commandAdapter.wheelOut to chassis.input;`:`        // INVALID CANDIDATE INTERFACE: BodyVelocity is not WheelRPM.
        connect navigation.commandOut to chassis.input;`}
${c.vision?`        connect camera.frameOut to visionProcessor.frameIn;
        connect camera.frameOut to imageRecorder.frameIn;
        connect visionProcessor.resultOut to imageRecorder.observationIn;\n`:''}
        attribute baseLoadAtBattery_W : Real = ${c.basePower_W.toFixed(6)};
        attribute addedVisionLoadAtBattery_W : Real = ${c.visionIncrement_W.toFixed(6)};
        attribute meanLoadAtBattery_W : Real = baseLoadAtBattery_W + addedVisionLoadAtBattery_W;
        attribute usableEnergyFraction : Real = ${c.usableFraction};
        attribute estimatedRuntime_h : Real = battery.energy_Wh * usableEnergyFraction / meanLoadAtBattery_W;
        attribute overallWidth_mm : Real = ${c.tray.installedRoverWidth_mm.toFixed(1)};
        // Scalar suffix units are a bounded teaching convention, not unit-library validation.
        // Electrical rails, harness, mass/inertia and calibrated mounting are not modeled fully.
    }

    requirement mapNavigation : MapNavigation;
    requirement localStop : LocalStop;
    requirement offlineOperation : OfflineOperation;
    requirement runtimeRequirement : RuntimeTarget;
    requirement widthRequirement : WidthLimit;
    requirement stateVisibility : StateVisibility;
${c.vision?'    requirement localVisionRequirement : OfflineVision;\n':''}
    // Separate candidate constraints from requirement assertions and test evidence.
    constraint estimatedRuntimeCheck {
        rover.estimatedRuntime_h >= runtimeRequirement.minimum_h
    }
    constraint overallWidthCheck {
        rover.overallWidth_mm <= widthRequirement.maximum_mm
    }
    constraint fixedOrientationBatteryFit {
        rover.battery.length_mm <= rover.tray.insideLength_mm and
        rover.battery.width_mm <= rover.tray.insideWidth_mm and
        rover.battery.height_mm <= rover.tray.insideHeight_mm
    }

    action def FollowRoute;
    action def IssueStopRequest;
    action def RecordState;
${c.vision?'    action def CaptureFrame;\n    action def ProcessLocally;\n    action def StoreLocally;\n':''}
    action operationalWorkflow {
        first start;
        then action followRoute : FollowRoute;
        then action recordState : RecordState;
        then done;
        doc /* STOP/FAULT branching is an obligation for the executable controller.
               The authored state catalogue below is not a completed transition implementation. */
    }
${c.vision?`    action localVisionWorkflow {
        first start;
        then action capture : CaptureFrame;
        then action process : ProcessLocally;
        then action save : StoreLocally;
        then done;
        doc /* R-07: local behavior proposal. No image recognition, disk I/O or motion runs here. */
    }
`:''}    state def OperationalStates {
        state idle;
        state navigating;
        state stopped;
        state fault;
    }
    // Verification intentions only. No successful verification is asserted in this draft.
    doc /* Intended evidence: parsed-model diagnostics, requirement review, numerical
           runtime/fit checks, controlled stopping and independent physical testing.
           Browser arithmetic is NOT execution of this SysML file. */
}
`;}
  function model(c,adapter=true){const path=s=>`Rover_${c.id}::${s}`;const node=(id,label,kind,data={},tags=[])=>({id,label,kind,path:path(id),file:`Rover_${c.id}.sysml`,revision:c.id,data,tags});const nodes=[
      node('rover','小车系统','part',{},['system']),node('rover.battery','电池','part',{selection:c.battery.id,energy_Wh:c.battery.Wh,size_mm:c.battery.size_mm},['电池','battery','续航','能源']),node('rover.tray','CNC电池托盘','part',{selection:c.tray.id,inside_mm:c.tray.inside_mm},['托盘','安装','尺寸','CNC']),node('rover.lidar','扫描雷达','part',{physicalId:'LID-01',output:'Scan2D'},['雷达','感知']),node('rover.lidar.imu','内置IMU','part',{physicalId:'IMU-L1',includedIn:'LID-01',independentFromLidar:false},['IMU','imu','内置','独立']),node('rover.navigation','本地导航','part',{requiresInternet:false,input:'Scan2D + ImuSample',output:'BodyVelocity'},['导航','离线','软件']),node('rover.chassis','差速底盘','part',{physicalId:'CH-01',includes:['MOTOR-L','MOTOR-R','MOTOR-CTRL'],input:'WheelRPM',wheelRadius_m:0.05,track_m:0.28},['底盘','电机','命令']),node('rover.chassis.motorLeft','左电机','part',{physicalId:'MOTOR-L',includedIn:'CH-01'},['电机','包含']),node('rover.chassis.motorRight','右电机','part',{physicalId:'MOTOR-R',includedIn:'CH-01'},['电机','包含']),node('rover.meanLoadAtBattery_W','电池侧平均功耗','attribute',{base_W:32,added_W:c.visionIncrement_W,total_W:c.power_W},['功耗','负载','相机','power']),node('rover.estimatedRuntime_h','续航分析','analysis',{value_h:checks(c,adapter).runtime_h,formula:'energy_Wh × 0.8 / meanLoadAtBattery_W'},['续航','runtime','电池','功耗']),node('runtimeRequirement','R-04续航要求','requirement',{id:'R-04',minimum_h:2},['续航','要求']),node('widthRequirement','R-05宽度要求','requirement',{id:'R-05',maximum_mm:350},['宽度','安装','要求']),node('offlineOperation','R-03离线要求','requirement',{id:'R-03',requiresInternet:false},['离线','要求']),node('operationalWorkflow','导航和状态记录职责','action',{states:['idle','navigating','stopped','fault'],runtimeStatus:'NOT_IMPLEMENTED'},['行为','导航','故障'])
    ];if(adapter)nodes.push(node('rover.commandAdapter','速度→轮速适配','part',{type:'DiffDriveAdapter',wheelRadius_m:.05,track_m:.28},['接口','命令','轮速','适配']));if(c.vision)nodes.push(node('rover.camera','深度相机','part',{physicalId:'DEPTH-01',output:'RGBDFrame'},['深度','相机','图像']),node('rover.visionProcessor','板载视觉处理','part',{requiresInternet:false},['相机','处理','离线']),node('rover.imageRecorder','本地图像记录','part',{requiresInternet:false},['相机','记录','离线']),node('localVisionRequirement','R-07新增视觉要求','requirement',{id:'R-07',source:'CR-08'},['相机','新增','要求']),node('localVisionWorkflow','采集→本地处理→记录','action',{runtimeStatus:'NOT_IMPLEMENTED'},['相机','行为','离线']));
    let edges=[['rover','rover.battery','contains'],['rover','rover.tray','contains'],['rover','rover.lidar','contains'],['rover.lidar','rover.lidar.imu','includes'],['rover','rover.navigation','contains'],['rover','rover.chassis','contains'],['rover.chassis','rover.chassis.motorLeft','includes'],['rover.chassis','rover.chassis.motorRight','includes'],['rover.lidar','rover.navigation','Scan2D'],['rover.lidar.imu','rover.navigation','ImuSample'],['rover.battery','rover.tray','fitsInto'],['rover.battery','rover.estimatedRuntime_h','parameter'],['rover.meanLoadAtBattery_W','rover.estimatedRuntime_h','parameter'],['runtimeRequirement','rover.estimatedRuntime_h','constrains'],['widthRequirement','rover.tray','constrains'],['offlineOperation','rover.navigation','constrains'],['rover.navigation','operationalWorkflow','allocated'],['rover.battery','rover.meanLoadAtBattery_W','supplies_aggregate']];if(adapter)edges.push(['rover.navigation','rover.commandAdapter','BodyVelocity'],['rover.commandAdapter','rover.chassis','WheelRPM'],['rover','rover.commandAdapter','contains']);else edges.push(['rover.navigation','rover.chassis','INCOMPATIBLE_DIRECT_LINK']);if(c.vision)edges.push(['rover','rover.camera','contains'],['rover','rover.visionProcessor','contains'],['rover','rover.imageRecorder','contains'],['rover.camera','rover.visionProcessor','RGBDFrame'],['rover.camera','rover.imageRecorder','RGBDFrame'],['rover.visionProcessor','rover.imageRecorder','LocalObservation'],['rover.camera','rover.meanLoadAtBattery_W','included_in_increment'],['rover.visionProcessor','rover.meanLoadAtBattery_W','included_in_increment'],['rover.imageRecorder','rover.meanLoadAtBattery_W','included_in_increment'],['localVisionRequirement','rover.camera','allocated'],['localVisionRequirement','localVisionWorkflow','constrains'],['rover.visionProcessor','localVisionWorkflow','allocated']);
    return {schema:'rover.teaching.graph/1',revision:c.id,source_kind:'AUTHORED_BROWSER_FIXTURE_NOT_SYSML_AST',config:clone(c),nodes,edges:edges.map(([from,to,type])=>({from,to,type})),fingerprint:checksum({config:c,adapter}),omitted:['full electrical architecture','actuator dynamics','safety validation','mass/inertia','exact CAD'],parser:'NOT_RUN'};}
  function alignment(adapter=true){return [
    {id:'M-01',source:'PerceptionOffer::OfferedLidar.output',target:'SoftwareOffer::LocalNavigation.scanIn',sourceType:'Scan2D',targetType:'Scan2D',proposedTag:'FullyMatched',decision:'Fixture definitions agree; references preserved. Not real driver compatibility.',sourceUnchanged:true},
    {id:'M-02',source:'SoftwareOffer::LocalNavigation.commandOut',target:'MechatronicsOffer::OfferedChassis.input',sourceType:'BodyVelocity [m/s, rad/s]',targetType:'WheelRPM [rpm]',proposedTag:'RequireModification',decision:adapter?'Add DiffDriveAdapter and two typed connections; no alias-only conversion.':'BLOCK: no adapter selected',sourceUnchanged:true},
    {id:'M-03',source:'PerceptionOffer::OfferedLidar.imu',target:'SoftwareOffer::LocalNavigation.imuIn',sourceType:'IMU-L1 physical source',targetType:'ImuSample',proposedTag:'FullyMatched',decision:'Reuse the one included IMU under declared fixture assumptions; do not claim independent redundancy.',sourceUnchanged:true},
    {id:'M-04',source:'MechatronicsOffer::OfferedChassis',target:'integrated parts/procurement view',sourceType:'assembly includes MOTOR-L/MOTOR-R',targetType:'physical identity registry',proposedTag:'RequireComplement',decision:'Retain motor child nodes but add inclusion metadata; no second purchased motor set.',sourceUnchanged:true}
  ];}
  function tokenize(q){const terms=['Jetson','Orin','树莓派','Raspberry','Pi5','主控','计算','D435i','MID-360S','Mid360S','USB','PointCloud2','CUDA','供电','载板','ICM40609','电池','battery','续航','runtime','功耗','负载','power','相机','深度','图像','托盘','安装','尺寸','CNC','宽度','雷达','IMU','imu','内置','独立','底盘','电机','导航','离线','软件','行为','命令','轮速','接口','适配','R-04','R-05','R-03','R-07'];return terms.filter(t=>q.toLowerCase().includes(t.toLowerCase()));}
  function retrieve(graph,query){if(typeof query!=='string'||query.length>3000)throw Error('Invalid query');const terms=tokenize(query);const ranked=graph.nodes.map(n=>{const t=[n.label,n.path,...n.tags,JSON.stringify(n.data)].join(' ').toLowerCase();const hits=terms.filter(x=>t.includes(x.toLowerCase()));return {node:n,score:hits.length,hits};}).filter(x=>x.score>0).sort((a,b)=>b.score-a.score||a.node.id.localeCompare(b.node.id));const seeds=ranked.slice(0,4);const ids=new Set(seeds.map(x=>x.node.id));for(const e of graph.edges){if(seeds.some(x=>x.node.id===e.from))ids.add(e.to);if(seeds.some(x=>x.node.id===e.to))ids.add(e.from);}const retrieved=graph.nodes.filter(n=>ids.has(n.id)).map(n=>({...clone(n),retrievalRole:seeds.some(x=>x.node.id===n.id)?'keyword_seed':'one_hop_neighbor',keywordHits:ranked.find(r=>r.node.id===n.id)?.hits||[]}));return {query,revision:graph.revision,sourceFingerprint:graph.fingerprint,method:'LOCAL_KEYWORD_PLUS_ONE_HOP_NOT_MINILM_OR_FAISS',terms,seeds:seeds.map(x=>({id:x.node.id,score:x.score,hits:x.hits})),elements:retrieved,edges:graph.edges.filter(e=>ids.has(e.from)&&ids.has(e.to)),status:retrieved.length?'CONTEXT_FOUND':'NO_CONTEXT',llmAnswer:'NOT_CALLED',completeness:'Not guaranteed; use explicit model queries for complete lists'};}
  function diff(a,b){const am=new Map(a.nodes.map(n=>[n.id,n])),bm=new Map(b.nodes.map(n=>[n.id,n]));return {from:a.revision,to:b.revision,added:b.nodes.filter(n=>!am.has(n.id)).map(n=>({id:n.id,label:n.label})),removed:a.nodes.filter(n=>!bm.has(n.id)).map(n=>({id:n.id,label:n.label})),changed:b.nodes.filter(n=>am.has(n.id)&&JSON.stringify(am.get(n.id).data)!==JSON.stringify(n.data)).map(n=>({id:n.id,label:n.label,before:am.get(n.id).data,after:n.data})),newConnections:b.edges.filter(e=>!a.edges.some(x=>JSON.stringify(x)===JSON.stringify(e)))};}
  return {clone,freeze,PAPER_SOURCES,REQUIREMENTS,CHANGE,CATALOG,config,checks,numericPass,wheelRpm,checksum,supplierCodes,sysml,model,alignment,retrieve,diff};
})();
if(typeof module!=='undefined')module.exports=RoverCore;
