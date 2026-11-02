# Dependency audit: local workbench

Checked November 1, 2026 PT after installing CopilotKit 1.83.0 and Next.js 16.4.3.

npm audit reports 34 package entries: 22 high, 6 moderate and 6 low. These include propagated findings, not 34 independent root vulnerabilities. The direct Zod4 installation is patched, while several CopilotKit/AG-UI paths require Zod3.

| Root | Installed path / issue | Why not blindly override |
| --- | --- | --- |
| Zod | Nested 3.25.76; direct 4.6.7 is outside the affected range | No verified 3.x backport; replacing Zod3 with Zod4 can break consumers |
| @hono/node-server | 1.19.17, fixed line reported at 2.1.3 | Outside current dependency range; static-serving advisory requires reachability review |
| graphql-scalars | 1.26.0, fixed line reported at 2.0.1 | Current runtime/type-graphql uses 1.x; current app does not expose the affected PhoneNumber scalar |
| KaTeX | 0.16.47, fixed line reported at 0.18.2 | Outside current CopilotKit range |
| Undici / Busboy | Legacy provider utility dependencies | Current selected OpenAI SDK3 provider path is separate; no verified compatible patches for all legacy consumers |

Sources:
- [Zod advisory](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5)
- [Hono advisory](https://github.com/advisories/GHSA-rmxm-3fg6-px4f)
- [GraphQL scalar advisory](https://github.com/advisories/GHSA-x8rm-f576-gq67)
- Reproduce with npm audit in web/.

The Next.js/React versions were not among the observed audit findings; that is not a claim that all application paths are secure.

Controls in this demo: loopback-only servers, same-origin mutation checks, model allowlist, bounded benchmark requests, a 64-KiB streamed chat-body cap, bounded chat message/context/tool counts, read-only assistant tools, server-only keys, and disabled CopilotKit telemetry.

Do not run npm audit fix --force: it proposed a CopilotKit downgrade while leaving other incompatible findings. Before exposing this app publicly, revisit maintained patched versions, remove unused dependency surfaces where feasible, and perform authentication/authorization and application-specific review.
