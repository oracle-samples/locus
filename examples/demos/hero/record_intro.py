# ruff: noqa: ASYNC221, S603, S607
"""Render intro.html → 6-second MP4 via Playwright."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

from playwright.async_api import async_playwright


HERE = Path(__file__).parent
PAGE = HERE / "intro.html"
FRAMES = HERE / "frames"
OUT_MP4 = HERE / "intro.mp4"

DURATION_MS = 6200  # 6 s logo + buffer
FPS = 24
FRAME_INTERVAL_MS = int(1000 / FPS)


async def main() -> None:
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir()

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": 1500, "height": 800},
            device_scale_factor=2,
        )
        page = await ctx.new_page()
        await page.goto(f"file://{PAGE.resolve()}")
        await page.wait_for_load_state("networkidle")

        n = DURATION_MS // FRAME_INTERVAL_MS
        for i in range(n):
            await page.screenshot(path=str(FRAMES / f"frame_{i:05d}.png"))
            await page.wait_for_timeout(FRAME_INTERVAL_MS)

        await ctx.close()
        await browser.close()

    subprocess.check_call(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-framerate",
            str(FPS),
            "-i",
            str(FRAMES / "frame_%05d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "scale=1500:800,format=yuv420p",
            "-movflags",
            "+faststart",
            str(OUT_MP4),
        ]
    )
    print(f"Wrote {OUT_MP4} ({OUT_MP4.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    asyncio.run(main())
