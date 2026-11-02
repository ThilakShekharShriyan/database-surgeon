import "server-only";
export function loadProjectEnvironment() { /* Keys are loaded by scripts/next.mjs before Next starts; never traced into the build. */ }
export function sameOrigin(request: Request) {
  const origin=request.headers.get("origin");
  const host=request.headers.get("host");
  try { return !origin || (new URL(origin).host===host && ["localhost","127.0.0.1"].includes(new URL(origin).hostname)); } catch { return false; }
}
