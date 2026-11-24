"""Turn project screenshots into small, embeddable JPEGs.

GitHub's image proxy won't let an SVG load other images, so screenshots are
resized here and inlined into the SVG as base64. Wide shots are cropped
from the top (where the interesting UI usually is); tall mobile shots are
centred on a blurred, darkened copy of themselves.
"""

from __future__ import annotations

import base64
import io

from PIL import Image, ImageEnhance, ImageFilter

SCALE = 1.5  # render at 1.5x the display size for sharp text on retina screens


def fit(data: bytes, w: int, h: int, quality: int = 74) -> str | None:
    """Return a data: URI with the image fitted to a w×h viewport."""
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:  # corrupt or unsupported file
        return None
    im = im.convert("RGB")
    W, H = int(w * SCALE), int(h * SCALE)
    ratio = im.width / im.height

    phone = im.width < 800 and ratio < 0.8
    if not phone:
        # Desktop (even full-page tall ones): fill the width, crop from the top.
        scale = max(W / im.width, H / im.height)
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        left = (im.width - W) // 2
        out = im.crop((left, 0, left + W, H))
    else:
        # Phone screenshot: contain, on a blurred background.
        bg_scale = max(W / im.width, H / im.height)
        bg = im.resize((round(im.width * bg_scale), round(im.height * bg_scale)), Image.LANCZOS)
        bl = (bg.width - W) // 2
        bt = (bg.height - H) // 2
        bg = bg.crop((bl, bt, bl + W, bt + H)).filter(ImageFilter.GaussianBlur(18))
        bg = ImageEnhance.Brightness(bg).enhance(0.45)
        fg_scale = (H * 0.94) / im.height
        fg = im.resize((round(im.width * fg_scale), round(im.height * fg_scale)), Image.LANCZOS)
        bg.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2))
        out = bg

    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
