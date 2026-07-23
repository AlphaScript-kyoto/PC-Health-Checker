"""アプリアイコン生成: 黒背景を透過し PNG / ICO を作る。"""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets" / "icon-source.png"
ASSETS = ROOT / "assets"
BUILD = ROOT / "build"


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    BUILD.mkdir(exist_ok=True)

    img = Image.open(SRC).convert("RGBA")
    pixels = img.load()
    assert pixels is not None
    width, height = img.size

    # ほぼ黒の背景を透過（ハートとモニタの線は残す）
    for y in range(height):
        for x in range(width):
            r, g, b, _a = pixels[x, y]
            if r < 28 and g < 28 and b < 28:
                pixels[x, y] = (0, 0, 0, 0)

    bbox = img.getbbox()
    if bbox:
        pad = 8
        left = max(0, bbox[0] - pad)
        top = max(0, bbox[1] - pad)
        right = min(width, bbox[2] + pad)
        bottom = min(height, bbox[3] + pad)
        img = img.crop((left, top, right, bottom))

    side = max(img.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    ox = (side - img.size[0]) // 2
    oy = (side - img.size[1]) // 2
    square.paste(img, (ox, oy), img)

    master = square.resize((512, 512), Image.Resampling.LANCZOS)
    master.save(ASSETS / "icon.png", "PNG")
    master.save(BUILD / "icon.png", "PNG")

    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        square.resize((size, size), Image.Resampling.LANCZOS).save(
            BUILD / f"icon-{size}.png",
            "PNG",
        )

    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    ico_images = [square.resize(size, Image.Resampling.LANCZOS) for size in ico_sizes]
    ico_path = BUILD / "icon.ico"
    ico_images[0].save(
        ico_path,
        format="ICO",
        sizes=ico_sizes,
        append_images=ico_images[1:],
    )
    shutil.copy2(ico_path, ASSETS / "icon.ico")
    print(f"OK: {ASSETS / 'icon.png'}")
    print(f"OK: {ico_path}")


if __name__ == "__main__":
    main()
