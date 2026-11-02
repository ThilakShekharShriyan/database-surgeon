import type { Metadata } from "next";
import { Providers } from "./providers";
import "@copilotkit/react-core/v2/styles.css";
import "./globals.css";
export const metadata: Metadata = {
  title: "Database Surgeon",
  description: "Verify-or-abstain PostgreSQL rewrites on Fireworks + NVIDIA Nemotron. Sealed bench: 0 incorrect, frontier-level accepts, measured SQL speedups.",
};
export default function RootLayout({children}:{children:React.ReactNode}) {
  return <html lang="en" data-theme="dark"><body><Providers>{children}</Providers></body></html>;
}
