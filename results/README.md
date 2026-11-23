# Results log

One row per published video, filled 7 days after it goes public.

- `type`: `long` or `short`
- `trigger`: `timely`, `evergreen` or `proven-topic`
- `clip_pct`: share of runtime that is third-party clips
- `linked_long_video_id` and `d7_clicks_to_long`: Shorts only
- `claims`: `none`, `claimed` or `blocked`
- `verdict`: `double`, `keep` or `drop`, set at the batch review
- `lesson`: one line, plain words

Muse appends rows from the daily analytics sweep. The batch review in
`PLAYBOOK.md` reads this file.
