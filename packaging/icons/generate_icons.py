"""生成安装包图标（PNG / ICO / ICNS）。不解析 SVG，用 Pillow 绘制与品牌色一致的 Q 标。"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# packaging/icons/generate_icons.py → 仓库根
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent

_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)


def _load_font(font_size: int) -> ImageFont.ImageFont:
    """按平台常见路径加载字体，避免 CI 上仅凭字体名找不到文件。"""
    for path in _FONT_CANDIDATES:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, font_size)
            except OSError:
                continue
    return ImageFont.load_default()


def _draw_icon(size: int) -> Image.Image:
    """绘制圆角蓝底 + 白字 Q + 右上角绿点。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = int(size * 0.25)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=(37, 99, 235, 255))
    # 右上角状态点
    r = max(3, int(size * 0.1))
    cx, cy = int(size * 0.76), int(size * 0.23)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(52, 211, 153, 255))
    font_size = int(size * 0.55)
    font = _load_font(font_size)
    text = "Q"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) / 2 - bbox[0]
    y = (size - th) / 2 - bbox[1] - size * 0.03
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    return img


def write_png(path: Path, size: int = 1024) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _draw_icon(size).save(path, format="PNG")


def write_ico(path: Path) -> None:
    """Windows 多尺寸 ICO。"""
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [_draw_icon(s) for s in sizes]
    images[0].save(path, format="ICO", sizes=[(s, s) for s in sizes], append_images=images[1:])


def write_icns(path: Path) -> None:
    """macOS ICNS：优先 iconutil，否则退回单张 PNG 改后缀（部分工具仍能用）。"""
    if sys.platform != "darwin" or shutil.which("iconutil") is None:
        png = path.with_suffix(".png")
        if not png.is_file():
            write_png(png, 1024)
        shutil.copyfile(png, path)
        return
    iconset = path.parent / "OneQMultiA.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir(parents=True)
    mapping = {
        16: ["icon_16x16.png"],
        32: ["icon_16x16@2x.png", "icon_32x32.png"],
        64: ["icon_32x32@2x.png"],
        128: ["icon_128x128.png"],
        256: ["icon_128x128@2x.png", "icon_256x256.png"],
        512: ["icon_256x256@2x.png", "icon_512x512.png"],
        1024: ["icon_512x512@2x.png"],
    }
    for size, names in mapping.items():
        img = _draw_icon(size)
        for name in names:
            img.save(iconset / name, format="PNG")
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(path)], check=True)
    shutil.rmtree(iconset, ignore_errors=True)


def main() -> None:
    png = OUT / "OneQMultiA.png"
    ico = OUT / "OneQMultiA.ico"
    icns = OUT / "OneQMultiA.icns"
    write_png(png, 1024)
    write_ico(ico)
    write_icns(icns)
    print(f"wrote {png}")
    print(f"wrote {ico}")
    print(f"wrote {icns}")


if __name__ == "__main__":
    main()
