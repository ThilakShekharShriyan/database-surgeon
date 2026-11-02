import type { Metadata } from "next";
import { Providers } from "./providers";
import "@copilotkit/react-core/v2/styles.css";
import "./globals.css";
export const metadata: Metadata = {title:"Database Surgeon — Research observatory",description:"Measured PostgreSQL rewrites: paired statistics, correctness evidence, cost, latency and query-level analysis."};
export default function RootLayout({children}:{children:React.ReactNode}) {
  return <html lang="en" data-theme="dark"><body><Providers>{children}</Providers></body></html>;
}
