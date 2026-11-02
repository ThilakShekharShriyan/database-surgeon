import {mkdirSync,writeFileSync} from "node:fs";
import {homedir} from "node:os";
import {join} from "node:path";
const {Browser,sleep}=await import(join(homedir(),".agents/skills/design-taste-frontend/scripts/lib/cdp.mjs"));
const out=".local/research-qa";mkdirSync(out,{recursive:true});
const browser=await Browser.launch();const report={checks:[],errors:[]};
const base=process.env.RESEARCH_BASE_URL||"http://127.0.0.1:3100";
function check(value,message){if(!value)throw Error(message);report.checks.push(message);console.log("PASS "+message);}
try {
  const page=await browser.newPage({width:1440,height:1000});
  browser.on(page.sessionId,"Runtime.exceptionThrown",e=>report.errors.push(e.exceptionDetails?.exception?.description||e.exceptionDetails?.text));
  if(process.argv.includes("--hydration-debug")){
    const tree=()=>{const visit=n=>n.nodeType===3?n.textContent:n.nodeType===1?{tag:n.tagName,cls:n.getAttribute('class'),children:Array.from(n.childNodes).filter(c=>c.nodeType===1||c.nodeType===3).map(visit)}:null;return visit(document.querySelector('.research'));};
    await page.send('Emulation.setScriptExecutionDisabled',{value:true});await page.goto(base,{settleMs:300});
    const server=await page.eval(tree);
    await page.send('Emulation.setScriptExecutionDisabled',{value:false});await page.goto(base,{settleMs:5000});
    const client=await page.eval(tree);const differences=[];
    function diff(a,b,p='root'){if(differences.length>15)return;if(typeof a!==typeof b||a==null||b==null){if(a!==b)differences.push({p,a,b});return;}if(typeof a==='string'){if(a!==b)differences.push({p,a,b});return;}if(a.tag!==b.tag||a.cls!==b.cls)differences.push({p,a:{tag:a.tag,cls:a.cls},b:{tag:b.tag,cls:b.cls}});for(let i=0;i<Math.max(a.children.length,b.children.length);i++)diff(a.children[i],b.children[i],p+'/'+(a.tag||'')+':'+i);}
    diff(server,client);console.log(JSON.stringify({differences,errors:report.errors},null,2));await browser.close();process.exit(0);
  }
  if(!process.argv.includes("--static-only")){
  await page.goto(base,{settleMs:2000});
  for(let i=0;i<40;i++){if(await page.eval(()=>!!document.querySelector(".r-kpis")))break;await sleep(500);}
  check(await page.eval(()=>document.querySelector("h1")?.textContent==="The evidence, in full."),"Research is the opening screen");
  check(await page.eval(()=>document.querySelectorAll(".r-svg-scroll svg").length===4),"Four quantitative SVG charts render from saved evidence");
  check(await page.eval(()=>document.querySelectorAll(".r-matrix tbody tr").length>=8),"Family acceptance matrix renders real query families");
  check(await page.eval(()=>document.documentElement.scrollWidth<=innerWidth),"Desktop stays inside viewport");
  check(await page.eval(()=>{
    const downloads=[];const original=HTMLAnchorElement.prototype.click;
    HTMLAnchorElement.prototype.click=function(){downloads.push(this.download);};
    try{document.querySelector('.r-title-actions .r-button')?.click();}finally{HTMLAnchorElement.prototype.click=original;}
    return downloads.includes('surgeon-dev-systems.csv');
  }),"CSV export creates a named evidence download");
  await page.screenshot({path:out+"/overview-desktop.jpg",fullPage:true});
  await page.eval(()=>document.querySelector('[role="tab"]:nth-child(2)').click());await sleep(300);
  check(await page.eval(()=>document.querySelector("h1")?.textContent==="Every comparison is paired."),"Paired statistics tab works");
  check(await page.eval(()=>document.querySelector(".r-contingency")?.textContent.includes("Baseline alone")),"McNemar contingency table is visible");
  await page.eval(()=>{const select=document.querySelector('[aria-label="Research baseline"]');select.value="open-raw";select.dispatchEvent(new Event("change",{bubbles:true}));});await sleep(300);
  check(await page.eval(()=>document.querySelector(".r-stats-kpis")?.textContent.includes("0.0020")),"Changing baseline recomputes displayed paired evidence");
  await page.screenshot({path:out+"/statistics-desktop.jpg",fullPage:true});
  await page.eval(()=>document.querySelector('[role="tab"]:nth-child(3)').click());await sleep(250);
  check(await page.eval(()=>document.querySelectorAll(".r-query-list button").length===98),"Query explorer lists all 98 development cases");
  await page.eval(()=>{const select=document.querySelector('[aria-label="Research system"]');select.value="fw-nemotron-harness";select.dispatchEvent(new Event("change",{bubbles:true}));});await sleep(250);
  await page.eval(()=>Array.from(document.querySelectorAll(".r-query-list button")).find(b=>b.textContent.includes("incorrect"))?.click());await sleep(250);
  check(await page.eval(()=>!!document.querySelector(".r-counterexample")),"Incorrect output exposes its recorded counterexample");
  await page.screenshot({path:out+"/counterexample-desktop.jpg",fullPage:true});
  await page.eval(()=>{const input=document.querySelector('[aria-label="Search query evidence"]');const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set;setter.call(input,"no-such-case-987654");input.dispatchEvent(new Event("input",{bubbles:true}));});await sleep(250);
  check(await page.eval(()=>document.querySelectorAll(".r-query-list button").length===0&&document.querySelector(".r-query-list")?.textContent.includes("No queries")),"Query search has an honest empty state");
  await page.eval(()=>document.querySelector('[role="tab"]:nth-child(4)').click());await sleep(250);
  check(await page.eval(()=>document.querySelectorAll(".r-pipeline>div").length===5),"Protocol and limitations are present");
  check(await page.eval(()=>{
    const downloads=[];const original=HTMLAnchorElement.prototype.click;
    HTMLAnchorElement.prototype.click=function(){downloads.push(this.download);};
    try{Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('Download research snapshot'))?.click();}finally{HTMLAnchorElement.prototype.click=original;}
    return downloads.includes('database-surgeon-research.json');
  }),"Snapshot export creates a named JSON evidence download");
  await page.eval(()=>Array.from(document.querySelectorAll(".r-split button")).find(b=>b.textContent.includes("Held-out"))?.click());await sleep(300);
  check(await page.eval(()=>document.querySelector(".r-snapshot-note")?.textContent.includes("incomplete")),"Held-out view discloses incomplete coverage");
  await page.eval(()=>document.querySelector('[role="tab"]:first-child').click());await sleep(200);
  for(const width of [768,390]){await page.setViewport({width,height:900});await sleep(250);check(await page.eval(()=>document.documentElement.scrollWidth<=innerWidth),`Research fits ${width}px viewport`);await page.screenshot({path:out+`/heldout-${width}.jpg`,fullPage:true});}
  await page.setViewport({width:390,height:844});
  await page.goto(base+"/demo",{settleMs:1200});
  await page.eval(()=>Array.from(document.querySelectorAll(".pitch-tabs button")).find(b=>b.textContent==="Live surgery")?.click());await sleep(200);
  await page.eval(()=>document.querySelectorAll(".preset-card")[1]?.click());await sleep(150);
  check(await page.eval(()=>document.querySelector(".sd-go")?.textContent.includes("Replay recorded trace")),"Demo exposes explicit recorded replay");
  await page.eval(()=>document.querySelector(".sd-go")?.click());
  for(let i=0;i<40;i++){if(await page.eval(()=>!!document.querySelector(".pipeline")))break;await sleep(250);}
  check(await page.eval(()=>document.querySelector(".pipeline")?.textContent.includes("Recorded replay")),"Recorded demo completes without evaluator or model inference");
  await page.screenshot({path:out+"/demo-replay-mobile.jpg",fullPage:true});
  check(await page.eval(()=>document.documentElement.scrollWidth<=innerWidth),"Live demo fits phone viewport");
  const missing=await page.eval(async()=>{const r=await fetch("/api/optimize",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({sql:"SELECT 987654 AS unrecorded",replay:true})});return r.status;});
  check(missing===404,"Missing replay is rejected instead of making a paid call");
  }
  await page.setViewport({width:1440,height:1000});await page.goto("http://127.0.0.1:8766",{settleMs:1000});
  for(let i=0;i<20;i++){if(await page.eval(()=>document.querySelectorAll("#systems tbody tr").length>0))break;await sleep(250);}
  check(await page.eval(()=>document.querySelectorAll("#systems tbody tr").length>2),"Static research companion loads the same real snapshot");
  await page.screenshot({path:out+"/static-desktop.jpg",fullPage:true});
  await page.setViewport({width:390,height:844});await sleep(200);
  await page.screenshot({path:out+"/static-mobile.jpg",fullPage:true});
  const overflow=await page.eval(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,elements:Array.from(document.querySelectorAll("body *")).filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,12).map(e=>[e.tagName,e.className,Math.round(e.getBoundingClientRect().width)])}));
  if(overflow.scroll>overflow.width)console.log(JSON.stringify(overflow));
  check(overflow.scroll<=overflow.width,"Static research companion fits phone viewport");
  check(report.errors.length===0,"No uncaught browser exceptions");
} finally {writeFileSync(out+"/report.json",JSON.stringify(report,null,2));await browser.close();}
