"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import "../app/product.css";

function Mark() {
  return (
    <svg width="22" height="22" viewBox="0 0 32 32" fill="none" aria-hidden>
      <path
        d="M5 9c0-3 22-3 22 0v14c0 4-22 4-22 0V9Zm0 0c0 4 22 4 22 0M5 16c0 3 11 4 16 2m-6 7 11-13 3 3-11 13-4 1Z"
        stroke="currentColor"
        strokeWidth="1.5"
      />
    </svg>
  );
}

export function ProductShell({
  children,
  ctaHref = "/demo",
  ctaLabel = "Live surgery",
}: {
  children: ReactNode;
  ctaHref?: string;
  ctaLabel?: string;
}) {
  const path = usePathname() || "/";
  const links = [
    { href: "/", label: "Home" },
    { href: "/research", label: "Scoreboard" },
    { href: "/demo", label: "Surgery" },
  ];
  return (
    <div className="ps">
      <header className="ps-nav">
        <Link href="/" className="ps-brand">
          <Mark /> Database Surgeon
        </Link>
        <nav className="ps-links" aria-label="Product">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={
                l.href === "/"
                  ? path === "/"
                    ? "active"
                    : ""
                  : path.startsWith(l.href)
                    ? "active"
                    : ""
              }
            >
              {l.label}
            </Link>
          ))}
          <a href="/research/FORGE_RESEARCH.md" target="_blank" rel="noreferrer">
            Write-up
          </a>
        </nav>
        <Link href={ctaHref} className="ps-cta">
          {ctaLabel}
        </Link>
      </header>
      {children}
    </div>
  );
}
