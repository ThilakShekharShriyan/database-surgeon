# Research companion

Buildless, interactive research report backed by the same snapshot as the Next.js
research dashboard. No model API, database service, remote fonts or chart dependency.

From the repository root:

```sh
bash scripts/site/sync.sh
python3 -m http.server 8766 --bind 127.0.0.1 --directory site
```

Open http://127.0.0.1:8766. Snapshot export reads recorded JSONL files only and
makes no paid calls. The page includes split/completeness filters, five data
views, paired McNemar tests, template sensitivity, resource intervals and downloads.
Local app links require the separate production demo server on port 3101.

The existing GitHub Pages workflow can publish the static directory on a later
push; this frontend task does not publish it. See `docs/DEMO.md` for the walkthrough.
