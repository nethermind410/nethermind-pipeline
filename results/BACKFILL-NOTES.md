# Backfill notes — 23 Nov 2026 (Muse)

First backfill of `log.csv`, done at Courtney's approval (he owns the call;
Muse owns this file). Base files (`log.csv` header, this folder's `README.md`)
were taken from GitHub `main` after the PR #2 merge, not from the local clone.

## Rules applied

- Rows: every PUBLIC long-form on @nnethermind, plus Shorts with a documented
  Related Video link to a long-form. The public set was verified live through
  the YouTube Data API (uploads playlist + `videos.list`), not taken from any
  hand list: 79 uploads, 47 public, 5 of them long-form.
- `date_published` is the API `publishedAt` date (UTC). AEDT is UTC+11, so a
  video the learning log dates 23 Nov in Sydney can read 2026-11-22 here.
- A cell with no real source stays blank. Nothing was estimated.
- The `d7_*` columns mean the video's first-7-days figures. Studio readings
  taken on other days exist for three rows (below) and were NOT entered —
  putting a day-0 or day-13 snapshot in a d7 column would corrupt the
  scoreboard. Those snapshots are recorded here instead, and the daily sweep
  will fill true d7 rows for future publishes.
- `thumbnail_winner` is blank on every row: no Test & Compare result has been
  recorded for any of these videos yet.
- `claims` is blank on every row: no claim record exists for any of them in
  the studio records (the one blocked video, the Bleach long-form
  eh6MQeyGqOE, is Private, so it has no row).
- `verdict` / `lesson` are blank on every row: both are set at the batch
  review, which has not run yet.

## Row by row

### fwBrTEHKDGU — "Who Is Marvel's Sun King?" (long, 2026-11-03)
- Identity/date/length/lifetime views (114): YouTube Data API, 23 Nov 2026.
- All d7 cells missing: the studio's sweeps never recorded this video (it
  predates the current studio system). No source exists; left blank.

### 9uW5gABPMww — "Bruce Wayne Isn't the Mask. Neither Is Batman." (long, 2026-11-10)
- Identity/date/length/lifetime views (807): YouTube Data API, 23 Nov 2026.
- d7 cells missing. The only Studio reading on record (Weekly bottleneck
  review, 23 Nov 2026) is a day-13 snapshot, not day 7: AVD 2:36, 21%
  average viewed, 46.2% still watching at 0:30. Recorded here, not in the
  d7 columns.

### 4CUNKFGkDEY — Anime Rain Ambience #1 (long, 2026-11-21)
- Identity/date/length/lifetime views (1): YouTube Data API, 23 Nov 2026.
- `clip_pct` = 0: the learning log's long-form lane entry (21 Nov 2026)
  defines the ambient series as "original visuals/music only".
- d7 cells missing: published 21 Nov, so its first 7 days have not elapsed
  and no per-video Studio figures were recorded for it.

### neNNwqFEGsI — Anime Rain Ambience #2 (long, 2026-11-21)
- Same as #1: API identity (2 lifetime views), `clip_pct` = 0 from the same
  learning-log source, d7 not yet elapsed / not recorded.

### 2FrDd8VD48U — "Why Did Luffy Stop Using 2nd Gear?" (long, 2026-11-22 UTC / 23 Nov AEDT)
- Identity/date/length/lifetime views (12): YouTube Data API, 23 Nov 2026.
- d7 cells missing: the video had been public under an hour at the only
  recorded check (Analytics sweep, 23 Nov 2026 ~08:03 AEDT): 24 impressions,
  0.0% CTR, 0 views in Analytics (Content list showed 1 view), 0.0 watch
  hours, 0 subs. That is a day-0 snapshot, recorded here, not in the d7
  columns. Its true d7 row can be filled by the sweep on 30 Nov 2026.

### pmpvvpfaXLs — "I Waited 13 Years For GTA 6…" (short, vicerat, 2026-11-19 UTC / 20 Nov AEDT)
- Included at the brief's explicit instruction (vicerat's only public video
  and the channel's anchor), even though it has no long-form link:
  `linked_long_video_id` and `d7_clicks_to_long` are blank.
- Identity/date/length/lifetime views (59): YouTube Data API, 23 Nov 2026.
- d7 cells missing. The Analytics sweep (23 Nov 2026) recorded a day-~4
  snapshot: 60 views at check time, 0.2 watch hours, 0 likes, 0 comments,
  +0 subs, 45.4% stayed to watch. Recorded here, not in the d7 columns.

## Public Shorts with NO row — and why

The log's Short rows are for Shorts linked to a long-form. No public
nnethermind Short has a documented Related Video link to a long-form:

- **BHaJECuQav8** (Nika Short) — it is a link *target* (the Ichigo Ep 1
  upload pack points its Related Video here), but no record shows it linking
  onward to a long-form.
- **yG0rBgYrIFg** (Ichigo Ep 1) — its Related Video points to the Nika Short
  (anime-vs-real rebuild BUILD-REPORT), i.e. Short → Short, so it has no
  `linked_long_video_id` to enter.
- **Ve1Av4XiHrY** (Sukuna v7) and **Dy2xYXiIbto** (Sukuna Part 2) — public,
  but no Related Video link is recorded for either.
- Every documented Short → long-form pair is still Private (44rBJraeTgQ →
  Gci4f_5m_Q0, WolDI58Q_Do → 2FrDd8VD48U, ehHZjsil3yA → eh6MQeyGqOE), and
  the Gear Second paired Short was never uploaded. Those rows land when the
  videos go public.
- The remaining ~36 public Shorts are pre-studio uploads with no funnel
  records at all.

If Courtney wants rows for public Shorts regardless of links, say the word
and they will be added — the API identity data is already pulled.
