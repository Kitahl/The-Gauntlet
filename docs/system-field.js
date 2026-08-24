(() => {
  'use strict';

  const canvas = document.getElementById('system-field-canvas');
  const caption = document.getElementById('system-caption');
  if (!canvas) return;
  const ctx = canvas.getContext('2d', { alpha: true });
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const DPR_CAP = 1.5;
  const COLORS = {
    base: '#8290a0', accent: '#ff735f', mind: '#dec167', space: '#80aef7', reality: '#df86cf', power: '#58cedc', time: '#84cb96', bad: '#e46b5b', good: '#82d79a'
  };

  let W = 0, H = 0, dpr = 1, active = 'hero', previous = 'hero', switchedAt = performance.now();
  let pointerX = 0, pointerY = 0;
  let far = [], webNodes = [], webEdges = [];
  const sceneLabels = {
    hero: ['LIVE SYSTEM VIEW','TASK → OBLIGATION → METHOD → RECEIPT'],
    overview: ['SYSTEM MAP','FIVE SPECIALISTS · FIVE CONTROL / REVIEW TOOLS'],
    workflow: ['ROUTING TRACE','ONLY LOAD-BEARING METHODS ACTIVATE'],
    gems: ['SPECIALIST LAYER','THE FIELD RECONFIGURES AROUND THE CLAIM'],
    mind: ['MIND / FORMAL REASONING','CLAIM → OBLIGATION → PROOF / COUNTEREXAMPLE'],
    space: ['SPACE / RESEARCH DISCOVERY','QUERY → SOURCES → SCOPED FINDING'],
    reality: ['REALITY / METHOD SYNTHESIS','KNOWN METHODS → GAP → CANDIDATE → RECHECK'],
    power: ['POWER / ENGINEERING VERIFICATION','SOURCE → BUILD → TEST → RUNTIME → RECEIPT'],
    time: ['TIME / EVALUATION','CANDIDATE ∥ BASELINE → MATCHED CELLS → STOP / GO'],
    system: ['CONTROL MODEL','TASK → OBLIGATIONS → METHODS → RECEIPTS → RESULT'],
    quiet: ['SOURCE / IMPLEMENTATION','DETAIL VIEW']
  };

  function rand(a,b){ return a + Math.random() * (b-a); }
  function hexToRgb(hex){ const n=parseInt(hex.slice(1),16); return [(n>>16)&255,(n>>8)&255,n&255]; }
  function rgba(hex,a){ const [r,g,b]=hexToRgb(hex); return `rgba(${r},${g},${b},${a})`; }
  function lerp(a,b,t){ return a + (b-a)*t; }
  function ease(t){ return t*t*(3-2*t); }
  function clamp(v,a,b){ return Math.max(a,Math.min(b,v)); }

  // Derived from the uploaded Nexus Rift menu's cosmic-web/orbital formation idea,
  // but implemented locally in Canvas2D so the public site has no remote runtime dependency.
  function buildFarField(){
    far = [];
    const count = W < 700 ? 220 : 520;
    for(let i=0;i<count;i++){
      const mode = i % 3;
      let x,y,z;
      if(mode===0){ // orbital tangle
        const a=rand(0,Math.PI*2), r=rand(.18,.55), squash=rand(.35,.8);
        x=.72+Math.cos(a)*r; y=.46+Math.sin(a)*r*squash; z=rand(.2,1);
      } else if(mode===1){ // cosmic web
        x=rand(.18,1.25); y=rand(-.1,1.15); z=rand(.15,1);
      } else { // scatter
        x=rand(0,1.3); y=rand(0,1); z=rand(.1,1);
      }
      far.push({x,y,z,s:rand(.45,1.7),phase:rand(0,Math.PI*2),speed:rand(.2,.8)});
    }
  }

  function buildWeb(){
    webNodes=[]; webEdges=[];
    const anchors = W < 700 ? 14 : 22;
    for(let i=0;i<anchors;i++) webNodes.push({x:rand(.48,1.05),y:rand(.08,.92),z:rand(.2,1),phase:rand(0,6.28)});
    for(let i=0;i<webNodes.length;i++){
      let ranked=[];
      for(let j=i+1;j<webNodes.length;j++){
        const a=webNodes[i],b=webNodes[j],d=(a.x-b.x)**2+(a.y-b.y)**2;
        ranked.push([d,j]);
      }
      ranked.sort((a,b)=>a[0]-b[0]);
      ranked.slice(0, i%3===0?2:1).forEach(([,j])=>webEdges.push([i,j]));
    }
  }

  function resize(){
    dpr=Math.min(devicePixelRatio||1,DPR_CAP); W=innerWidth; H=innerHeight;
    canvas.width=Math.floor(W*dpr); canvas.height=Math.floor(H*dpr); canvas.style.width=W+'px'; canvas.style.height=H+'px';
    ctx.setTransform(dpr,0,0,dpr,0,0); buildFarField(); buildWeb();
  }

  function diamond(x,y,r,color,alpha=1,fill=true){
    ctx.save();ctx.translate(x,y);ctx.rotate(Math.PI/4);ctx.globalAlpha=alpha;
    if(fill){ctx.fillStyle=color;ctx.fillRect(-r,-r,r*2,r*2);}else{ctx.strokeStyle=color;ctx.lineWidth=1;ctx.strokeRect(-r,-r,r*2,r*2);}ctx.restore();
  }
  function line(a,b,color,alpha=1,width=1){ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.strokeStyle=rgba(color,alpha);ctx.lineWidth=width;ctx.stroke();}
  function label(text,x,y,color='#b6c0cb',alpha=.8,align='center',size=10){ctx.font=`700 ${size}px ${getComputedStyle(document.documentElement).getPropertyValue('--mono') || 'monospace'}`;ctx.textAlign=align;ctx.textBaseline='middle';ctx.fillStyle=rgba(color,alpha);ctx.fillText(text,x,y);}

  function drawFar(t,intensity){
    const driftX=Math.sin(t*.00006)*16 + pointerX*5, driftY=Math.cos(t*.00005)*8 + pointerY*4;
    far.forEach((p,i)=>{
      const tw=.55+.45*Math.sin(t*.0007*p.speed+p.phase);
      const perspective=.55+.45*p.z;
      const x=(p.x*W)+driftX*(1-p.z), y=(p.y*H)+driftY*(1-p.z);
      const a=intensity*(.05+.12*tw)*(1-p.z*.32);
      diamond(x,y,p.s*perspective,'#c7d0da',a,true);
    });
    ctx.save();ctx.globalCompositeOperation='lighter';
    webEdges.forEach(([i,j],k)=>{
      const a=webNodes[i],b=webNodes[j];
      const ax=a.x*W+driftX*(1-a.z),ay=a.y*H+driftY*(1-a.z),bx=b.x*W+driftX*(1-b.z),by=b.y*H+driftY*(1-b.z);
      const pulse=.5+.5*Math.sin(t*.00035+k*.7); line([ax,ay],[bx,by],COLORS.base,intensity*(.025+.035*pulse),.65);
    });
    ctx.restore();
  }

  function gemGeometry(cx,cy,s){
    const p=[
      [cx,cy-s],[cx-s*.64,cy-s*.55],[cx-s,cy],[cx-s*.58,cy+s*.68],[cx,cy+s],[cx+s*.58,cy+s*.68],[cx+s,cy],[cx+s*.64,cy-s*.55],
      [cx,cy-s*.42],[cx-s*.38,cy],[cx,cy+s*.42],[cx+s*.38,cy],[cx,cy]
    ];
    const e=[[0,1],[1,2],[2,3],[3,4],[4,5],[5,6],[6,7],[7,0],[0,8],[1,8],[7,8],[2,9],[3,10],[4,10],[5,10],[6,11],[8,12],[9,12],[10,12],[11,12],[8,9],[9,10],[10,11],[11,8]];
    return {p,e};
  }

  function drawGem(cx,cy,s,color,t,alpha=1){
    const {p,e}=gemGeometry(cx,cy,s); ctx.save();ctx.globalCompositeOperation='lighter';
    e.forEach((edge,k)=>{const pulse=.45+.55*Math.sin(t*.0011-k*.29);line(p[edge[0]],p[edge[1]],color,alpha*(.24+.19*pulse),1);});
    p.forEach((q,i)=>diamond(q[0],q[1],i===12?4:2.3,color,alpha*(i===12?.95:.55),true));ctx.restore(); return {p,e};
  }

  function travellingPulse(a,b,t,offset,color,alpha=1){
    const u=(t*.00018+offset)%1, x=lerp(a[0],b[0],u),y=lerp(a[1],b[1],u);diamond(x,y,3,color,alpha,true);
  }

  function stagePos(){
    if(W<800) return {cx:W*.64,cy:H*.36,s:Math.min(W,H)*.23};
    return {cx:W*.73,cy:H*.49,s:Math.min(W,H)*.27};
  }

  function drawTaskRoute(t,color=COLORS.accent,alpha=.8){
    const {cx,cy,s}=stagePos();
    const inP=[W<800?W*.12:W*.48,cy],out=[W<800?W*.92:W*.94,cy];
    line(inP,[cx-s,cy],color,alpha*.5,1.2);line([cx+s,cy],out,color,alpha*.5,1.2);
    diamond(inP[0],inP[1],4,color,alpha,true);diamond(out[0],out[1],4,COLORS.good,alpha,true);
    if(W>760){label('TASK',inP[0],inP[1]-18,'#cbd3dc',alpha*.7);label('RECEIPT',out[0],out[1]-18,'#cbd3dc',alpha*.7);}
    travellingPulse(inP,[cx-s,cy],t,.05,color,alpha);travellingPulse([cx+s,cy],out,t,.45,COLORS.good,alpha);
    return {cx,cy,s,inP,out};
  }

  function drawHero(t,transition){
    const {cx,cy,s}=stagePos(); const reveal=clamp((t%10500)/6500,0,1); const r=ease(reveal);
    // reveal front borrowed from Nexus Rift's progressive constellation reveal, now tied to a task graph.
    drawGem(cx,cy,s,COLORS.accent,t,.65*r);
    const task=[W*.48,cy], obligations=[[cx-s*.98,cy-s*.48],[cx-s*1.08,cy],[cx-s*.98,cy+s*.48]], receipts=[[cx+s*.9,cy-s*.48],[cx+s*1.04,cy],[cx+s*.9,cy+s*.48]];
    if(W>800){
      obligations.forEach((o,i)=>{line(task,o,COLORS.accent,.25*r,1);diamond(o[0],o[1],3,COLORS.base,.55*r);line(o,receipts[i],COLORS.accent,.22*r,1);diamond(receipts[i][0],receipts[i][1],3,COLORS.good,.65*r);});
      diamond(task[0],task[1],5,'#e8edf2',.85*r);label('TASK',task[0],task[1]-20,'#dfe5ec',.7*r);
      label('SPACE',cx,cy-s*.45,COLORS.space,.75*r);label('POWER',cx,cy,COLORS.power,.75*r);label('COUNCIL',cx,cy+s*.45,COLORS.reality,.65*r);
    }
    const front=lerp(W*.42,W*.97,r);ctx.fillStyle=rgba('#c7d7ea',.08*(1-r));ctx.fillRect(front,0,1,H);
  }

  function drawOverview(t){
    const baseX=W<800?W*.2:W*.53, step=W<800?W*.145:W*.09, y=H*.5, s=Math.min(W,H)*(W<800?.08:.105);
    [COLORS.mind,COLORS.space,COLORS.reality,COLORS.power,COLORS.time].forEach((c,i)=>{const yy=W<800?H*(.25+i*.12):y;const xx=W<800?W*.72:baseX+i*step;drawGem(xx,yy,s,c,t,.27);});
  }

  function drawWorkflow(t){
    const y=H*.52, xs=W<800?[W*.17,W*.38,W*.59,W*.8]:[W*.47,W*.61,W*.75,W*.89];const names=['SPACE','REALITY','POWER','TIME'], cols=[COLORS.space,COLORS.reality,COLORS.power,COLORS.time];
    for(let i=0;i<xs.length;i++){if(i<xs.length-1)line([xs[i],y],[xs[i+1],y],COLORS.accent,.28,1);drawGem(xs[i],y,Math.min(W,H)*(W<800?.075:.095),cols[i],t,.58);if(W>800)label(names[i],xs[i],y,cols[i],.75);if(i<xs.length-1)travellingPulse([xs[i],y],[xs[i+1],y],t,i*.23,COLORS.accent,.8);}
  }

  function drawMind(t){
    const st=drawTaskRoute(t,COLORS.mind,.9);drawGem(st.cx,st.cy,st.s,COLORS.mind,t,.78);
    const top=[st.cx+st.s*1.08,st.cy-st.s*.52], bot=[st.cx+st.s*1.08,st.cy+st.s*.52], core=[st.cx,st.cy];
    line(core,top,COLORS.mind,.42,1.2);line(core,bot,COLORS.bad,.35,1.1);diamond(top[0],top[1],4,COLORS.good,.9);diamond(bot[0],bot[1],4,COLORS.bad,.8);
    if(W>760){label('PROOF',top[0],top[1]-18,COLORS.good,.85);label('COUNTEREXAMPLE',bot[0],bot[1]+18,COLORS.bad,.8);label('PROOF OBLIGATION',core[0],core[1],COLORS.mind,.8);}
  }

  function drawSpace(t){
    const st=drawTaskRoute(t,COLORS.space,.9);drawGem(st.cx,st.cy,st.s,COLORS.space,t,.76);
    const targets=[[st.cx+st.s*.45,st.cy-st.s*1.15],[st.cx+st.s*1.05,st.cy-st.s*.38],[st.cx+st.s*.45,st.cy+st.s*1.15]],names=['PAPERS','REPOS','STANDARDS'];
    targets.forEach((p,i)=>{line([st.cx,st.cy],p,COLORS.space,.35,1);diamond(p[0],p[1],4,COLORS.space,.78);travellingPulse([st.cx,st.cy],p,t,i*.22,COLORS.space,.85);if(W>760)label(names[i],p[0],p[1]+(i===2?17:-17),'#c9d8ee',.72);});
  }

  function drawReality(t){
    const st=drawTaskRoute(t,COLORS.reality,.9);drawGem(st.cx,st.cy,st.s,COLORS.reality,t,.76);
    const gap=[st.cx-st.s*.1,st.cy],a=[st.cx+st.s*.6,st.cy-st.s*.48],b=[st.cx+st.s*.6,st.cy+st.s*.48];
    line(gap,a,COLORS.reality,.42,1);line(gap,b,COLORS.reality,.32,1);diamond(a[0],a[1],4,COLORS.good,.82);diamond(b[0],b[1],4,COLORS.bad,.55);
    if(W>760){label('NAMED GAP',gap[0],gap[1],COLORS.reality,.8);label('CANDIDATE',a[0],a[1]-18,COLORS.good,.8);label('KILLED',b[0],b[1]+18,COLORS.bad,.65);}
  }

  function drawPower(t){
    const st=drawTaskRoute(t,COLORS.power,.9);drawGem(st.cx,st.cy,st.s,COLORS.power,t,.76);
    const ys=st.cy, xs=[st.cx-st.s*.62,st.cx-st.s*.28,st.cx+.05*st.s,st.cx+.38*st.s,st.cx+.7*st.s];
    const names=['SOURCE','BUILD','TEST','RUN','REGRESS'];
    xs.forEach((x,i)=>{if(i<xs.length-1)line([x,ys],[xs[i+1],ys],COLORS.power,.4,1.1);diamond(x,ys,3.4,COLORS.power,.75);if(W>760)label(names[i],x,ys-18,'#cce8eb',.65, 'center', 9);if(i<xs.length-1)travellingPulse([x,ys],[xs[i+1],ys],t,i*.14,COLORS.power,.9);});
    const fail=[xs[2],ys+st.s*.72];line([xs[2],ys],fail,COLORS.bad,.34,1);diamond(fail[0],fail[1],4,COLORS.bad,.7);if(W>760)label('FAILURE CLASS',fail[0],fail[1]+18,COLORS.bad,.65);
  }

  function drawTime(t){
    const st=drawTaskRoute(t,COLORS.time,.9);drawGem(st.cx,st.cy,st.s,COLORS.time,t,.72);
    const y1=st.cy-st.s*.34,y2=st.cy+st.s*.34,xs=[st.cx-st.s*.62,st.cx-st.s*.18,st.cx+st.s*.26,st.cx+st.s*.68];
    xs.forEach((x,i)=>{if(i<xs.length-1){line([x,y1],[xs[i+1],y1],COLORS.time,.38,1);line([x,y2],[xs[i+1],y2],COLORS.base,.24,1);}diamond(x,y1,3.2,COLORS.time,.75);diamond(x,y2,3.2,COLORS.base,.58);if(i<xs.length-1){travellingPulse([x,y1],[xs[i+1],y1],t,i*.13,COLORS.time,.86);travellingPulse([x,y2],[xs[i+1],y2],t,.5+i*.13,'#aeb7c1',.65);}});
    if(W>760){label('CANDIDATE',xs[0],y1-18,COLORS.time,.75);label('BASELINE',xs[0],y2+18,'#aeb7c1',.65);label('COMPARE',xs[3],st.cy,'#dce4de',.75);}
  }

  function drawSystem(t){
    const y=W<800?H*.28:H*.24,xs=W<800?[W*.12,W*.31,W*.5,W*.69,W*.88]:[W*.53,W*.63,W*.73,W*.83,W*.93];
    xs.forEach((x,i)=>{if(i<xs.length-1)line([x,y],[xs[i+1],y],COLORS.accent,.24,1);diamond(x,y,i===0||i===4?4.5:3.2,i===4?COLORS.good:COLORS.accent,.65);if(i<xs.length-1)travellingPulse([x,y],[xs[i+1],y],t,i*.17,COLORS.accent,.7);});
  }

  function drawScene(t){
    const intensity=active==='quiet'?.18:(active==='hero'?.78:(active==='overview'?.28:.5));drawFar(t,intensity);
    const reveal=reduced?1:ease(clamp((t-switchedAt)/720,0,1));
    ctx.save();ctx.globalAlpha=reveal;
    switch(active){
      case 'hero': drawHero(t); break; case 'overview': drawOverview(t); break; case 'workflow': drawWorkflow(t); break; case 'gems': drawOverview(t); break;
      case 'mind': drawMind(t); break; case 'space': drawSpace(t); break; case 'reality': drawReality(t); break; case 'power': drawPower(t); break; case 'time': drawTime(t); break;
      case 'system': drawSystem(t); break; case 'quiet': break;
    }
    ctx.restore();
  }

  function frame(t){
    ctx.clearRect(0,0,W,H);ctx.fillStyle='#030405';ctx.fillRect(0,0,W,H);drawScene(reduced?3500:t);if(!reduced)requestAnimationFrame(frame);
  }

  function setScene(scene){
    if(scene===active) return; previous=active;active=scene;switchedAt=performance.now();document.body.dataset.scene=scene;
    if(caption && sceneLabels[scene]){caption.innerHTML=`<strong>${sceneLabels[scene][0]}</strong><span>${sceneLabels[scene][1]}</span>`;}
    const section=document.querySelector(`.scene-section[data-scene="${scene}"]`);const accent=section?.dataset.accent||'';if(accent)document.documentElement.style.setProperty('--live-accent',accent);else document.documentElement.style.removeProperty('--live-accent');
    if(reduced){ctx.clearRect(0,0,W,H);ctx.fillStyle='#030405';ctx.fillRect(0,0,W,H);drawScene(3500);}
  }

  const sections=[...document.querySelectorAll('.scene-section[data-scene]')];
  let sceneRAF=0;
  function resolveScene(){
    sceneRAF=0;
    const targetY=H*.48;
    let best=null,bestDist=Infinity;
    for(const section of sections){
      const r=section.getBoundingClientRect();
      if(r.bottom<=0 || r.top>=H) continue;
      const visibleTop=Math.max(0,r.top),visibleBottom=Math.min(H,r.bottom);
      if(visibleBottom<=visibleTop) continue;
      const center=(visibleTop+visibleBottom)*.5;
      const dist=Math.abs(center-targetY);
      if(dist<bestDist){best=section;bestDist=dist;}
    }
    if(best)setScene(best.dataset.scene||'hero');
  }
  function queueScene(){if(!sceneRAF)sceneRAF=requestAnimationFrame(resolveScene);}
  const observer=new IntersectionObserver(queueScene,{threshold:[0,.1,.25,.5,.75]});
  sections.forEach(s=>observer.observe(s));
  addEventListener('scroll',queueScene,{passive:true});
  addEventListener('resize',()=>{resize();queueScene();},{passive:true});
  addEventListener('pointermove',e=>{pointerX=(e.clientX/W-.5);pointerY=(e.clientY/H-.5);},{passive:true});
  resize();
  if(reduced){drawScene(3500);}else requestAnimationFrame(frame);
})();
