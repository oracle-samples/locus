# Hero animation

The 44-second hero shown at the top of the project README is generated
from a single HTML page and recorded with Playwright + ffmpeg. It is
not a screen capture — every frame is deterministic, so the file size
is small and the animation is crisp at any resolution.

## Files

- [`hero.html`](hero.html) — the page (CSS animations, no JS).
- [`record.py`](record.py) — Playwright loads the page, takes 24-fps
  PNG frames for 44 s, ffmpeg stitches into MP4, then a palettegen
  pass produces the 14-fps GIF.

The compiled outputs live at:

- [`docs/img/hero.gif`](../../../docs/img/hero.gif) (~1.5 MB)
- [`docs/img/hero.mp4`](../../../docs/img/hero.mp4) (~450 KB — preferred for sites that play video)

## Re-render

```bash
pip install playwright
python -m playwright install chromium
brew install ffmpeg

cd examples/demos/hero
python record.py
```

Outputs `hero.mp4` and `hero.gif` next to the script.

## What it shows

| Beat | Time | Content |
|---|---|---|
| Title | 0–5 s | Locus mark + "Build agents that finish." + service badges |
| Code | 5–24 s | `demo.py` snippet, three red-bordered callouts pulsing in turn over `OracleVectorStore`, `idempotent=True`, `reflexion=True` |
| Run | 23–41 s | Terminal trace: chain-of-thought per iteration, real Oracle 26ai rows with scores, Reflexion confidence, idempotent email, green RESULT box |
| Outcome | 36–44 s | "✓ Brief sent. 4 iterations · 3 tools · 5 services · powered by locus on Oracle 26ai" |

## Editing

Adjust timings in `hero.html` (`animation-delay` on each `.hl-*`,
`.co-*`, `.code-stage`, `.term-stage`, `.victory`) and update
`DURATION_MS` in `record.py` to match the longest delay + buffer.
