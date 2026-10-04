## Issue identified

The `::preview{file="..."}` directive requires a registered TRANSCRIPT_DIRECTIVE_AREA plugin. The Hermes desktop app has no built-in HTML preview directive — only `hermes-talk` and `hermes-office` are installed as desktop plugins, neither handles `::preview`.

So `::preview{file="growth_workflow.html"}` won't render. You need to open the file another way.

## Quickest path to see the growth workflow dashboard

**Option A: Open directly in browser**
```bash
open /Users/courtneyblyde/nethermind-pipeline/drafts/growth_workflow.html
```

**Option B: Serve from the existing Nethermind App** (port 8765) — add a static route for drafts. The nethermind_app.py serves DASHBOARD_HTML hardcoded; we'd need to patch it to serve files from the drafts folder. Takes ~5 min.

**Option C: Use the existing dashboard at localhost:8765** — it's running right now. Open that URL in a browser. It's the factory-floor card view (not the growth one, but it works).

## Which route?

A = see the growth draft immediately (browser)  
B = embed growth draft into the Nethermind App (so buttons work, data wires)  
C = use current dashboard as-is  

Pick one and I'll execute it. No more "nothing generated" — we'll make it real.