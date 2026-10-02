'use strict';
/* Research explanation layer. It never approves a candidate, invokes an LLM,
   pretends to parse SysML, or changes supplier files. Excerpts are literal selections
   from the same exportable source, not separate LLM-written explanations. */
const LESSONS=[
 {id:'author',title:'要求 → 供应商模型',method:'NPS · 建立',paper:'nps',stage:3,view:'A',part:'rover.lidar',tab:'structure',file:'3 × Offer.sysml',page:'NPS 幻灯片 8 / 10 / 13'},
 {id:'align',title:'不同接口 → 集成',method:'CMBSE · 软对齐',paper:'cmb',stage:4,view:'A',part:'rover.commandAdapter',tab:'ports',file:'mappings → Rover_A',page:'CMBSE PDF 5–7页 · §IV / Fig.1'},
 {id:'model',title:'设计 → 独立检查',method:'SYSML + 我们的工具',paper:'ours',stage:6,view:'A',part:'rover.battery',tab:'structure',file:'model → check report',page:'NPS 图是模型视图；独立工具是本项目补强'},
 {id:'retrieve',title:'问题 → 相关模型',method:'GRAG · 检索',paper:'grag',stage:8,view:'A',part:'rover.battery',tab:'structure',file:'A → graph → context',page:'GRAG PDF 4页 · §IV / Fig.3'},
 {id:'change',title:'新增要求 → 部件',method:'NPS · 修改',paper:'nps',stage:9,view:'B0',part:'rover.camera',tab:'ports',file:'CR-08 → Rover_B0',page:'NPS 幻灯片 14–15 · 增加部件 / 要求'},
 {id:'iterate',title:'冲突 → 再设计',method:'工具反馈 + 再集成',paper:'cmb',stage:11,view:'B1',part:'rover.tray',tab:'ports',file:'B0 → B1 → B2',page:'CMBSE 的迭代思想；数值规则由我们实现'},
 {id:'review',title:'批准 → 新版知识',method:'人工 + 索引更新',paper:'ours',stage:12,view:'B2',part:'rover.camera',tab:'structure',file:'approved B → index B',page:'项目工作流扩展，不是论文已部署的产品'}
];
const LCOL={nps:['#8963ae','#f4edfa'],cmb:['#1e8584','#eaf7f4'],grag:['#b18a42','#fbf3e5'],ours:['#4d758f','#edf4f8']};
let LP={step:0,term:'usage',query:'电池 续航 功耗 托盘',result:null,resultSource:null,manual:false};
function lessonSet(i){if(i<0||i>=LESSONS.length)return;LP.step=i;LP.manual=true;const d=LESSONS[i];stop();V.follow=false;V.view=d.view;V.part=d.part;V.tab=d.tab;V.zoom=1;S.selected=d.stage;S.paper=d.paper;
 if(!viewGraph().nodes.some(n=>n.id===V.part))V.part='rover.battery';
 renderBoard();renderLegend();renderInspector();renderLab();renderGuide();
 if(i===3&&!LP.result)lessonRetrieve(false);
}
function lessonBack(){lessonSet(Math.max(0,LP.step-1));}
function lessonNext(){lessonSet(Math.min(LESSONS.length-1,LP.step+1));}
function lessonFollow(){LP.manual=false;V.follow=true;followStage();render();}
function lessonStageFromMain(){if(!V.follow)return;LP.manual=false;const stage=S.selected;LP.step=stage<=3?0:stage<=5?1:stage===6?2:stage<=8?3:stage===9?4:stage<=11?5:6;}
function literalExcerpt(file,text,terms,limit=9){const lines=text.split('\n'),seen=new Set(),selected=[];for(const word of terms){const idx=lines.findIndex(x=>x.includes(word));if(idx>=0){for(let j=idx;j<=Math.min(lines.length-1,idx+1);j++)if(!seen.has(j)){seen.add(j);selected.push({n:j+1,text:lines[j]});}}}selected.sort((a,b)=>a.n-b.n);return `<div class="lesson-source">${esc(file)} · 当前可导出草稿的实际行</div><pre class="lesson-code">${selected.slice(0,limit).map(x=>`${String(x.n).padStart(3)}  ${esc(x.text)}`).join('\n')||'此版本没有这些元素；不能伪造代码。'}</pre>`;}
function lessonBox(label,body,tag=''){return `<section class="lesson-box"><header>${label}<small>${tag}</small></header>${body}</section>`;}
function inside(s){return `<div class="inside">${s}</div>`;}
function chips(arr,cls=''){return arr.map(t=>`<span class="lesson-atom ${cls}">${esc(t)}</span>`).join('');}
function arrowMini(a,b,mid,ok=true){return `<svg class="lesson-mini-svg" viewBox="0 0 320 145" role="img" aria-label="接口关系示意"><defs><marker id="ln-arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L10 5L0 10" fill="#5b938e"/></marker></defs><rect x="8" y="6" width="144" height="35" rx="5" fill="#f0eef8" stroke="#c3b4d6"/><text x="80" y="28" text-anchor="middle" fill="#6d528b" font-size="12">${esc(a)}</text><rect x="169" y="6" width="143" height="35" rx="5" fill="#eef5f7" stroke="#b8d0d9"/><text x="240" y="28" text-anchor="middle" fill="#496d80" font-size="12">${esc(b)}</text><path d="M80 41V66H240V41" fill="none" stroke="#cd8d79" stroke-dasharray="4 3"/><text x="160" y="62" text-anchor="middle" fill="#bd715b" font-size="10">不是同一种命令</text><path d="M80 70V90H108 M211 109H240V70" stroke="#5b938e" fill="none" marker-end="url(#ln-arr)"/><rect x="29" y="91" width="262" height="39" rx="6" fill="${ok?'#eaf5f1':'#fcf0e9'}" stroke="${ok?'#86b6a2':'#d79781'}"/><text x="160" y="115" text-anchor="middle" fill="#3c7165" font-size="12">${esc(mid)}</text></svg>`;}
function fitSketch(c){const bl=c.battery.size_mm[0],tl=c.tray.inside_mm[0],scale=1.65,origin=28,max=Math.max(bl,tl),w=max*scale;return `<svg class="lesson-mini-svg" viewBox="0 0 340 132" aria-label="电池与托盘标称长度比较"><text x="24" y="17" fill="#5d7d8a" font-size="10">相同起点与固定方向；不含公差 / 插头</text><rect x="${origin}" y="34" width="${tl*scale}" height="28" rx="3" fill="#e4f0f5" stroke="#7ea5b8"/><text x="${origin+tl*scale/2}" y="52" text-anchor="middle" fill="#47788f" font-size="11">仓内 ${tl} mm</text><rect x="${origin}" y="76" width="${bl*scale}" height="26" rx="3" fill="#f4e7bf" stroke="#bd9a4e"/><text x="${origin+bl*scale/2}" y="94" text-anchor="middle" fill="#8a6c2c" font-size="11">电池 ${bl} mm</text><path d="M${origin+tl*scale} 26V110" stroke="${bl>tl?'#c1715a':'#8bacbb'}" stroke-dasharray="4 3"/><text x="24" y="124" fill="${bl>tl?'#b76951':'#497f71'}" font-size="11">${bl>tl?'超出 '+(bl-tl)+' mm → 不可装入':'剩余 '+(tl-bl)+' mm → 此项标称检查通过'}</text></svg>`;}
function lessonData(){const s=LP.step,d=LESSONS[s],g=viewGraph(),src=C.sysml(g.config,S.adapter);let a,b,c,origin,extension,boundary;
 if(s===0){
  a=inside(`<p><b>你给要求，不是给一张成品图片。</b></p>${chips(['R-01 室内导航','R-03 离线处理','R-04 ≥ 2小时','R-05 ≤ 350mm'])}<p style="margin-top:9px">给每个角色附：<code>model_author.md</code>、供应商资料，以及少量经过审查的写法示例。</p>`);
  b=inside(`<p><b>同一种 NPS 建模方法，服务三家模拟供应商。</b></p>${chips(['感知 → PerceptionOffer','机电 → MechatronicsOffer','软件 → SoftwareOffer'])}<p style="margin-top:10px">角色是任务分工，不是三篇论文分别扮演一家供应商。每家都交付部件、接口和未知项。</p>`);
  c=literalExcerpt('PerceptionOffer.sysml',C.supplierCodes['PerceptionOffer.sysml'],['part def OfferedLidar','part def OfferedDepthCamera'])+inside('<b>输出：实际模型草稿。</b> 图是这个设计的一种视图；不是重新让图像模型画一辆车。');
  origin='NPS SSE-SM：建模指令、领域知识、SysML规范／记法、模板及Se-lib.py；自行车实验按文字建立和修改模型。';extension='把相同方法用于三个小车子系统；角色组织、目录与软件工程流程是本项目设计。';boundary='本页输出来自模板，不是GPT调用；这些草稿尚未经过真实SysML工具检查。';
 }else if(s===1){
  a=literalExcerpt('RoverLibrary.sysml',C.supplierCodes['RoverLibrary.sysml'],['port commandOut : BodyCommandPort','port input : ~WheelCommandPort'])+inside(`<p>软件方案给 <code>BodyVelocity</code>，底盘要求 <code>WheelRPM</code>。原文件的含义保留，不能改个名字就说兼容。</p>`);
  b=inside(arrowMini('BodyVelocity','WheelRPM','DiffDriveAdapter · 明确适配职责',S.adapter)+`<div class="lesson-controls"><button class="small-tool" onclick="lessonToggleAdapter()">${S.adapter?'试：移除适配并重检':'恢复适配职责'}</button></div><small>此按钮修改主线配置，会使 A/B 审批与索引失效。</small>`);
  c=literalExcerpt('Rover_'+g.revision+'.sysml',src,['part commandAdapter','connect navigation.commandOut','connect commandAdapter.wheelOut'])+inside(`<b>${S.adapter?'已表示适配职责':'当前直接连接存在类型冲突'}</b><br><code>mappings.json</code>记录对应与理由；<code>Rover_A.sysml</code>写新增关系。两个源文件不被覆盖。`);
  origin='CMBSE §IV：提取元素→提出匹配→审查→附加集成包；import / alias / metadata 保留源模型独立性。';extension='本例的速度转换职责和理想轮速公式是我们的领域规则，不是论文自动提供的驱动。';boundary='alias不是转换程序；LLM自检不是独立解析；供应商匹配建议不是接口已在硬件上运行。';
 }else if(s===2){const r=C.checks(cA(),S.adapter);
  a=literalExcerpt('Rover_A.sysml',C.sysml(cA(),S.adapter),['part battery','attribute meanLoadAtBattery_W','attribute estimatedRuntime_h']);
  b=inside(`<p><b>SysML：把选择、关系与要求写清楚。</b></p>${chips(['part：具体部件','port：交互口','connect：关系','requirement：义务'])}<p style="margin-top:8px">下面的模型词典可以逐项点选。3D是外观示意，模型中的电池能量才是计算输入。</p><p>候选语言能否通过，应由真实建模工具另行确认。</p>`);
  c=inside(`<div class="diagnostic-mini"><div><b>${f(r.runtime_h)} h</b><span>96 Wh × 0.8 ÷ ${f(cA().power_W)} W</span></div><div><b>${r.checks[0].status}</b><span>局部续航估算</span></div></div><p>这里实际执行的是 <code>C.checks(...)</code>。<b>SysML解析 NOT RUN</b>，停车、强度、电气和硬件测试仍未运行。</p><button class="small-tool" onclick="runUntil(6)">运行主线①—⑥，不自动批准</button>`);
  origin='NPS展示“模型文本＋模型图”；论文不提供本页小车的续航、几何或接口验证程序。';extension='我们用同一教学配置连接模型草稿、关系图、3D及数值检查。真实后端应由解析模型取参数。';boundary='本页不是“解析SysML后运行”。显示PASS的只是指定假设下的一项计算，不是整车通过验收。';
 }else if(s===3){
  const q=LP.result;const gg=LP.resultSource||(S.index||C.model(cA(),S.adapter));
  const current=q&&q.sourceFingerprint===(S.index||C.model(cA(),S.adapter)).fingerprint;
  a=inside(`<p><b>CR-08：</b>“增加深度相机，仍须至少2小时。”先查当前设计，不要凭常识重写。</p><div class="lesson-query"><input id="lesson-query" value="${esc(LP.query)}" maxlength="300" aria-label="教学检索问题"><button class="small-tool" onclick="lessonRetrieve()">检索</button></div><p style="margin-top:9px">${S.index?'使用当前主线索引：'+S.index.revision:'主线索引未建立：只在 A 的教学副本上试检索，不冒充已批准索引。'}</p>`);
  b=inside(`<p>${chips(['SysML模型','模型图','相关节点＋邻居','带出处的上下文'])}</p><p>原论文：API/JSON-LD → RDF → MiniLM 384维 → FAISS → LLM。</p><p><b>本页：</b>教学图 → 关键词＋一跳展开。没有执行前面那套向量流水线。</p><p>完整批准需求仍直接提供，不能依赖搜索碰巧找到。</p>`);
  c=current?inside(`<p><b>${q.status}</b> · 来源 ${q.revision} · ${q.elements.length}个元素</p>${q.elements.slice(0,4).map(n=>`<button class="retrieved-mini" onclick="lessonSelectRetrieved('${esc(n.id)}')">${esc(n.label)}<code>${esc(n.path)}</code><span>${esc(JSON.stringify(n.data))}</span></button>`).join('')}<small>显示前4项，完整内容见下方。检索没有修改电池，也没有自动作出可行性结论。</small><details><summary>完整检索结果</summary><pre class="lesson-code">${esc(j(q))}</pre></details>`):inside('<p>点击检索，看实际返回哪些模型元素、关系和版本。旧结果若与当前索引版本不同，会在这里失效，不给新设计背书。</p>');
  origin='GRAG §IV：模型API数据转RDF，节点与一跳邻居嵌入，FAISS检索后重建上下文；原例是电动车。';extension='把模型上下文提供给下一次设计修改。这里的关键字检索是教学替身，不是MiniLM/FAISS复现。';boundary='检索不保证完整，不判断续航是否合格，也不自动修改SysML。已有模型图与检索派生图不是同一个存储职责。';
 }else if(s===4){const c0=cB('B0'),txt=C.sysml(c0,S.adapter);
  a=inside(`<p><b>保持原要求，增加 R-07：</b></p><p>${esc(C.CHANGE.text)}</p><p>${chips(['A：已有模型','GRAG：相关内容','规则：保留R-03/R-04/R-05'])}</p>`);
  b=inside(`<p><b>NPS修改：把功能写成部件与行为。</b></p>${chips(['＋camera','＋visionProcessor','＋imageRecorder','＋localVisionWorkflow'],'add')}<p style="margin-top:9px">点击3D中的相机，再看端口图和代码：不是只在图上贴一个相机图标。</p><button class="small-tool" onclick="choosePart('rover.camera');setDiagramTab('ports')">定位 camera 与连接</button>`);
  c=literalExcerpt('Rover_B0.sysml',txt,['part camera','part visionProcessor','part imageRecorder','connect camera.frameOut','action localVisionWorkflow'],10)+inside(`<b>B0 仅为候选：</b>新增 ${S.deltaW} W 后，总负载 ${c0.power_W} W，续航估算 ${f(C.checks(c0).runtime_h)} h。新增功能不应悄悄破坏2小时要求。`);
  origin='NPS幻灯片14–15：修改自行车模型加入踏板，再加入承载要求；同一模型可以继续修改。';extension='本例新增深度相机、本地处理和记录；软件部件的3D板块只是部署示意，不是新增商品硬件。';boundary='模板展示的是预期建模结果。没有真正运行视觉算法、图像记录、GPT或SysML解析器。';
 }else if(s===5){const cc=g.revision==='A'?cB('B1'):g.config,r=C.checks(cc,S.adapter);
  a=inside(`<p><b>改了感知需求，连电源和结构也受影响。</b></p><div class="lesson-controls">${['B0','B1','B2'].map(id=>`<button class="small-tool ${V.view===id?'active':''}" onclick="lessonCandidate('${id}')">${id} · ${id==='B0'?'原电池':id==='B1'?'换电池':'换托盘'}</button>`).join('')}</div><p style="margin-top:9px"><label>新增电池侧平均负载 <input id="lesson-load" type="number" min="4" max="48" step="1" value="${S.deltaW}" style="width:65px;padding:4px;border:1px solid #c6d9df" aria-label="新增负载瓦数"> W</label> <button class="small-tool" onclick="lessonLoad()">应用并使旧证据失效</button></p><small>4–48 W教学假设；不来自厂家性能。</small>`);
  b=inside(fitSketch(cc)+`<div class="diagnostic-mini"><div><b>${f(r.runtime_h)} h</b><span>${cc.battery.Wh}×0.8÷${cc.power_W}</span></div><div><b>${r.checks[1].status}</b><span>标称尺寸配合</span></div></div>`);
  c=literalExcerpt('Rover_'+cc.id+'.sysml',C.sysml(cc,S.adapter),['part battery','part tray','attribute addedVisionLoadAtBattery_W'])+inside(`<p>${cc.id==='B0'?'B0保持小电池；是否续航不足由当前硬件与负载实际计算，不预设失败。':cc.id==='B1'?'B1虽增加能量，但电池长140mm，原仓只有130mm。3D把电池悬在仓外，故意不画成已装入。':'B2把安装选择改为ExpandedTray，供应商OriginalTray没有被偷偷放大。'}</p><p><b>源模型保持：</b>${verifySources()?'指纹未变':'发生变化，需检查'}。${C.numericPass(r)?'有限检查通过，不等于整车验证完成。':'当前仍有阻止项，不能批准为合格。'}</p>`);
  origin='CMBSE保留源模型，另建集成内容；NPS支持修改已有模型。两篇都不替我们完成电源或机械验证。';extension='确定性续航与固定方向包络检查把具体失败交回设计流程。B0→B1→B2展示不同修复方向。';boundary='B1的悬置是防止错误装配印象的显示规则，不是改变需求。没有结构强度、碰撞、公差或物理仿真认证。';
 }else{const cp=checkpoint(),idx=S.index?.revision||'未建立';
  a=inside(`<p><b>当前工作流：</b>${S.cursor}/12</p><p>A批准：${S.aApproval?'已记录':'没有'}<br>B批准：${S.bApproval?.candidate||'没有'}<br>索引版本：${idx}</p><p>观察B2不等于批准B2。教学预览不会点击你的确认框。</p>`);
  b=inside(`<p><b>${cp.title}</b></p><p>${cp.body}</p><button class="btn primary" onclick="document.getElementById('flow-guide').scrollIntoView({behavior:'smooth',block:'center'})">同页定位真正审批关口</button>`);
  c=inside(`<p>${chips(['模型版本','检查结果','批准记录','索引来源'])}</p><p>批准B之后，还要显式更新派生索引。旧的A引用仍保留自己的版本标签。</p><div class="lesson-controls"><button class="small-tool" onclick="rebuildIndex()" ${!S.bApproval?'disabled':''}>从已批准B重建索引</button><button class="small-tool" onclick="downloadArtifact('evidence')">导出真实当前记录</button></div><p style="margin-top:9px">${S.index&&S.bApproval&&S.index.fingerprint===S.bApproval.fingerprint?'当前索引已与批准B一致。':'尚未宣称索引与批准B一致。'}</p>`);
  origin='CMBSE原方法设人工确认；GRAG从指定模型仓库取得上下文。三篇没有联合提供本工作台。';extension='应用状态、审批门槛、版本指纹、重新检查和索引失效是我们的实现责任。';boundary='本页批准是教学候选确认，不是身份认证、工程签署、制造许可或机器人安全验收。';
 }
 return{d,a,b,c,origin,extension,boundary};
}
function renderLearning(){if(!$('lesson-panel'))return;lessonStageFromMain();const q=lessonData(),d=q.d,[tone,wash]=LCOL[d.paper];$('lesson-panel').style.setProperty('--tone',tone);$('lesson-panel').style.setProperty('--wash',wash);
 $('learning-steps').innerHTML=LESSONS.map((d,i)=>{const [t,w]=LCOL[d.paper];return `<button class="learning-step ${i===LP.step?'active':''}" style="--tone:${t};--wash:${w}" onclick="lessonSet(${i})" aria-pressed="${i===LP.step}"><small>0${i+1} / ${d.method}</small><strong>${d.title}</strong><em>${d.file}</em></button>`;}).join('');
 $('lesson-panel').innerHTML=`<div class="lesson-title"><div><span class="lesson-badge">${d.page}</span><h3>${d.title}</h3><p>看这里的具体输入与输出，再对照上方的小车、模型节点和代码。<b>方法位置 ${d.stage}/12；主线实际执行 ${S.cursor}/12。</b></p></div><div class="lesson-nav"><button class="small-tool" onclick="lessonBack()" ${LP.step===0?'disabled':''}>← 上一段</button><button class="small-tool" onclick="lessonNext()" ${LP.step===6?'disabled':''}>下一段 →</button><button class="small-tool" onclick="lessonFollow()">随主线</button></div></div><div class="lesson-grid">${lessonBox('① 输入：确切资料',q.a)}${lessonBox('② 方法：这里做什么',q.b)}${lessonBox('③ 输出：具体改变与依据',q.c)}</div><div class="method-band"><div><b>论文原文支持</b>${q.origin}</div><div><b>迁移到本项目</b>${q.extension}</div><div><b>不能据此声称</b>${q.boundary}</div></div>`;
 renderTerms();renderPartRoute();
}
function lessonRetrieve(useInput=true){if(useInput)LP.query=$('lesson-query')?.value||LP.query;const graph=S.index?C.clone(S.index):C.model(cA(),S.adapter);LP.resultSource=graph;LP.result=C.retrieve(graph,LP.query);renderLearning();}
function lessonSelectRetrieved(id){const g=LP.resultSource;if(!g||!g.nodes.some(n=>n.id===id))return;V.view=g.revision;V.follow=false;V.part=id;V.tab='structure';renderLab();}
function lessonCandidate(id){LP.step=5;LP.manual=true;V.follow=false;setView(id);V.part=id==='B0'?'rover.camera':'rover.battery';V.tab='ports';renderLab();}
function lessonLoad(){const n=Number($('lesson-load').value);setWorkload(n);LP.step=5;V.follow=false;renderLab();}
function lessonToggleAdapter(){setAdapter(!S.adapter);LP.step=1;V.follow=false;V.view='A';V.part=S.adapter?'rover.commandAdapter':'rover.navigation';V.tab='ports';renderLab();}
const TERMS={
 definition:{button:'part def · 类型',text:'像零件类型的定义：Camera规定这种部件有哪些端口。它不是“已经买了一只相机”。',file:'RoverLibrary.sysml',needles:['part def Camera']},
 usage:{button:'part · 实例',text:'在当前方案中用到的一只具体相机：rover.camera，类型是供应商的OfferedDepthCamera。A里没有，B里新增。',file:'candidate',needles:['part camera']},
 port:{button:'port · 端口',text:'模型中的交互边界：frameOut输出RGBDFrame。它不是USB插头的三维几何，也不自动创建驱动。',file:'RoverLibrary.sysml',needles:['port def ImagePort','part def Camera']},
 connection:{button:'connect · 连接',text:'说明哪个端口接到哪个端口。连接关系不是在电脑里实际发送图像；没有驱动也不会自己运行。',file:'candidate',needles:['connect camera.frameOut']},
 requirement:{button:'requirement · 要求',text:'R-07描述本地视觉的新义务。存在需求元素和追溯关系，不等于这一要求已经被实现或验证。',file:'candidate',needles:['requirement def OfflineVision','requirement localVisionRequirement']}
};
function termSelect(id){if(!TERMS[id])return;LP.term=id;renderTerms();}
function renderTerms(){
 if(!$('model-terms'))return;const g=viewGraph(),n=g.nodes.find(x=>x.id===V.part),isPart=n?.kind==='part',id=isPart?n.id:'rover.camera',name=id.split('.').at(-1),type=isPart?typeFor(n,g):'OfferedDepthCamera';
 const files={['Rover_'+g.revision+'.sysml']:C.sysml(g.config,S.adapter),...C.supplierCodes};
 const want=(needle,all=false)=>{let found=[];for(const[file,text]of Object.entries(files)){text.split('\n').forEach((s,i)=>{if(s.includes(needle))found.push({file,line:i+1,text:s.trim()});});if(found.length&&!all)break;}return found.slice(0,3);};
 let msg='',rows=[];
 if(LP.term==='definition'){msg=`类型说明这一类部件具有什么。例如当前 ${name} 使用 ${type}。定义本身不是一件已安装实物。`;rows=want('part def '+type);}
 if(LP.term==='usage'){msg=`实例表示本方案中选用的一件部件：${id}。内含的电机或IMU仍属于原总成，不自动成为额外采购。`;rows=want('part '+name+' :');if(!rows.length)rows=want('part '+name+':');if(!rows.length&&name==='rover')rows=want('part rover {');}
 if(LP.term==='port'){
  const lookup={'rover.camera':['port usbStream : USBDevicePort','USBDevicePort'],'rover.lidar':['port packets : LivoxPacketPort','LivoxPacketPort'],'rover.livoxDriver':['port cloudOut : PointCloudPort','PointCloudPort'],'rover.cloudProjection':['port cloudIn : ~PointCloudPort','PointCloudPort'],'rover.realsenseDriver':['port usbIn : ~USBDevicePort','USBDevicePort'],'rover.lidar.imu':['part def Imu','ImuPort'],'rover.navigation':['port commandOut : BodyCommandPort','BodyCommandPort'],'rover.commandAdapter':['port bodyIn : ~BodyCommandPort','WheelCommandPort'],'rover.chassis':['port input : ~WheelCommandPort','WheelCommandPort'],'rover.visionProcessor':['part def VisionProcessor','ImagePort'],'rover.imageRecorder':['part def Recorder','LocalObservationPort']};
  if(lookup[id]){rows=[...want(lookup[id][0]),...want('port def '+lookup[id][1])].slice(0,2);msg='端口是模型中的交互边界；方向与类型说明收发什么，不是实际插头几何，也不自动运行驱动。';}
  else{msg='这个部件在当前草稿中没有完整的外部端口定义。不能因为3D看得到电池或电机，就声称电源／驱动接口已建全。';}
 }
 if(LP.term==='connection'){rows=want('connect '+name+'.');if(!rows.length){for(const[file,text]of Object.entries(files)){const ls=text.split('\n');ls.forEach((line,i)=>{if(line.includes('connect ')&&line.includes(' '+name+'.'))rows.push({file,line:i+1,text:line.trim()});});}rows=rows.slice(0,2);}msg='连接说明端口之间的关系。连接写进模型不等于数据已发送；实现和运行需要另外的驱动与测试。';}
 if(LP.term==='requirement'){const target=['rover.camera','rover.visionProcessor','rover.imageRecorder'].includes(id)?'OfflineVision':id==='rover.battery'?'RuntimeTarget':id==='rover.tray'?'WidthLimit':'MapNavigation';rows=want('requirement def '+target);msg='要求表达设计必须满足的义务；追溯连接帮助找到依据，但不是“已验证”的证明。以下是当前部件相关要求的示例。';}
 $('model-terms').innerHTML=`<div class="term-buttons"><small>选中 ${esc(name)}</small>${Object.entries(TERMS).map(([key,t])=>`<button onclick="termSelect('${key}')" class="${LP.term===key?'active':''}">${t.button}</button>`).join('')}</div><div class="term-explanation">${esc(msg)}<br><code>${rows.length?rows.map(r=>esc(r.file)+' L'+r.line+' · '+esc(r.text)).join('<br>'):'未在本版草稿中找到对应定义／关系；保持未建模，不补造。'}</code></div>`;
}
function renderPartRoute(){const e=$('part-paper-route');if(!e)return;const g=viewGraph(),n=g.nodes.find(n=>n.id===V.part);if(!n)return;const isCamera=['rover.camera','rover.visionProcessor','rover.imageRecorder'].includes(n.id);e.innerHTML=`<strong>${esc(n.label)} 的设计履历</strong><button onclick="lessonSet(${isCamera?4:0})">NPS：${isCamera?'新增部件／行为':'创建供应商模型'}</button><span class="arrow">→</span><button onclick="lessonSet(1)">CMBSE：审查对应与连接</button><span class="arrow">→</span><button onclick="lessonSet(3)">GRAG：查询模型依据</button><span class="arrow">→</span><button onclick="lessonSet(5)">工具／人：复查与决定</button><small class="small-note">论文是处理方法，不是“某一家的供应商身份”</small>`;}
function setIsolate(v){if(roverViewer){roverViewer.isolate=!!v;roverViewer.draw();refreshRenderStatus();}const e=$('isolate-part');if(e)e.checked=!!v;}
function setCutaway(v){if(roverViewer){roverViewer.cutaway=!!v;roverViewer.draw();refreshRenderStatus();}}
function inspectHiddenImu(){setView(V.view);choosePart('rover.lidar.imu');setIsolate(true);setExplode(45);cameraView('iso');}
// Extend, rather than replace, existing state transitions and review gates.
const _learningRenderLab=renderLab,_learningReset=reset,_learningQuery=runQuery,_learningHighlight=highlightPaper;
renderLab=function(){_learningRenderLab();renderLearning();};
reset=function(){LP={step:0,term:'usage',query:'电池 续航 功耗 托盘',result:null,resultSource:null,manual:false};if(roverViewer){roverViewer.isolate=false;roverViewer.cutaway=false;}_learningReset();if($('isolate-part'))$('isolate-part').checked=false;if($('cutaway-part'))$('cutaway-part').checked=false;renderLearning();};
runQuery=function(text){const ok=_learningQuery(text);if(ok){LP.result=C.clone(S.auxQuery);LP.resultSource=C.clone(S.index);renderLearning();}return ok;};
highlightPaper=function(p){_learningHighlight(p);const selected=S.paper;if(selected){const i={nps:0,cmb:1,grag:3,ours:2}[selected];lessonSet(i);}else renderLearning();};
const _learningEvidence=evidence;evidence=function(){const e=_learningEvidence();e.explanationLayer={selectedLesson:LESSONS[LP.step].id,origin:'source-derived method map + authored worked example',runsModel:false,previewRetrieval:LP.result?{method:LP.result.method,revision:LP.result.revision,approvedIndexUsed:S.index?.fingerprint===LP.result.sourceFingerprint}:null};e.rendering={opaqueDepth:'per-pixel',softwareFallback:'CPU_Z_BUFFER',transparentPolicy:'opaque pass then depth-tested back-to-front alpha; opaque+cutaway recommended',b1:'infeasible battery lifted; numerical failure retained',geometryNotValidated:true};return e;};
window.refreshRenderStatus=refreshRenderStatus;
window.ROVER_LEARNING={state:()=>C.clone(LP),select:lessonSet,next:lessonNext,query:lessonRetrieve,terms:termSelect,lessonData,fit:fitSketch,reset,follow:lessonFollow};
// Patch exported test helpers to expose the final reset/evidence implementations.
window.ROVER_FLOW.reset=reset;window.ROVER_FLOW.evidence=evidence;
renderLearning();refreshRenderStatus();
