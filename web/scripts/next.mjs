import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { spawn } from "node:child_process";
for (const filename of [".env.local", ".env"]) {
  try {
    for (const line of readFileSync(resolve(process.cwd(), "..", filename),"utf8").split(/\r?\n/)) {
      const match=line.match(/^([A-Z_][A-Z0-9_]*)=(.*)$/);
      if(!match || process.env[match[1]]!==undefined) continue;
      let value=match[2].trim();
      if ((value.startsWith('"')&&value.endsWith('"'))||(value.startsWith("'")&&value.endsWith("'"))) value=value.slice(1,-1);
      process.env[match[1]]=value;
    }
  } catch {}
}
process.env.COPILOTKIT_TELEMETRY_DISABLED="true";
const mode=process.argv[2]||"dev";
if(!["dev","build","start"].includes(mode)) throw Error("Unknown Next.js mode");
const args=[resolve("node_modules/next/dist/bin/next"),mode];
const port=process.env.SURGEON_WEB_PORT||"3100";
if(!/^\d+$/.test(port)||Number(port)<1||Number(port)>65535) throw Error("SURGEON_WEB_PORT must be 1–65535");
if(mode!=="build") args.push("--hostname","127.0.0.1","--port",port);
const child=spawn(process.execPath,args,{stdio:"inherit",env:process.env});
for(const signal of ["SIGINT","SIGTERM"]) process.on(signal,()=>child.kill(signal));
child.on("exit",code=>process.exit(code??1));
