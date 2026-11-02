import type { NextConfig } from "next";
const config: NextConfig = { distDir: process.env.NEXT_BUILD_DIR || ".next", devIndicators: false, serverExternalPackages: ["@copilotkit/runtime"], experimental: { proxyClientMaxBodySize: "1mb" } };
export default config;
