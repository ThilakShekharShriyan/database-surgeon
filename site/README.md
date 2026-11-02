# Database Surgeon — Research site

**Live:** https://thilakshekharshriyan.github.io/database-surgeon/

Static companion to the Next.js `/research` dashboard. Same measured snapshot — no API keys, no chart CDN.

```sh
bash scripts/site/sync.sh
python3 -m http.server 8766 --bind 127.0.0.1 --directory site
```

Open http://127.0.0.1:8766. Deploy is automatic via `.github/workflows/pages.yml` on pushes that touch `site/**`.
