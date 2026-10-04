# Nethermind App — Ready to Run

## Dashboard Live

http://127.0.0.1:8765

## System State

- 0 assets, 1 job, 0 approvals
- Fresh start — ready for a video source
- 5 video files uploaded:
  - `9bb822f521e5402a97d2a96f170c6b58_MOVI0000.mp4`
  - `6364676a18f849a98c785e5a22e219f0_2025-12-30 17-59-23.mov`
  - `2215432f9aba42bfab10887f644f694c_MOVI0000.mp4`
  - `6ec124495eea4d58ba9123cd8935815f_MOVI0000.mp4`
  - `dab41162b8c846ac8081df76d1ab9e7c_MOVI0000.mp4`

## How to Run a Pipeline

```bash
# Start the dashboard
cd /Users/courtneyblyde/nethermind-pipeline/clipping-farm
.venv/bin/python -m clipping_farm.nethermind_app --port 8765

# Then open http://127.0.0.1:8765
# Click "Run Pipeline" and enter the source_id
```

## What Happens

1. **Trending** — finds hot moments in the video
2. **Script** — writes a script for the best moment
3. **Referator** — builds the production pack
4. **Approval** — waits for you to approve the script
5. **Production** — renders the clips
6. **QC** — quality checks before publish
7. **Brain** — learns what works

## Mr Beast Verdict

He'd use it for: ideation, scripting, QC, learning
He wouldn't use it for: full production, publishing (human decides), analytics (needs real data)