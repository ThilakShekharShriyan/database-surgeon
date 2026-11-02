import { mkdirSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
const { Browser, sleep } = await import(join(homedir(),".agents/skills/design-taste-frontend/scripts/lib/cdp.mjs"));
mkdirSync(".local/ui-qa",{recursive:true});
const browser=await Browser.launch();
const report={checks:[],errors:[],chat:false};
const assert=(value,message)=>{if(!value)throw Error(message);report.checks.push(message);console.log("PASS "+message);};
try {
  const page=await browser.newPage({width:1440,height:1000});
  browser.on(page.sessionId,"Runtime.exceptionThrown",event=>report.errors.push(event.exceptionDetails?.text||"Browser exception"));
  await page.goto("http://127.0.0.1:3100/lab",{settleMs:1800});
  for(let i=0;i<15;i++){if(await page.eval(()=>document.querySelectorAll(".query-row").length>0))break;await sleep(500);}
  assert(await page.eval(()=>document.querySelector("h1")?.textContent==="Optimization lab"),"Workbench opens");
  assert(await page.eval(()=>document.querySelectorAll(".query-row").length>=3),"Real query rows load");
  assert(await page.eval(()=>document.documentElement.scrollWidth<=innerWidth),"Desktop has no horizontal overflow");
  await page.eval(()=>document.querySelector('[aria-label="Datasets"]').click());
  await sleep(300);
  assert(await page.eval(()=>document.querySelector("h1")?.textContent==="Dataset registry"),"Dataset navigation works");
  assert(await page.eval(()=>document.querySelectorAll("tbody tr").length===14),"All fourteen admitted inputs are visible");
  await page.screenshot({path:".local/ui-qa/datasets.jpg",fullPage:true});
  await page.eval(()=>document.querySelector('[aria-label="Experiments"]').click());
  await sleep(250);
  assert(await page.eval(()=>document.querySelector("h1")?.textContent==="Experiment ledger"),"Experiment ledger opens");
  assert(await page.eval(()=>document.querySelectorAll("tbody tr").length>=6),"Real experiment history is visible");
  await page.screenshot({path:".local/ui-qa/experiments.jpg",fullPage:true});
  await page.eval(()=>document.querySelector('[aria-label="Workbench"]').click());
  await page.eval(()=>Array.from(document.querySelectorAll("button")).find(b=>b.textContent.includes("Run evaluation"))?.click());
  await sleep(200);
  assert(await page.eval(()=>!!document.querySelector('[role="dialog"]')),"Bounded evaluation dialog opens");
  assert(await page.eval(()=>document.querySelector('[role="dialog"]').textContent.includes("paid API calls")),"Paid-call scope is disclosed");
  await page.eval(()=>document.querySelector('[aria-label="Close evaluation dialog"]').click());
  await page.eval(()=>document.querySelector(".copilot-toggle").click());
  await sleep(1800);
  assert(await page.eval(()=>!!document.querySelector('[aria-label="Research copilot"]')),"CopilotKit research panel opens");
  if(process.argv.includes("--chat")){
    await page.eval(()=>document.querySelector(".chat-welcome button")?.click());
    for(let i=0;i<80;i++){
      const state=await page.eval(()=>({evidence:!!document.querySelector(".evidence-card"),error:document.querySelector(".error-message")?.textContent,busy:document.querySelector(".chat-messages")?.textContent.includes("Reading experiment evidence")}));
      if(state.error)throw Error("Copilot error: "+state.error.slice(0,500));
      if(state.evidence&&!state.busy){report.chat=true;break;}
      await sleep(1000);
    }
    assert(report.chat,"Copilot invokes read-only tool and renders measured query evidence");
    await page.screenshot({path:".local/ui-qa/copilot.jpg",fullPage:true});
  }
  await page.eval(()=>document.querySelector('[aria-label="Close copilot"]').click());
  await page.setViewport({width:390,height:844});
  await sleep(300);
  assert(await page.eval(()=>document.documentElement.scrollWidth<=innerWidth),"Phone has no horizontal overflow");
  await page.screenshot({path:".local/ui-qa/mobile.jpg",fullPage:true});
  assert(report.errors.length===0,"No uncaught browser exceptions");
} finally {
  writeFileSync(".local/ui-qa/report.json",JSON.stringify(report,null,2));
  await browser.close();
}
