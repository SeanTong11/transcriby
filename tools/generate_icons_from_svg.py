#!/usr/bin/env python3
"""Generate Transcriby icon assets from an SVG source.

Outputs:
- Icona-{size}.png for standard sizes
- icona.png (256x256)
- Icona.ico (contains exact PNG frames for Windows)
"""

from __future__ import annotations

import argparse
import io
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path


DEFAULT_SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256, 1024]
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate icon assets from SVG")
    parser.add_argument(
        "--svg",
        default="transcriby/resources/Icona-clean.svg",
        help="Path to SVG source",
    )
    parser.add_argument(
        "--out-dir",
        default="transcriby/resources",
        help="Output directory for generated icon assets",
    )
    parser.add_argument(
        "--supersample",
        type=int,
        default=8,
        help="Render SVG at size*supersample before downsampling (default: 8)",
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=0.06,
        help="Transparent padding ratio around icon (0.0-0.45, default: 0.06)",
    )
    parser.add_argument(
        "--no-small-sharpen",
        action="store_true",
        help="Disable mild sharpening for <=48px outputs",
    )
    return parser.parse_args()


def render_svg_png(svg_path: Path, svg_bytes: bytes, size: int, supersample: int) -> bytes:
    render_size = max(size, size * max(1, supersample))

    # Preferred: CairoSVG
    try:
        import cairosvg

        return cairosvg.svg2png(bytestring=svg_bytes, output_width=render_size, output_height=render_size)
    except ModuleNotFoundError:
        pass

    # Fallback: Inkscape CLI
    inkscape = shutil.which("inkscape")
    if inkscape:
        with tempfile.TemporaryDirectory(prefix="icona-svg-") as td:
            out_png = Path(td) / f"icon-{size}.png"
            cmd = [
                inkscape,
                str(svg_path),
                "--export-type=png",
                f"--export-width={render_size}",
                f"--export-height={render_size}",
                f"--export-filename={out_png}",
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return out_png.read_bytes()

    raise ModuleNotFoundError("cairosvg")


def ensure_rgba_image(png_bytes: bytes):
    from PIL import Image

    return Image.open(io.BytesIO(png_bytes)).convert("RGBA")


def normalize_icon_canvas(img, size: int, padding: float):
    from PIL import Image, ImageOps

    padding = max(0.0, min(0.45, padding))
    alpha = img.getchannel("A")
    bbox = alpha.getbbox()

    if bbox is None:
        return Image.new("RGBA", (size, size), (0, 0, 0, 0))

    cropped = img.crop(bbox)
    inner = max(1, int(round(size * (1.0 - 2.0 * padding))))
    fitted = ImageOps.contain(cropped, (inner, inner), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = (size - fitted.width) // 2
    y = (size - fitted.height) // 2
    canvas.paste(fitted, (x, y), fitted)
    return canvas


def maybe_sharpen_small_icon(img, size: int, enable: bool):
    from PIL import ImageFilter

    if not enable:
        return img
    if size <= 24:
        return img.filter(ImageFilter.UnsharpMask(radius=0.45, percent=65, threshold=2))
    if size <= 48:
        return img.filter(ImageFilter.UnsharpMask(radius=0.55, percent=55, threshold=2))
    return img


def image_to_png_bytes(img) -> bytes:
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def write_ico_exact_frames(ico_path: Path, png_frames: dict[int, bytes]) -> None:
    entries = []
    chunks = []
    offset = 6 + 16 * len(ICO_SIZES)

    for size in ICO_SIZES:
        frame = png_frames[size]
        wh = 0 if size == 256 else size
        entry = struct.pack(
            "<BBBBHHII",
            wh,  # width
            wh,  # height
            0,   # color count
            0,   # reserved
            1,   # planes
            32,  # bpp
            len(frame),
            offset,
        )
        entries.append(entry)
        chunks.append(frame)
        offset += len(frame)

    header = struct.pack("<HHH", 0, 1, len(ICO_SIZES))
    ico_blob = header + b"".join(entries) + b"".join(chunks)
    ico_path.write_bytes(ico_blob)


def main() -> int:
    args = parse_args()
    svg_path = Path(args.svg)
    out_dir = Path(args.out_dir)
    supersample = max(1, args.supersample)
    padding = args.padding
    small_sharpen = not args.no_small_sharpen

    if not svg_path.exists():
        raise SystemExit(f"SVG not found: {svg_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    svg_bytes = svg_path.read_bytes()

    png_frames: dict[int, bytes] = {}

    for size in DEFAULT_SIZES:
        raw_png = render_svg_png(svg_path, svg_bytes, size, supersample)
        img = ensure_rgba_image(raw_png)
        img = normalize_icon_canvas(img, size, padding)
        img = maybe_sharpen_small_icon(img, size, small_sharpen)
        png = image_to_png_bytes(img)
        png_frames[size] = png
        (out_dir / f"Icona-{size}.png").write_bytes(png)

    # Runtime alias used by app.
    (out_dir / "icona.png").write_bytes(png_frames[256])

    # Windows icon with exact per-size PNG frames.
    write_ico_exact_frames(out_dir / "Icona.ico", png_frames)

    print(f"Generated icon assets from: {svg_path}")
    print(f"Output directory: {out_dir}")
    print(f"Options: supersample={supersample}, padding={padding}, small_sharpen={small_sharpen}")
    print("Files: Icona-{16..1024}.png, icona.png, Icona.ico")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ModuleNotFoundError as exc:
        missing = str(exc).split("'")[1] if "'" in str(exc) else str(exc)
        print(f"Missing dependency: {missing}")
        print("Install with one command (or install Inkscape and rerun):")
        print("  uv run --with cairosvg --with pillow python tools/generate_icons_from_svg.py")
        raise
