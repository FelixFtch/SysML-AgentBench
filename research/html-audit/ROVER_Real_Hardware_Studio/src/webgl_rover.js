'use strict';
/* Native WebGL rendering. No CDN, images, sensors, physics or CAD assets.
   Parts and selection keys come from the shared authored teaching graph.
   Visual-only geometry is recorded separately and never proves manufacturability. */
window.RoverWebGL = (()=>{
 const RENDER_BUILD='rotation-fix-2026-09-15-r1';
 const M={
  id:()=>new Float32Array([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]),
  mul:(a,b)=>{const r=new Float32Array(16);for(let c=0;c<4;c++)for(let row=0;row<4;row++)for(let k=0;k<4;k++)r[c*4+row]+=a[k*4+row]*b[c*4+k];return r;},
  translate:(x,y,z)=>{const r=M.id();r[12]=x;r[13]=y;r[14]=z;return r;},
  rotX:a=>new Float32Array([1,0,0,0,0,Math.cos(a),Math.sin(a),0,0,-Math.sin(a),Math.cos(a),0,0,0,0,1]),
  rotY:a=>new Float32Array([Math.cos(a),0,-Math.sin(a),0,0,1,0,0,Math.sin(a),0,Math.cos(a),0,0,0,0,1]),
  rotZ:a=>new Float32Array([Math.cos(a),Math.sin(a),0,0,-Math.sin(a),Math.cos(a),0,0,0,0,1,0,0,0,0,1]),
  ortho:(l,r,b,t,n,f)=>new Float32Array([2/(r-l),0,0,0,0,2/(t-b),0,0,0,0,-2/(f-n),0,-(r+l)/(r-l),-(t+b)/(t-b),-(f+n)/(f-n),1]),
  perspective:(fov,asp,n,f)=>{const t=1/Math.tan(fov/2);return new Float32Array([t/asp,0,0,0,0,t,0,0,0,0,(f+n)/(n-f),-1,0,0,2*f*n/(n-f),0]);},
  point:(a,p)=>{const [x,y,z]=p;return [a[0]*x+a[4]*y+a[8]*z+a[12],a[1]*x+a[5]*y+a[9]*z+a[13],a[2]*x+a[6]*y+a[10]*z+a[14],a[3]*x+a[7]*y+a[11]*z+a[15]];},
  look:(eye,target)=>{let z=norm(sub(eye,target)),x=norm(cross([0,1,0],z)),y=cross(z,x);return new Float32Array([x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-dot(x,eye),-dot(y,eye),-dot(z,eye),1]);}
 };
 const sub=(a,b)=>a.map((x,i)=>x-b[i]),dot=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0),norm=a=>{let d=Math.hypot(...a)||1;return a.map(x=>x/d);},cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
 function box(w,h,d){let p=[],n=[];const x=w/2,y=h/2,z=d/2,faces=[[[1,0,0],[[x,-y,-z],[x,y,-z],[x,y,z],[x,-y,z]]],[[-1,0,0],[[-x,-y,z],[-x,y,z],[-x,y,-z],[-x,-y,-z]]],[[0,1,0],[[-x,y,-z],[-x,y,z],[x,y,z],[x,y,-z]]],[[0,-1,0],[[-x,-y,z],[-x,-y,-z],[x,-y,-z],[x,-y,z]]],[[0,0,1],[[x,-y,z],[x,y,z],[-x,y,z],[-x,-y,z]]],[[0,0,-1],[[-x,-y,-z],[-x,y,-z],[x,y,-z],[x,-y,-z]]]];for(const [normal,v] of faces)for(const i of [0,1,2,0,2,3]){p.push(...v[i]);n.push(...normal);}return {p,n};}
 function cylinder(r,h,segments=40,r2=r){const p=[],n=[];function tri(v,ns){p.push(...v.flat());n.push(...ns.flat());}for(let i=0;i<segments;i++){let a=i/segments*Math.PI*2,b=(i+1)/segments*Math.PI*2;let ca=Math.cos(a),sa=Math.sin(a),cb=Math.cos(b),sb=Math.sin(b),na=norm([ca,(r-r2)/h,sa]),nb=norm([cb,(r-r2)/h,sb]);let va=[r*ca,-h/2,r*sa],vb=[r*cb,-h/2,r*sb],vc=[r2*ca,h/2,r2*sa],vd=[r2*cb,h/2,r2*sb];tri([va,vc,vd],[na,na,nb]);tri([va,vd,vb],[na,nb,nb]);tri([[0,h/2,0],vd,vc],[[0,1,0],[0,1,0],[0,1,0]]);tri([[0,-h/2,0],va,vb],[[0,-1,0],[0,-1,0],[0,-1,0]]);}return{p,n};}
 const rgb=hex=>{let s=hex.replace('#','');return[0,2,4].map(i=>parseInt(s.slice(i,i+2),16)/255);};
 class Viewer {
  constructor(container,canvas,labelLayer,onSelect){this.container=container;this.canvas=canvas;this.labels=labelLayer;this.onSelect=onSelect;this.azimuth=.90;this.elevation=.60;this.distance=.70;this.target=[0,.145,0];this.explode=0;this.transparent=false;this.showLabels=true;this.showFlows=false;this.rotate=false;this.visible=false;this.meshes=[];this.selected='rover.battery';this.focusGroup='all';this.anchors={};this.key='';this.frame=0;this.disposed=false;this.w=1;this.h=1;this.pickIds=[''];this.events=0;this.renderCount=0;this.failed=false;this.reason='';this.projection='orthographic';this.autoFit=true;this.requestedRenderer='auto';this.contextLost=false;this.lastGlError=0;this.cameraStats={};
   canvas.addEventListener('webglcontextcreationerror',e=>{this.reason=e.statusMessage||'WebGL context unavailable';});
   this.gl=canvas.getContext('webgl',{antialias:true,alpha:false,depth:true,stencil:false,preserveDrawingBuffer:true})||canvas.getContext('experimental-webgl',{antialias:true,alpha:false,depth:true,stencil:false,preserveDrawingBuffer:true});
   if(this.gl){try{this.initGL();this.status='WEBGL';}catch(e){this.reason=e.message;this.gl=null;this.status='SOFTWARE_3D';}}else{this.status='SOFTWARE_3D';this.reason=this.reason||'WebGL context unavailable';}
   this.bind();this.ro=new ResizeObserver(()=>this.resize());this.ro.observe(container);this.io=new IntersectionObserver(entries=>{this.visible=entries[0].isIntersecting;if(this.visible)this.draw();});this.io.observe(container);this.resize();
   this.canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();for(const m of this.meshes){m.pb=null;m.nb=null;}this.program=null;this.fbo=null;this.tex=null;this.depth=null;this.fbSize='';this.contextLost=true;this.failed=true;this.status='SOFTWARE_3D';this.reason='WEBGL_CONTEXT_LOST';this.fallback();if(window.refreshRenderStatus)window.refreshRenderStatus();});
   this.canvas.addEventListener('webglcontextrestored',()=>{
    this.contextLost=false;
    if(this.requestedRenderer==='software'){this.failed=true;this.status='SOFTWARE_3D';this.reason='USER_SELECTED_CPU_ZBUFFER';return;}
    try {this.initGL();this.failed=false;this.status='WEBGL';this.reason='';this.showGL();this.key='';if(this.graph)this.setModel(this.graph);this.resize();}
    catch(e){this.failToSoftware('WEBGL_RESTORE_FAILED: '+e.message);}
    if(window.refreshRenderStatus)window.refreshRenderStatus();
   });
   const loop=t=>{if(this.disposed)return;if(this.rotate&&this.visible){this.azimuth+=Math.min(.04,(t-(this.lastT||t))/1000)*.24;this.draw();}this.lastT=t;this.frame=requestAnimationFrame(loop);};this.frame=requestAnimationFrame(loop);
  }
  initGL(){
   const g=this.gl;if(!g||g.isContextLost())throw new Error('No live WebGL context');
   g.bindFramebuffer(g.FRAMEBUFFER,null);if(this.program&&g.isProgram(this.program))g.deleteProgram(this.program);if(this.fbo&&g.isFramebuffer(this.fbo))g.deleteFramebuffer(this.fbo);if(this.tex&&g.isTexture(this.tex))g.deleteTexture(this.tex);if(this.depth&&g.isRenderbuffer(this.depth))g.deleteRenderbuffer(this.depth);
   // Keep varying precision identical on both stages. The view uses metre-scale geometry.
   const hi=g.getShaderPrecisionFormat(g.FRAGMENT_SHADER,g.HIGH_FLOAT),precision=hi&&hi.precision>0?'highp':'mediump';
   const vs=`precision ${precision} float;attribute vec3 aP;attribute vec3 aN;uniform mat4 uM,uVP;varying vec3 vN,vP;void main(){vec4 w=uM*vec4(aP,1.0);vN=mat3(uM)*aN;vP=w.xyz;gl_Position=uVP*w;}`;
   const fs=`precision ${precision} float;uniform vec3 uC,uEye;uniform float uPick,uSel,uAlpha,uFloor;varying vec3 vN,vP;void main(){if(uPick>0.5){gl_FragColor=vec4(uC,1.0);return;}vec3 n=normalize(vN);if(!gl_FrontFacing)n=-n;float l=max(dot(n,normalize(vec3(0.1,1.0,0.6))),0.0);float rim=pow(1.0-max(dot(n,normalize(uEye-vP)),0.0),3.0);vec3 col=uC*(0.58+0.4*l)+vec3(.03)*rim;col=mix(col,vec3(.98,.69,.18),uSel*.30);if(uFloor>0.5){float sx=step(.955,fract((vP.x+2.0)*20.0));float sz=step(.955,fract((vP.z+2.0)*20.0));float fine=max(sx,sz);float fade=1.0-smoothstep(.23,.7,length(vP.xz));col=mix(vec3(.949,.961,.969),vec3(.79,.84,.87),fine*fade*.6);}gl_FragColor=vec4(col,uAlpha);}`;
   const sh=(type,source)=>{let x=g.createShader(type);g.shaderSource(x,source);g.compileShader(x);if(!g.getShaderParameter(x,g.COMPILE_STATUS)){const msg=g.getShaderInfoLog(x);g.deleteShader(x);throw Error(msg);}return x;};
   const v=sh(g.VERTEX_SHADER,vs),f=sh(g.FRAGMENT_SHADER,fs),pr=g.createProgram();g.attachShader(pr,v);g.attachShader(pr,f);g.linkProgram(pr);if(!g.getProgramParameter(pr,g.LINK_STATUS))throw Error(g.getProgramInfoLog(pr));g.deleteShader(v);g.deleteShader(f);
   this.program=pr;this.loc={};for(const a of ['aP','aN'])this.loc[a]=g.getAttribLocation(pr,a);for(const u of ['uM','uVP','uC','uEye','uPick','uSel','uAlpha','uFloor'])this.loc[u]=g.getUniformLocation(pr,u);
   g.enable(g.DEPTH_TEST);g.depthFunc(g.LESS);g.disable(g.CULL_FACE);g.frontFace(g.CCW);g.clearDepth(1);g.depthRange(0,1);
   if(g.getParameter(g.DEPTH_BITS)<16)throw new Error('Default drawing buffer has no adequate depth attachment');
   this.fbo=g.createFramebuffer();this.tex=g.createTexture();this.depth=g.createRenderbuffer();this.fbSize='';this.lastGlError=0;this.allocatePickTarget();
  }
  showGL(){this.canvas.style.opacity='1';this.softwareCanvas?.remove();this.softwareCanvas=null;this.softwareContext=null;}
  failToSoftware(reason){this.failed=true;this.status='SOFTWARE_3D';this.reason=reason;this.fallback();if(window.refreshRenderStatus)window.refreshRenderStatus();}
  allocatePickTarget(){
   const g=this.gl,w=this.canvas.width||1,h=this.canvas.height||1;if(!g||g.isContextLost()||this.fbSize===w+':'+h)return;
   g.bindTexture(g.TEXTURE_2D,this.tex);g.texImage2D(g.TEXTURE_2D,0,g.RGBA,w,h,0,g.RGBA,g.UNSIGNED_BYTE,null);
   for(const param of [g.TEXTURE_MIN_FILTER,g.TEXTURE_MAG_FILTER])g.texParameteri(g.TEXTURE_2D,param,g.NEAREST);
   for(const param of [g.TEXTURE_WRAP_S,g.TEXTURE_WRAP_T])g.texParameteri(g.TEXTURE_2D,param,g.CLAMP_TO_EDGE);
   g.bindRenderbuffer(g.RENDERBUFFER,this.depth);g.renderbufferStorage(g.RENDERBUFFER,g.DEPTH_COMPONENT16,w,h);g.bindFramebuffer(g.FRAMEBUFFER,this.fbo);
   g.framebufferTexture2D(g.FRAMEBUFFER,g.COLOR_ATTACHMENT0,g.TEXTURE_2D,this.tex,0);g.framebufferRenderbuffer(g.FRAMEBUFFER,g.DEPTH_ATTACHMENT,g.RENDERBUFFER,this.depth);
   const status=g.checkFramebufferStatus(g.FRAMEBUFFER);g.bindFramebuffer(g.FRAMEBUFFER,null);g.bindTexture(g.TEXTURE_2D,null);g.bindRenderbuffer(g.RENDERBUFFER,null);
   if(status!==g.FRAMEBUFFER_COMPLETE)throw Error('Picking framebuffer incomplete: '+status);
   this.fbSize=w+':'+h;this.pickFramebufferStatus=status;
  }
  bind(){const el=this.canvas;this.pointers=new Map();el.addEventListener('contextmenu',e=>e.preventDefault());el.addEventListener('pointerdown',e=>{this.rotate=false;if(window.refreshRenderStatus)window.refreshRenderStatus();this.pointers.set(e.pointerId,[e.clientX,e.clientY]);this.down={x:e.clientX,y:e.clientY,button:e.button,moved:false};this.prev=[e.clientX,e.clientY];if(el.setPointerCapture)el.setPointerCapture(e.pointerId);});el.addEventListener('pointermove',e=>{if(!this.pointers.has(e.pointerId))return;const old=this.pointers.get(e.pointerId);this.pointers.set(e.pointerId,[e.clientX,e.clientY]);if(!this.down)return;let dx=e.clientX-old[0],dy=e.clientY-old[1];if(Math.hypot(e.clientX-this.down.x,e.clientY-this.down.y)>4)this.down.moved=true;if(this.pointers.size>1){const arr=Array.from(this.pointers.values()),dist=Math.hypot(arr[0][0]-arr[1][0],arr[0][1]-arr[1][1]);if(this.pinch)this.distance=Math.max(.31,Math.min(1.5,this.distance*this.pinch/dist));this.pinch=dist;this.autoFit=false;}else if(e.shiftKey||this.down.button===2){this.target[0]-=dx*.0005;this.target[1]+=dy*.0005;this.autoFit=false;}else{this.azimuth-=dx*.007;this.elevation=Math.max(.08,Math.min(1.5,this.elevation+dy*.005));}this.draw();});const end=e=>{if(this.down&&!this.down.moved&&this.pointers.size===1){const id=this.pick(e.clientX,e.clientY);if(id)this.onSelect(id);}this.pointers.delete(e.pointerId);this.pinch=null;if(!this.pointers.size)this.down=null;};el.addEventListener('pointerup',end);el.addEventListener('pointercancel',e=>{this.pointers.delete(e.pointerId);this.down=null;});this.container.addEventListener('wheel',e=>{e.preventDefault();this.distance=Math.max(.31,Math.min(1.5,this.distance*Math.exp(e.deltaY*.001)));this.autoFit=false;this.draw();},{passive:false});el.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','-','Home'].includes(e.key)){e.preventDefault();if(e.key==='ArrowLeft')this.azimuth-=.15;if(e.key==='ArrowRight')this.azimuth+=.15;if(e.key==='ArrowUp')this.elevation=Math.min(1.5,this.elevation+.1);if(e.key==='ArrowDown')this.elevation=Math.max(.08,this.elevation-.1);if(e.key==='+'){this.distance*=.9;this.autoFit=false;}if(e.key==='-'){this.distance*=1.1;this.autoFit=false;}if(e.key==='Home')this.resetCamera();this.draw();}});
  }
  resize(){
   const r=this.container.getBoundingClientRect();if(r.width<10||r.height<10)return;
   const changed=Math.abs(this.w-r.width)>1||Math.abs(this.h-r.height)>1;this.w=r.width;this.h=r.height;
   const d=Math.min(devicePixelRatio||1,1.6),w=Math.round(this.w*d),h=Math.round(this.h*d);
   if(this.canvas.width!==w)this.canvas.width=w;if(this.canvas.height!==h)this.canvas.height=h;
   if(this.gl&&!this.failed){try{this.allocatePickTarget();}catch(e){this.failToSoftware(e.message);return;}}
   if(changed&&this.autoFit&&this.meshes.length)this.fitScene(false);this.draw();
  }
  add(id,shape,dims,pos,color,options={}){const geo=shape==='box'?box(...dims):cylinder(...dims);let mesh={id,shape,dims,pos,color:rgb(color),alpha:options.alpha??1,rot:options.rot||[0,0,0],explode:options.explode||[0,0,0],group:options.group||'all',decor:options.decor||false,floor:options.floor||false,logical:options.logical||false,normalColor:color,geo,pickId:0};if(id){let i=this.pickIds.indexOf(id);if(i<0){i=this.pickIds.length;this.pickIds.push(id);}mesh.pickId=i;}if(this.gl&&!this.failed){const g=this.gl;mesh.pb=g.createBuffer();g.bindBuffer(g.ARRAY_BUFFER,mesh.pb);g.bufferData(g.ARRAY_BUFFER,new Float32Array(geo.p),g.STATIC_DRAW);mesh.nb=g.createBuffer();g.bindBuffer(g.ARRAY_BUFFER,mesh.nb);g.bufferData(g.ARRAY_BUFFER,new Float32Array(geo.n),g.STATIC_DRAW);}mesh.bounds={min:[0,1,2].map(i=>Math.min(...geo.p.filter((v,k)=>k%3===i))),max:[0,1,2].map(i=>Math.max(...geo.p.filter((v,k)=>k%3===i)))};this.meshes.push(mesh);return mesh;}
  setModel(graph){this.graph=graph;if(this.key===graph.fingerprint){this.draw();return;}this.key=graph.fingerprint;this.build(graph.config);this.fitScene(false);this.draw();}
  build(c){
   if(this.gl&&!this.gl.isContextLost())for(const m of this.meshes){if(m.pb)this.gl.deleteBuffer(m.pb);if(m.nb)this.gl.deleteBuffer(m.nb);}
   this.meshes=[];this.pickIds=[''];this.anchors={};
   const box=(id,d,p,col,o)=>this.add(id,'box',d,p,col,o),cy=(id,d,p,col,o)=>this.add(id,'cyl',d,p,col,o);
   const opt=(group,exp=[0,0,0],extra={})=>({group,explode:exp,...extra});
   const ch='rover.chassis';
   // Wheel centres/radius follow the teaching catalog. The display deck is narrower
   // than the inner tyre planes and higher than the tyre tops: no unintended cut-through.
   box('',[1.6,.003,1.6],[0,-.009,0],'#edf3f6',{floor:true,decor:true});
   box(ch,[.330,.008,.236],[0,.115,0],'#becbd5',opt('mechanical'));
   for(const z of [-.113,.113])box(ch,[.314,.020,.006],[0,.101,z],'#647988',opt('mechanical'));
   for(const x of [-.157,.157])box(ch,[.008,.020,.220],[x,.101,0],'#8b9ca8',opt('mechanical'));
   // A front/rear bumper denotes the authored overall-width envelope. No CAD claim.
   const overall=c.tray.installedRoverWidth_mm/1000;
   for(const x of [-.174,.174])box(ch,[.011,.016,overall],[x,.124,0],'#394d5b',opt('mechanical'));
   for(const [id,z] of [['rover.chassis.motorLeft',-.14],['rover.chassis.motorRight',.14]]){
    const ex=[-.020,-.008,Math.sign(z)*.090];
    cy(id,[.05,.026,48],[-.065,.050,z],'#25333d',opt('mechanical',ex,{rot:[Math.PI/2,0,0]}));
    // Hubs protrude beyond the tyre end faces; no coplanar caps.
    cy(id,[.030,.030,36],[-.065,.050,z],'#b4c4cf',opt('mechanical',ex,{rot:[Math.PI/2,0,0]}));
    cy(id,[.012,.034,24],[-.065,.050,z],'#667f8c',opt('mechanical',ex,{rot:[Math.PI/2,0,0]}));
    box(id,[.060,.030,.042],[-.065,.050,Math.sign(z)*.089],'#6e9097',opt('mechanical',ex));
    cy(id,[.006,.017,16],[-.065,.050,Math.sign(z)*.1185],'#a8bac3',opt('mechanical',ex,{rot:[Math.PI/2,0,0]}));
    this.anchors[id]={pos:[-.065,.069,z],explode:ex};
   }
   // Passive support wheels and struts are non-selectable hardware within chassis.
   for(const z of [-.077,.077]){
    cy(ch,[.022,.019,28],[.125,.022,z],'#405868',opt('mechanical',[.045,-.008,0],{rot:[Math.PI/2,0,0]}));
    box(ch,[.027,.053,.027],[.125,.070,z],'#9cabb6',opt('mechanical',[.045,-.008,0]));
   }
   for(const x of [-.140,.145])for(const z of [-.104,.104])cy(ch,[.004,.004,14],[x,.123,z],'#617784',opt('mechanical'));
   const tray='rover.tray',battery='rover.battery';
   const [tl,tw,th]=c.tray.inside_mm.map(x=>x/1000),tx=-.045,ty=.123;
   const ez=[-.042,.085,-.01],eb=[-.042,.178,-.01],col=c.id==='B2'?'#5298b0':'#8ca4b2';
   // The inner cavity starts at ty+2mm. Wall thickness is OUTSIDE that cavity.
   box(tray,[tl+.008,.004,tw+.008],[tx,ty,0],col,opt('mechanical',ez));
   for(const x of [-1,1])box(tray,[.004,th,tw+.008],[tx+x*(tl/2+.002),ty+.002+th/2,0],c.id==='B1'?'#ce7865':col,opt('mechanical',ez));
   for(const z of [-1,1])box(tray,[tl,th,.004],[tx,ty+.002+th/2,z*(tw/2+.002)],col,opt('mechanical',ez));
   const [bl,bw,bh]=c.battery.size_mm.map(x=>x/1000),by=ty+.004+bh/2;
   // B1 intentionally illustrates an infeasible pack. Lift it above the cavity rather
   // than rendering intersecting walls as if it were assembled. The violation stays FAIL.
   const lift=c.id==='B1'?.064:0;
   box(battery,[bl-.010,bh,bw],[tx,by+lift,0],'#d4a94d',opt('power',eb));
   for(const dir of [-1,1])box(battery,[.005,bh,bw],[tx+dir*(bl/2-.0025),by+lift,0],'#344d5e',opt('power',eb));
   // A separated thin label has a real depth gap, not a duplicate coplanar face.
   box(battery,[bl*.57,.0006,bw*.49],[tx,by+lift+bh/2+.0007,0],'#fff0c4',opt('power',eb));
   this.anchors[battery]={pos:[tx,by+lift+bh/2+.009,0],explode:eb};
   this.anchors[tray]={pos:[tx-tl/2-.006,ty+th*.65,.049],explode:ez};
   // Hardware outlines use cited product dimensions; supports, heights and detail placement are schematic.
   const lidar='rover.lidar',imu='rover.lidar.imu',lx=.104,el=[.055,.150,-.055];
   for(const z of [-.025,.025])cy(lidar,[.0035,.054,12],[lx,.145,z],'#a9bcc7',opt('sensing',el));
   box(lidar,[.071,.004,.071],[lx,.174,0],'#b7c9d1',opt('sensing',el));
   // Mid-360S is a compact non-spinning 65x65x60mm sensor, not a rotating cylinder.
   box(lidar,[.065,.024,.065],[lx,.188,0],'#364c46',opt('sensing',el));
   box(lidar,[.065,.032,.065],[lx,.216,0],'#253746',opt('sensing',el));
   box(lidar,[.065,.004,.065],[lx,.234,0],'#566a70',opt('sensing',el));
   box(lidar,[.022,.0007,.020],[lx,.2368,0],'#c4d5c9',opt('sensing',el));
   box(imu,[.013,.005,.013],[lx-.006,.188,.005],'#55ac93',opt('sensing',[.125,.27,-.1]));
   this.anchors[lidar]={pos:[lx,.246,0],explode:el};this.anchors[imu]={pos:[lx-.006,.2,.005],explode:[.125,.27,-.1]};
   this.anchors[ch]={pos:[-.16,.127,-.10],explode:[0,0,0]};
   const host='rover.compute',hx=-.073,hy=.274,hz=-.007,eh=[-.080,.205,.065];
   // Elevated illustrative mounting shelf avoids overlap with both large battery and B1 suspended pack.
   for(const dx of [-.045,.045])for(const dz of [-.033,.033])cy(host,[.002,.014,10],[hx+dx,hy-.010,hz+dz],'#b5c6ce',opt('computing',eh));
   const pi=c.hardware&&c.hardware.computeId!=='nx16';
   if(pi){
    box(host,[.085,.002,.056],[hx,hy,hz],'#267d58',opt('computing',eh));
    box(host,[.015,.004,.015],[hx-.011,hy+.0035,hz],'#263b45',opt('computing',eh));
    box(host,[.034,.013,.024],[hx-.009,hy+.014,hz],'#8b9ea6',opt('computing',eh));
    for(let i=0;i<7;i++)box(host,[.002,.006,.024],[hx-.024+i*.005,hy+.0235,hz],'#74878e',opt('computing',eh));
    for(const dz of [-.017,0,.018])box(host,[.017,.012,.013],[hx+.034,hy+.008,hz+dz],'#b6c4c9',opt('computing',eh));
    box(host,[.050,.005,.005],[hx-.006,hy+.004,hz+.0245],'#b7a454',opt('computing',eh));
   }else{
    const carrier='rover.compute.carrier',mod='rover.compute.module';
    box(carrier,[.100,.002,.080],[hx,hy,hz],'#346157',opt('computing',eh));
    // Carrier outline and connectors are NOT vendor verified. The SoM has the real 69.6x45 outline.
    box(mod,[.0696,.002,.045],[hx-.006,hy+.006,hz-.006],'#248362',opt('computing',eh));
    box(mod,[.045,.006,.031],[hx-.009,hy+.011,hz-.006],'#929f9b',opt('computing',eh));
    for(let i=0;i<9;i++)box(mod,[.003,.012,.030],[hx-.029+i*.005,hy+.0205,hz-.006],'#8a979d',opt('computing',eh));
    for(const z of [-.023,.001,.025])box(carrier,[.018,.014,.017],[hx+.040,hy+.009,hz+z],'#abbec4',opt('computing',eh));
    this.anchors[mod]={pos:[hx-.006,hy+.031,hz-.006],explode:eh};this.anchors[carrier]={pos:[hx+.037,hy+.014,hz+.03],explode:eh};
   }
   this.anchors[host]={pos:[hx,hy+.04,hz],explode:eh};
   // Software is deployed on this host, not shown as separately purchased circuit boards.
   for(const id of ['rover.navigation','rover.commandAdapter','rover.livoxDriver','rover.cloudProjection','rover.stateEstimator','rover.visionProcessor','rover.imageRecorder','rover.realsenseDriver'])
    this.anchors[id]={pos:[hx,hy+.045,hz],explode:eh};
   if(c.vision){
    const ca='rover.camera',ec=[.095,.06,.025],cx=.177,cyy=.174;
    box(ca,[.025,.025,.090],[cx,cyy,0],'#9baeb8',opt('sensing',ec));
    box(ca,[.001,.020,.085],[cx+.0133,cyy,0],'#293e4e',opt('sensing',ec));
    box(ca,[.018,.025,.025],[cx-.017,cyy-.024,0],'#adbfc8',opt('sensing',ec));
    for(const z of [-.0325,.0175,.035]){cy(ca,[.006,.0012,22],[cx+.0145,cyy,z],'#536b7a',opt('sensing',ec,{rot:[0,0,-Math.PI/2]}));cy(ca,[.0035,.0006,22],[cx+.0156,cyy,z],'#6cc2d0',opt('sensing',ec,{rot:[0,0,-Math.PI/2]}));}
    const ci='rover.camera.imu';box(ci,[.008,.004,.009],[cx-.005,cyy+.002,-.008],'#57a991',opt('sensing',[.135,.16,.10]));
    this.anchors[ci]={pos:[cx,cyy+.015,-.008],explode:[.135,.16,.10]};this.anchors[ca]={pos:[cx+.018,cyy+.020,0],explode:ec};
   }
   this.anchors.rover={pos:[0,.15,0],explode:[0,.05,0]};
  }
  matrix(mesh){let p=mesh.pos.map((v,i)=>v+mesh.explode[i]*this.explode);return M.mul(M.translate(...p),M.mul(M.rotZ(mesh.rot[2]),M.mul(M.rotY(mesh.rot[1]),M.rotX(mesh.rot[0]))));}
  sceneBounds(){
   let min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];const points=[];
   for(const mesh of this.meshes){if(mesh.decor||this.opacity(mesh)<=.005)continue;const m=this.matrix(mesh),b=mesh.bounds;
    for(let i=0;i<8;i++){const p=M.point(m,[i&1?b.max[0]:b.min[0],i&2?b.max[1]:b.min[1],i&4?b.max[2]:b.min[2]]).slice(0,3);points.push(p);for(let a=0;a<3;a++){min[a]=Math.min(min[a],p[a]);max[a]=Math.max(max[a],p[a]);}}
   }
   if(!points.length)return {min:[-.1,0,-.1],max:[.1,.2,.1],center:[0,.1,0],radius:.18,points:[[0,.1,0]]};
   const center=min.map((v,i)=>(v+max[i])/2),radius=Math.max(.025,...points.map(p=>Math.hypot(...sub(p,center))));return {min,max,center,radius,points};
  }
  fitScene(draw=true){const b=this.sceneBounds();this.target=[...b.center];const aspect=Math.max(.1,this.w/this.h),half=.36;
   this.distance=this.projection==='orthographic'?b.radius*1.08/(Math.tan(half)*Math.min(1,aspect)):b.radius*1.10/Math.sin(Math.min(half,Math.atan(Math.tan(half)*aspect)));
   this.distance=Math.max(.20,Math.min(3,this.distance));this.autoFit=true;if(draw)this.draw();
  }
  setProjection(mode){this.projection=mode==='perspective'?'perspective':'orthographic';this.fitScene();if(window.refreshRenderStatus)window.refreshRenderStatus();}
  camera(){
   this.elevation=Math.max(.06,Math.min(1.52,Number.isFinite(this.elevation)?this.elevation:.6));this.azimuth=Number.isFinite(this.azimuth)?this.azimuth:.9;
   this.distance=Math.max(.20,Math.min(3,Number.isFinite(this.distance)?this.distance:.8));
   const b=this.sceneBounds(),radius=Math.max(.03,...b.points.map(p=>Math.hypot(...sub(p,this.target))));
   // Orbit outside a sphere containing EVERY visible part at the current explode pose.
   // Orthographic zoom changes projection scale, never the camera's physical location.
   const orbit=this.projection==='orthographic'?Math.max(.8,3*radius+.2):Math.max(this.distance,radius*1.12+.08);
   this.eye=[this.target[0]+Math.cos(this.azimuth)*Math.cos(this.elevation)*orbit,this.target[1]+Math.sin(this.elevation)*orbit,this.target[2]+Math.sin(this.azimuth)*Math.cos(this.elevation)*orbit];
   const near=Math.max(.005,(orbit-radius)*.25),far=orbit+radius+.25,aspect=Math.max(.05,this.w/this.h);
   const halfH=Math.max(.025,this.distance*Math.tan(.36)),proj=this.projection==='orthographic'?M.ortho(-halfH*aspect,halfH*aspect,-halfH,halfH,near,far):M.perspective(.72,aspect,near,far);
   this.vp=M.mul(proj,M.look(this.eye,this.target));this.cameraStats={projection:this.projection,near,far,orbitDistance:orbit,visibleRadius:radius,zoomDistance:this.distance,autoFit:this.autoFit,visibleBounds:{min:b.min,max:b.max},depthClipPolicy:'orbit outside assembly; dynamic planes'};
  }
  draw(picking=false){
   if(!this.meshes.length)return;this.camera();if(!this.gl||this.failed){if(!picking)this.fallback();return;}
   const g=this.gl;if(g.isContextLost()){this.failToSoftware('WEBGL_CONTEXT_LOST');return;}
   try {
    // Never inherit depth/blend/framebuffer/culling state from picking or another pass.
    g.bindFramebuffer(g.FRAMEBUFFER,picking?this.fbo:null);g.useProgram(this.program);g.uniformMatrix4fv(this.loc.uVP,false,this.vp);g.uniform3fv(this.loc.uEye,this.eye);
    g.viewport(0,0,this.canvas.width,this.canvas.height);g.colorMask(true,true,true,true);g.depthMask(true);g.clearDepth(1);g.depthRange(0,1);
    g.disable(g.SCISSOR_TEST);g.disable(g.STENCIL_TEST);g.disable(g.POLYGON_OFFSET_FILL);g.disable(g.SAMPLE_COVERAGE);g.disable(g.SAMPLE_ALPHA_TO_COVERAGE);g.disable(g.CULL_FACE);g.frontFace(g.CCW);g.disable(g.BLEND);
    if(picking)g.disable(g.DITHER);else g.enable(g.DITHER);
    g.clearColor(picking?0:.949,picking?0:.961,picking?0:.969,1);g.clear(g.COLOR_BUFFER_BIT|g.DEPTH_BUFFER_BIT);g.enable(g.DEPTH_TEST);g.depthFunc(g.LESS);
    let draws=0;const drawMesh=mesh=>{
     if(!mesh.pb||!mesh.nb)throw Error('Mesh GPU buffers unavailable: '+mesh.id);
     g.uniformMatrix4fv(this.loc.uM,false,this.matrix(mesh));g.uniform1f(this.loc.uPick,picking?1:0);g.uniform1f(this.loc.uFloor,mesh.floor&&!picking?1:0);g.uniform1f(this.loc.uSel,this.isSelectedMesh(mesh)&&!picking?1:0);g.uniform1f(this.loc.uAlpha,picking?1:this.opacity(mesh));g.uniform3fv(this.loc.uC,picking?[mesh.pickId/255,0,0]:mesh.color);
     g.bindBuffer(g.ARRAY_BUFFER,mesh.pb);g.vertexAttribPointer(this.loc.aP,3,g.FLOAT,false,0,0);g.enableVertexAttribArray(this.loc.aP);g.bindBuffer(g.ARRAY_BUFFER,mesh.nb);g.vertexAttribPointer(this.loc.aN,3,g.FLOAT,false,0,0);g.enableVertexAttribArray(this.loc.aN);g.drawArrays(g.TRIANGLES,0,mesh.geo.p.length/3);draws++;
    };
    const visible=this.meshes.filter(m=>this.opacity(m)>.005);
    if(picking){for(const m of visible)if(m.pickId&&this.opacity(m)>=.12)drawMesh(m);}
    else {
     for(const m of visible)if(this.opacity(m)>=.995)drawMesh(m);
     const cameraDepth=m=>{const p=M.point(this.matrix(m),[0,0,0]);return dot(sub(p.slice(0,3),this.eye),norm(sub(this.target,this.eye)));};
     const translucent=visible.filter(m=>this.opacity(m)<.995).sort((a,b)=>cameraDepth(b)-cameraDepth(a));
     g.enable(g.BLEND);g.blendFunc(g.SRC_ALPHA,g.ONE_MINUS_SRC_ALPHA);g.depthMask(false);
     // Translucency is optional; opaque solids always retain depth. Two-sided meshes
     // avoid disappearing faces on drivers when no manufacturing winding is promised.
     for(const m of translucent)drawMesh(m);
    }
    g.depthMask(true);g.disable(g.BLEND);g.disable(g.CULL_FACE);g.enable(g.DITHER);
    const error=g.getError();this.lastGlError=error;if(error!==g.NO_ERROR)throw Error('WebGL error '+error);
    if(!picking){this.lastDrawStats={drawCalls:draws,visibleMeshes:visible.length};this.renderCount++;this.canvas.style.opacity='1';this.drawLabels();}
   }catch(e){if(!g.isContextLost())g.bindFramebuffer(g.FRAMEBUFFER,null);this.failToSoftware(e.message);}
  }
  selectedRoot(){return this.graph?.nodes.find(n=>n.id===this.selected)?.data?.deployedOn||this.selected;}
  isSelectedMesh(m){const root=this.selectedRoot();return m.id===root||(root==='rover.compute'&&m.id.startsWith(root+'.'));}
  opacity(m){
   if(m.decor)return m.alpha;
   const root=this.selectedRoot();if(this.isolate&&this.anchors[this.selected]&&root!=='rover'&&m.id!==root&&!m.id.startsWith(root+'.'))return 0;
   if(this.cutaway&&m.id==='rover.chassis'&&m.shape==='box'&&m.dims[0]>.3&&m.dims[1]<.011)return 0;
   let a=m.alpha;
   const group=this.focusGroup==='software'?'computing':this.focusGroup;if(group!=='all'&&m.group!==group&&!this.isSelectedMesh(m))a*=.11;
   if(this.transparent&&m.id==='rover.chassis')a*=.18;
   return a;
  }
  point(id){let a=this.anchors[id];if(!a)return null;let pos=a.pos.map((v,i)=>v+a.explode[i]*this.explode);let t=M.point(this.vp,pos);if(t[3]<=0||t[2]<-t[3]||t[2]>t[3])return null;return {x:(t[0]/t[3]+1)*this.w/2,y:(1-t[1]/t[3])*this.h/2,depth:t[2]/t[3],world:pos};}
  drawLabels(){
   if(!this.labels||!this.graph)return;
   let important=this.showLabels?['rover.lidar','rover.battery','rover.chassis','rover.camera',this.selected]:[this.selected];
   if(this.isolate)important=[this.selected];
   const candidates=[...new Set(important)].map(id=>({id,n:this.graph.nodes.find(n=>n.id===id),p:this.point(id)})).filter(x=>x.n&&x.p&&x.p.depth<1&&x.p.x>=0&&x.p.x<=this.w&&x.p.y>=0&&x.p.y<=this.h);
   // Screen-space label lanes avoid multiple labels being stamped on the same face.
   const labelW=Math.min(128,this.w*.32),labelH=24,occupied=[];let html='',leaders='';
   candidates.sort((a,b)=>(b.id===this.selected)-(a.id===this.selected));
   for(const x of candidates){const p=x.p,id=x.id;const left=p.x<this.w*.52?8:this.w-labelW-8;let top=Math.max(44,Math.min(this.h-105,p.y-12));
    const overlaps=y=>occupied.some(r=>Math.abs(r.x-left)<labelW&&Math.abs(r.y-y)<labelH+5);
    let steps=0;while(overlaps(top)&&steps++<10){top+=labelH+6;if(top>this.h-100)top=45+(steps-1)*3;}
    if(overlaps(top)&&id!==this.selected)continue;occupied.push({x:left,y:top});
    const endX=left<this.w*.5?left+labelW:left;
    leaders+=`<path d="M${p.x},${p.y} L${endX},${top+12}" fill="none" stroke="${id===this.selected?'#b4893f':'#829dab'}" stroke-width="1"/><circle cx="${p.x}" cy="${p.y}" r="2.5" fill="${id===this.selected?'#bf913b':'#6b929c'}"/>`;
    html+=`<button class="part-pin ${id===this.selected?'selected':''}" style="left:${left}px;top:${top}px;width:${labelW}px" onclick="choosePart('${id}')" data-part-id="${id}"><i></i>${x.n.label}${id==='rover.battery'?' · '+this.graph.config.battery.Wh+'Wh':''}</button>`;
   }
   let flow='';if(this.showFlows){const segments=this.graph.edges.filter(e=>['Scan2D','ImuSample','BodyVelocity','WheelRPM','RGBDFrame','LocalObservation','INCOMPATIBLE_DIRECT_LINK'].includes(e.type));flow=`<defs><marker id="three-arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10" fill="#6955a4"/></marker></defs>`+segments.map(e=>{const a=this.point(e.from),b=this.point(e.to);if(!a||!b)return'';return `<path class="projected-flow-path" d="M${a.x},${a.y} Q${(a.x+b.x)/2},${Math.min(a.y,b.y)-26} ${b.x},${b.y}" stroke="${e.type.includes('INCOMPATIBLE')?'#c66a51':'#7963aa'}" stroke-width="2" fill="none" stroke-dasharray="4 4" marker-end="url(#three-arr)"/>`;}).join('');}
   this.labels.innerHTML=`<svg class="projected-links" viewBox="0 0 ${this.w} ${this.h}">${leaders}${flow}</svg>`+html;
  }
  pick(clientX,clientY){
   const rect=this.canvas.getBoundingClientRect();
   if(!this.gl||this.failed){const buf=this.softwarePick;if(!buf)return null;const x=Math.floor((clientX-rect.left)/rect.width*buf.w),y=Math.floor((clientY-rect.top)/rect.height*buf.h);if(x<0||x>=buf.w||y<0||y>=buf.h)return null;this.events++;return this.pickIds[buf.ids[y*buf.w+x]]||null;}
   const g=this.gl,x=Math.max(0,Math.min(this.canvas.width-1,Math.floor((clientX-rect.left)/rect.width*this.canvas.width))),y=Math.max(0,Math.min(this.canvas.height-1,this.canvas.height-1-Math.floor((clientY-rect.top)/rect.height*this.canvas.height)));let hit=null;
   try{this.allocatePickTarget();this.draw(true);if(this.failed)return null;const p=new Uint8Array(4);g.readPixels(x,y,1,1,g.RGBA,g.UNSIGNED_BYTE,p);this.lastGlError=g.getError();if(this.lastGlError)throw Error('Pick readPixels failed '+this.lastGlError);hit=this.pickIds[p[0]]||null;}
   catch(e){this.failToSoftware(e.message);}
   finally{if(!g.isContextLost())g.bindFramebuffer(g.FRAMEBUFFER,null);this.draw();}
   this.events++;return hit;
  }
  fallback(){
   // CPU fallback uses a PER-PIXEL z-buffer and picking buffer. Painter sorting is
   // insufficient where long triangles overlap; it caused the old speckled surfaces.
   this.canvas.style.opacity='0';if(!this.graph)return;this.camera();
   if(!this.softwareCanvas){this.softwareCanvas=document.createElement('canvas');this.softwareCanvas.className='software-3d-canvas';this.container.insertBefore(this.softwareCanvas,this.labels);this.softwareContext=this.softwareCanvas.getContext('2d',{willReadFrequently:true});}
   if(!this.softwareContext)return;
   const ctx=this.softwareContext,can=this.softwareCanvas;
   const scale=Math.min(1.35,Math.sqrt(430000/(this.w*this.h)));
   const w=Math.max(1,Math.round(this.w*scale)),h=Math.max(1,Math.round(this.h*scale));
   if(can.width!==w||can.height!==h){can.width=w;can.height=h;}
   ctx.setTransform(1,0,0,1,0,0);ctx.fillStyle='#f2f6f8';ctx.fillRect(0,0,w,h);
   const project=pos=>{const v=M.point(this.vp,pos);return[(v[0]/v[3]+1)*w/2,(1-v[1]/v[3])*h/2,v[2]/v[3],v[3]];};
   ctx.strokeStyle='#dae4e9';ctx.lineWidth=.65;for(let k=-9;k<=9;k++){const t=k*.05;for(const ends of [[[t,-.006,-.45],[t,-.006,.45]],[[-.45,-.006,t],[.45,-.006,t]]]){const a=project(ends[0]),b=project(ends[1]);if(a[3]<=0||b[3]<=0)continue;ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.stroke();}}
   const center=project([0,0,0]);ctx.save();ctx.translate(center[0],center[1]);ctx.scale(1,.45);const grad=ctx.createRadialGradient(0,0,2,0,0,w*.23);grad.addColorStop(0,'#30465e24');grad.addColorStop(1,'#30465e00');ctx.fillStyle=grad;ctx.beginPath();ctx.arc(0,0,w*.23,0,Math.PI*2);ctx.fill();ctx.restore();
   const image=ctx.getImageData(0,0,w,h),pixels=image.data;
   const depth=new Float64Array(w*h);depth.fill(Infinity);const ids=new Uint16Array(w*h);
   const pickDepth=new Float64Array(w*h);pickDepth.fill(Infinity);
   const faces=[],light=norm([.1,1,.6]);
   const planes=[v=>v[3]+v[0],v=>v[3]-v[0],v=>v[3]+v[1],v=>v[3]-v[1],v=>v[3]+v[2],v=>v[3]-v[2]];
   const clipPolygon=vertices=>{let out=vertices;for(const dist of planes){const input=out;out=[];if(!input.length)break;for(let i=0;i<input.length;i++){const a=input[i],b=input[(i+1)%input.length],da=dist(a),db=dist(b),ain=da>=0,bin=db>=0;if(ain)out.push(a);if(ain!==bin){const t=da/(da-db);out.push(a.map((v,j)=>v+(b[j]-v)*t));}}}return out;};
   const fromClip=v=>[(v[0]/v[3]+1)*w/2,(1-v[1]/v[3])*h/2,v[2]/v[3],v[3]];
   for(const mesh of this.meshes){if(mesh.decor)continue;const alpha=this.opacity(mesh);if(alpha<.005)continue;const mat=this.matrix(mesh),geo=mesh.geo;
    for(let k=0;k<geo.p.length;k+=9){const world=[];for(let z=0;z<3;z++)world.push(M.point(mat,geo.p.slice(k+z*3,k+z*3+3)).slice(0,3));
     const poly=clipPolygon(world.map(p=>M.point(this.vp,p)));if(poly.length<3)continue;
     const nr=geo.n.slice(k,k+3);let normal=norm([mat[0]*nr[0]+mat[4]*nr[1]+mat[8]*nr[2],mat[1]*nr[0]+mat[5]*nr[1]+mat[9]*nr[2],mat[2]*nr[0]+mat[6]*nr[1]+mat[10]*nr[2]]);
     const centroid=[0,1,2].map(i=>(world[0][i]+world[1][i]+world[2][i])/3);if(dot(normal,sub(this.eye,centroid))<0)normal=normal.map(v=>-v);
     const lighting=.58+.40*Math.max(0,dot(normal,light)),selected=this.isSelectedMesh(mesh);
     const rgb=mesh.color.map((c,i)=>Math.round(255*Math.min(1,c*lighting*(selected?.86:1)+(selected?[.95,.72,.32][i]*.14:0))));
     for(let i=1;i<poly.length-1;i++){const pts=[poly[0],poly[i],poly[i+1]].map(fromClip);faces.push({id:mesh.id,pickId:mesh.pickId,pts,z:(pts[0][2]+pts[1][2]+pts[2][2])/3,rgb,alpha});}
    }
   }
   const raster=(face,opaque)=>{
    const[a,b,c]=face.pts,area=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1]);if(Math.abs(area)<.00001)return;
    const minX=Math.max(0,Math.ceil(Math.min(a[0],b[0],c[0])-.5)),maxX=Math.min(w-1,Math.floor(Math.max(a[0],b[0],c[0])-.5));
    const minY=Math.max(0,Math.ceil(Math.min(a[1],b[1],c[1])-.5)),maxY=Math.min(h-1,Math.floor(Math.max(a[1],b[1],c[1])-.5));
    if(minX>maxX||minY>maxY)return;
    const dx0=(b[1]-c[1])/area,dy0=(c[0]-b[0])/area,dx1=(c[1]-a[1])/area,dy1=(a[0]-c[0])/area;
    for(let y=minY;y<=maxY;y++){
     let q0=((b[1]-c[1])*(minX+.5-c[0])+(c[0]-b[0])*(y+.5-c[1]))/area;
     let q1=((c[1]-a[1])*(minX+.5-c[0])+(a[0]-c[0])*(y+.5-c[1]))/area;
     for(let x=minX;x<=maxX;x++,q0+=dx0,q1+=dx1){const q2=1-q0-q1;if(q0<0||q1<0||q2<0)continue;
      const z=q0*a[2]+q1*b[2]+q2*c[2],idx=y*w+x;if(z>=depth[idx])continue;const p=idx*4;
      if(opaque){pixels[p]=face.rgb[0];pixels[p+1]=face.rgb[1];pixels[p+2]=face.rgb[2];depth[idx]=z;}
      else {const A=face.alpha;pixels[p]=face.rgb[0]*A+pixels[p]*(1-A);pixels[p+1]=face.rgb[1]*A+pixels[p+1]*(1-A);pixels[p+2]=face.rgb[2]*A+pixels[p+2]*(1-A);}
      if(face.alpha>=.12&&z<pickDepth[idx]){ids[idx]=face.pickId;pickDepth[idx]=z;}
     }
    }
   };
   faces.filter(f=>f.alpha>=.995).forEach(f=>raster(f,true));faces.filter(f=>f.alpha<.995).sort((a,b)=>b.z-a.z).forEach(f=>raster(f,false));
   ctx.putImageData(image,0,0);this.softwarePick={ids,w,h,depth:pickDepth};
   this.softwareFaces=faces.map(f=>({...f,pts:f.pts.map(p=>[p[0]*this.w/w,p[1]*this.h/h,p[2]])}));
   this.renderCount++;this.drawLabels();
  }
  setRenderingMode(mode){
   this.requestedRenderer=mode;
   if(mode==='software'){this.failed=true;this.status='SOFTWARE_3D';this.reason='USER_SELECTED_CPU_ZBUFFER';this.draw();}
   else if(this.gl&&!this.gl.isContextLost()){
    try{this.failed=false;this.status='WEBGL';this.reason='';this.showGL();this.initGL();this.key='';if(this.graph)this.setModel(this.graph);this.resize();}
    catch(e){this.failToSoftware(e.message);}
   }else {this.failed=!!this.gl;this.status='SOFTWARE_3D';this.reason=this.reason||'WebGL unavailable; using CPU z-buffer';this.draw();}
   if(window.refreshRenderStatus)window.refreshRenderStatus();
  }
  resetCamera(view='iso'){this.rotate=false;if(view==='top'){this.azimuth=Math.PI/2;this.elevation=1.50;}else if(view==='front'){this.azimuth=0;this.elevation=.11;}else if(view==='side'){this.azimuth=Math.PI/2;this.elevation=.20;}else{this.azimuth=.90;this.elevation=.60;}this.fitScene();}
  setExplode(value){this.explode=Math.max(0,Math.min(1,value));this.fitScene();}
  resetVisibility(){this.isolate=false;this.cutaway=false;this.transparent=false;this.focusGroup='all';this.rotate=false;this.fitScene();}
  inspect(){
   let glInfo=null;if(this.gl&&!this.gl.isContextLost()){const g=this.gl,e=g.getExtension('WEBGL_debug_renderer_info');glInfo={version:g.getParameter(g.VERSION),renderer:e?g.getParameter(e.UNMASKED_RENDERER_WEBGL):g.getParameter(g.RENDERER),depthBits:g.getParameter(g.DEPTH_BITS),drawingBuffer:[g.drawingBufferWidth,g.drawingBufferHeight],contextAttributes:g.getContextAttributes()};}
   return {build:RENDER_BUILD,renderer:this.status,requestedRenderer:this.requestedRenderer,reason:this.reason,glInfo,glError:this.lastGlError,pickFramebufferComplete:this.pickFramebufferStatus===this.gl?.FRAMEBUFFER_COMPLETE,revision:this.graph?.revision,parts:this.pickIds.filter(Boolean),selected:this.selected,explode:this.explode,renderCount:this.renderCount,pickCount:this.events,camera:{azimuth:this.azimuth,elevation:this.elevation,distance:this.distance,...this.cameraStats},visibility:{isolate:!!this.isolate,cutaway:!!this.cutaway,transparent:!!this.transparent,focusGroup:this.focusGroup},geometrySource:'AUTHORED_SCHEMATIC_GEOMETRY_PLUS_CATALOG_DIMENSIONS',depthPolicy:this.status==='WEBGL'?'EXPLICIT_FRAME_STATE_OPAQUE_DEPTH_SORTED_ALPHA':'PER_PIXEL_CPU_ZBUFFER_HOMOGENEOUS_CLIP',meshCount:this.meshes.length,lastDraw:this.lastDrawStats,parser:'NOT_RUN'};
  }
  exportView(){this.draw();return (this.status==='WEBGL'?this.canvas:this.softwareCanvas).toDataURL('image/png');}
 }
 return {Viewer,Matrix:M};
})();
