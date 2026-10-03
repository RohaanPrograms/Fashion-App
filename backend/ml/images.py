"""Stage 3 — shrink product photos before they go anywhere near Storage.

Supabase's free tier gives 1 GB of storage and limited monthly bandwidth, and a
swipe feed loads images continuously. The originals are ~135 KB each (~700 MB
for 5,000); at 400px wide in WebP they are ~20 KB, and still sharp on a phone.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def resize_to_webp(source: Path, dest: Path, max_width: int) -> None:
    """Resize to at most `max_width` wide and write as WebP.

    Aspect ratio is preserved. Images already narrower than `max_width` are
    converted but not upscaled — upscaling costs bytes and adds no detail.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image = image.convert("RGB")
        if image.width > max_width:
            height = round(image.height * max_width / image.width)
            image = image.resize((max_width, height), Image.LANCZOS)
        image.save(dest, format="WEBP", quality=80, method=6)
