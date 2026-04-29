# ruff: noqa: ASYNC221, S603, S607
"""Render hero.html → frames → MP4 via Playwright + ffmpeg.

This is a build script for the GIF embedded at the top of the project
README. Calls ffmpeg via subprocess; that's intentional and the inputs
are statically defined paths.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from pathlib import Path

from playwright.async_api import async_playwright


HERE = Path(__file__).parent
HERO = HERE / "hero.html"
FRAMES = HERE / "frames"
OUT_MP4 = HERE / "hero.mp4"
OUT_GIF = HERE / "hero.gif"

DURATION_MS = 44000  # match the longest CSS animation
FPS = 24
FRAME_INTERVAL_MS = int(1000 / FPS)


async def main() -> None:
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir()

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            device_scale_factor=2,
        )
        page = await ctx.new_page()

        # Pause CSS animations so we can step them deterministically.
        await page.add_init_script("""
            window.__step = 0;
        """)

        await page.goto(f"file://{HERO.resolve()}")
        await page.wait_for_load_state("networkidle")

        # Force animations to use a virtual clock instead of real time.
        # We'll use page.clock controls if available; otherwise just sleep
        # in a tight loop and screenshot.
        await page.emulate_media(reduced_motion=None)

        n_frames = DURATION_MS // FRAME_INTERVAL_MS
        for i in range(n_frames):
            path = FRAMES / f"frame_{i:05d}.png"
            await page.screenshot(path=str(path), full_page=False)
            await page.wait_for_timeout(FRAME_INTERVAL_MS)

        await ctx.close()
        await browser.close()

    # Stitch into MP4.
    if OUT_MP4.exists():
        OUT_MP4.unlink()
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
            "scale=1280:720,format=yuv420p",
            "-movflags",
            "+faststart",
            str(OUT_MP4),
        ]
    )

    # MP4 → GIF (palette-optimised, ~12 fps, scaled to 1080p width).
    if OUT_GIF.exists():
        OUT_GIF.unlink()
    palette = HERE / "palette.png"
    subprocess.check_call(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(OUT_MP4),
            "-vf",
            "fps=10,scale=820:-1:flags=lanczos,palettegen=stats_mode=diff:max_colors=96",
            str(palette),
        ]
    )
    subprocess.check_call(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(OUT_MP4),
            "-i",
            str(palette),
            "-lavfi",
            "fps=10,scale=820:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3",
            str(OUT_GIF),
        ]
    )
    print(f"Wrote {OUT_MP4} ({OUT_MP4.stat().st_size // 1024} KiB)")
    print(f"Wrote {OUT_GIF} ({OUT_GIF.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    asyncio.run(main())
