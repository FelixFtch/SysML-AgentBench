"""Local browser regression; no device, LLM, or SysML compiler is exercised.
Run: xvfb-run -a python tests/test_browser.py (requires Playwright + Chromium).
"""
from pathlib import Path
import json, time, traceback, os
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'tests'; SHOTS=ROOT/'screenshots'; OUTPUT.mkdir(exist_ok=True);SHOTS.mkdir(exist_ok=True)
rows=[]; errors=[]
def add(title,ok,detail=None):
 rows.append({'id':f'B{len(rows)+1:02}','title':title,'pass':bool(ok),'detail':detail})
 if not ok: print('FAIL',title,detail)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=os.environ.get('CHROMIUM','/usr/bin/chromium'),headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
 page=b.new_page(viewport={'width':1440,'height':1080},device_scale_factor=1,accept_downloads=True)
 page.on('pageerror',lambda e:errors.append(str(e)))
 def ev(s):return page.evaluate(s)
 def test(title,s):
  try:add(title,ev(s))
  except Exception as e:add(title,False,str(e))
 def shot(name,selector=None):
  page.wait_for_timeout(120)
  if selector: page.locator(selector).screenshot(path=str(SHOTS/name),timeout=10000)
  else: page.screenshot(path=str(SHOTS/name))
 def fresh():
  page.set_content((ROOT/'ROVER_Real_Hardware_Studio.html').read_text(),wait_until='load')
  page.wait_for_timeout(150)
 try:
  fresh()
  renderer=ev('ROVER_VISUAL.renderer()');(OUTPUT/'renderer.json').write_text(json.dumps(renderer,ensure_ascii=False,indent=2))
  test('Native WebGL context and depth buffers created','roverViewer.inspect().renderer==="WEBGL" && roverViewer.inspect().glError===0 && roverViewer.inspect().pickFramebufferComplete')
  test('Initial compute NX16 and source catalog available','HW.computeId==="nx16"&&HardwareData.sources.length===11')
  rules=ev('ROVER_HARDWARE.tests()');(OUTPUT/'hardware_rules.json').write_text(json.dumps(rules,ensure_ascii=False,indent=2))
  add('All 28 deterministic hardware rules',len(rules)==28 and all(x['pass'] for x in rules))
  test('Current source hashes intact','verifySources()')
  test('Runtime formula is dynamic, not old32W','nodeFacts(6).includes("32.78")&&!nodeFacts(6).includes("2.40")')
  test('Camera dimensions are90x25x25mm and mode maxima separated','HardwareData.camera.body_mm.join()==="90,25,25"&&HardwareData.camera.depthMaxFps===90&&HardwareData.camera.rgbShutter==="rolling"')
  test('Official S model cutoff is not guaranteed40m range','HardwareData.lidar.rangeTypical_m===40&&HardwareData.lidar.cutoff_m===100')
  test('All primary sources use HTTPS','HardwareData.sources.every(s=>s.url.startsWith("https://"))')
  test('Compute facts included in graph and SysML','C.model(cA()).nodes.find(x=>x.id==="rover.compute").data.ram_GB===16&&C.sysml(cA()).includes("part compute : JetsonAssembly")')
  test('Model numeric text retains computed budget precision','C.sysml(cA()).includes(cA().basePower_W.toFixed(6))')
  test('No direct LiDAR-to-navigation edge','!C.model(cA()).edges.some(e=>e.from==="rover.lidar"&&e.to==="rover.navigation")')
  test('Public IMU ownership distinct from calibration proof','C.model(cB()).nodes.find(x=>x.id==="rover.camera.imu").data.statisticalIndependence==="NOT_ASSESSED"')
  shot('01_hardware_overview.png','#hardware-lab')
  # Configuration controls are actual DOM change events.
  page.select_option('#hardware-compute','pi5_8')
  test('Select Pi8 updates core/geometry/selected hardware','HW.computeId==="pi5_8"&&C.model(cA()).nodes.find(x=>x.id==="rover.compute").data.ram_GB===8&&!roverViewer.inspect().parts.includes("rover.compute.module")')
  page.select_option('#hardware-compute','pi5_16')
  test('Select Pi16 updates type and RAM','C.sysml(cA()).includes("RaspberryPi5_16")&&C.model(cA()).nodes.find(x=>x.id==="rover.compute").data.ram_GB===16')
  ev("setView('B0');choosePart('rover.compute');setDiagramTab('ports')")
  test('Pi B0 is not hard-coded to fail','C.numericPass(C.checks(cB("B0"),true))')
  shot('03_pi16_usb_model.png','#visual-lab')
  page.select_option('#hw-piSupply','3a')
  test('Ordinary3A PSU fails B peripheral allowance','C.checks(cB("B0")).checks.find(x=>x.id==="K-PI-USB").status==="FAIL"')
  test('A without camera can still satisfy .6A allowance','C.checks(cA()).checks.find(x=>x.id==="K-PI-USB").status==="PASS"')
  page.select_option('#hw-piSupply','5a')
  test('Recognized5A restores model-side peripheral budget','C.checks(cB()).checks.find(x=>x.id==="K-PI-USB").status==="PASS"')
  page.select_option('#hw-visionRuntime','cuda_only')
  test('Pi CUDA-only is rejected','!C.numericPass(C.checks(cB()))')
  ev("setView('B2')");shot('04_pi_cuda_conflict.png','#hardware-content .hw-status-grid')
  page.select_option('#hw-visionRuntime','portable')
  page.select_option('#hw-usbMode','usb2')
  test('USB2 conflicts with selected USB3 profile requirement','C.checks(cB()).checks.find(x=>x.id==="K-USB-LINK").status==="FAIL"')
  page.select_option('#hw-usbMode','usb3')
  page.select_option('#hw-pointcloudAdapter','false')
  test('Missing projection prevents A approval','!C.numericPass(C.checks(cA()))')
  ev('runUntil(11)')
  test('Workflow stops atA and does not approve invalid configuration','S.cursor===6&&!S.aApproval&&!canApproveA()')
  page.select_option('#hw-pointcloudAdapter','true')
  test('Hardwarechange resets run and index','S.cursor===0&&S.index===null&&S.aChecks===null')
  ev("changeHardware('lidarSupply_V','28')")
  test('28V outside LiDAR limits is rejected','C.checks(cA()).checks.find(x=>x.id==="K-LIDAR-V").status==="FAIL"')
  ev("changeHardware('lidarSupply_V','12')")
  old=ev('HW.computeA_W');ev("changeHardware('computeA_W','NaN')")
  add('Nonfinite inputs rejected without corrupting state',ev('HW.computeA_W')==old)
  ev("changeHardware('computeA_W','90')")
  add('Out-of-range input rejected',ev('HW.computeA_W')==old)
  # defaultNX end-to-end real approvals and export
  page.select_option('#hardware-compute','nx16')
  ev('runUntil(11)')
  test('PrepareB pauses at unapproved A','S.cursor===6&&S.aChecks!==null&&!S.aApproval')
  page.check('#approve-a-check');page.click('#approve-a-btn')
  test('ExplicitAapproval recorded','!!S.aApproval&&S.aApproval.fingerprint===S.aModel.fingerprint')
  ev('runUntil(11)')
  test('B checks executed, A index preserved','S.cursor===11&&S.index.revision==="A"&&evidenceReady()')
  ev("chooseForReview('B1')")
  test('B1cannot pass despite capacity','!canApproveB()&&S.bChecks.results.B1.checks[1].status==="FAIL"')
  ev("chooseForReview('B2')")
  page.check('#approve-b-req');page.check('#approve-b-limits')
  ev('render()')
  test('Re-render preserves explicit acknowledgements','document.getElementById("approve-b-req").checked&&document.getElementById("approve-b-limits").checked')
  page.click('#approve-b-btn')
  test('ApprovedB creates only teaching release atstep12','S.cursor===12&&S.bApproval.candidate==="B2"&&S.bApproval.kind.includes("TEACHING")')
  ev('rebuildIndex()')
  test('Index points to approvedB fingerprint','S.index.revision==="B2"&&S.index.fingerprint===S.bApproval.fingerprint')
  test('New model retrieves selected compute with sources','C.retrieve(S.index,"主控 Jetson USB").elements.some(n=>n.id==="rover.compute"&&n.data.sourceRefs.includes("HW-NX"))')
  test('Original supplier models stay unchanged','verifySources()')
  ev("setView('B2');setExplode(18);choosePart('rover.compute');setDiagramTab('ports')")
  shot('02_jetson_B2_studio.png','#visual-lab')
  for name,value in ev('Object.fromEntries(ARTIFACTS.map(x=>[x[1],artifactValue(x[0])]))').items():
   target=ROOT/'examples'/'NX_B2';target.mkdir(parents=True,exist_ok=True);(target/name).write_text(value,encoding='utf-8')
  test('Report has actual hardware and dynamic budgets','reportHtml().includes("Jetson Orin NX 16GB")&&!reportHtml().includes("基线电池侧平均32W")')
  test('Hardwareevidence marks unknown carrier not runtimevalidated','evidence().hardware.selection.jetsonCarrier==="NOT_SELECTED"')
  for id in ['hardware','planning','hardwareModel','modelA','modelB','report']:
   with page.expect_download(timeout=10000) as di: ev(f"downloadArtifact('{id}')")
   d=di.value;dest=OUTPUT/'download_smoke'/d.suggested_filename;dest.parent.mkdir(exist_ok=True);d.save_as(dest)
   add('Download '+id,dest.exists() and dest.stat().st_size>50)
  # hardwarechanges invalidate evidence, not append false approval
  page.select_option('#hardware-compute','pi5_16')
  test('Changinghostinvalidates models/approval/index','S.cursor===0&&!S.aApproval&&!S.bApproval&&!S.index&&Object.keys(S.bModels).length===0')
  test('Invalidation log preserves which prior evidence became stale','S.logs.some(l=>l.type==="HARDWARE_INVALIDATION"&&l.payload.oldEvidence.approvalB)')
  ev('runUntil(11)');page.check('#approve-a-check');page.click('#approve-a-btn');ev('runUntil(11)');ev("chooseForReview('B0')")
  test('Pi B0 is an allowed alternative','canApproveB()')
  page.check('#approve-b-req');page.check('#approve-b-limits');page.click('#approve-b-btn');ev('rebuildIndex()')
  test('B0approved, index not forcedB2','S.bApproval.candidate==="B0"&&S.index.revision==="B0"')
  # all teaching and diagram tabs remain interactive
  for step in range(7):
   ev(f'lessonSet({step})')
   test(f'Teaching lesson{step+1} renders',f'LP.step==={step}&&document.getElementById("lesson-content").innerText.length>10' if ev('!!document.getElementById("lesson-content")') else f'LP.step==={step}')
  for tab in ['structure','ports','behavior','code']:
   ev(f"setView('B2');setDiagramTab('{tab}')")
   test('Diagram tab '+tab,f'V.tab==="{tab}"&&document.getElementById("model-stage").innerHTML.length>100')
  for part in ['rover.compute','rover.camera','rover.lidar','rover.livoxDriver','rover.camera.imu']:
   ev(f"choosePart('{part}')")
   test('Part-link '+part,f'V.part==="{part}"&&document.getElementById("part-detail").innerText.length>60')
  ev("choosePart('rover.lidar');termSelect('port')")
  test('LiDARportteaching uses actual packets, not oldScanPort','document.getElementById("model-terms").innerText.includes("LivoxPacketPort")')
  ev("choosePart('rover.camera');termSelect('port')")
  test('CameraUSBteaching points to actual source','document.getElementById("model-terms").innerText.includes("USBDevicePort")')
  # rotations nativeWebGL with different geometry; changingcamera doesn't alter design
  rotations=[]
  for host in ['nx16','pi5_8','pi5_16']:
   ev(f"hardwareChoice('{host}')")
   for rev in ['A','B1','B2']:
    for proj in ['orthographic','perspective']:
     for expl in [0,1]:
      ev(f"setView('{rev}');roverViewer.setProjection('{proj}');roverViewer.setExplode({expl});roverViewer.fitScene(false)")
      for ang in [0,1.57,3.14,4.71]:
       d=ev(f"(()=>{{roverViewer.azimuth={ang};roverViewer.draw();const d=roverViewer.inspect();return {{host:HW.computeId,revision:V.view,angle:{ang},explode:{expl},projection:'{proj}',error:d.glError,draws:d.lastDraw.drawCalls,near:d.camera.near,far:d.camera.far}}}})()")
       rotations.append(d)
  (OUTPUT/'rotation_cases.json').write_text(json.dumps(rotations,ensure_ascii=False,indent=2))
  add('144WebGLrotation cases keep nonempty buffers/no GL errors',len(rotations)==144 and all(x['error']==0 and x['draws']>10 and x['far']>x['near']>0 for x in rotations))
  ev('restoreRoverView()')
  ev("choosePart('rover.livoxDriver');setIsolate(true)")
  test('Softwareisolationrevealsitscomputinghostnotemptyview','roverViewer.meshes.some(m=>m.id.startsWith(\"rover.compute\")&&roverViewer.opacity(m)>.99)')
  ev('restoreRoverView()')
  test('Restoreviewclearsisolation','!roverViewer.isolate&&!roverViewer.transparent&&roverViewer.focusGroup==="all"')
  # fresh renderer context loss test and dual fallback
  ev('roverViewer.setRenderingMode("software")')
  test('CPU fallback remains available','roverViewer.inspect().renderer!=="WEBGL"')
  ev('roverViewer.setRenderingMode("auto")')
  test('Auto restoresWebGL','roverViewer.inspect().renderer==="WEBGL"')
  # responsiveness at all specified widths
  for w,h in [(390,844),(768,1024),(1440,1000)]:
   page.set_viewport_size({'width':w,'height':h});page.wait_for_timeout(150)
   test(f'No body horizontaloverflow {w}px','document.documentElement.scrollWidth<=innerWidth+2')
   page.locator('#hardware-lab').scroll_into_view_if_needed();shot(f'width_{w}_hardware.png')
   ev("setView('B2');setDiagramTab('ports');choosePart('rover.camera')")
   page.locator('#visual-lab').scroll_into_view_if_needed();shot(f'width_{w}_studio.png')
  add('NoJavaScript runtime errors',not errors,errors)
 except Exception as e:
  add('Unexpected harness interruption',False,traceback.format_exc());print(traceback.format_exc())
 finally:
  report={'time':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'environment':'Chromium with ANGLE SwiftShader (WebGL API path, not physicalRTX4090)','summary':{'passed':sum(x['pass'] for x in rows),'total':len(rows)},'checks':rows,'js_errors':errors,'limitations':['No real LLM calls','No SysML parser executed','No device/driver/USB measurements','Model and geometry share authored data; not parser-derived CAD','All operating loads are editable planning assumptions']}
  (OUTPUT/'browser_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report['summary']));b.close()
