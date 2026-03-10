#!/usr/bin/env python3
from __future__ import annotations
from glob import glob
import json
from pathlib import Path
from typing import Iterable

try:
    from PIL import Image, ImageOps
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Pillow が必要です。\n"
        "インストール例: python3 -m pip install pillow"
    ) from exc

ROOT = Path(__file__).resolve().parent
IMAGES_DIR = ROOT / "images"
OUT_DIR = IMAGES_DIR / "optimized"

# 2カラムの実表示幅がだいたい 320〜360px なので、
# grid 用は 360/720、overlay 用は 1200 を作る。
SHOWCASE_WIDTHS = (360, 720, 1200)
AVATAR_WIDTHS = (48, 96, 192)
WEBP_QUALITY = 78
WEBP_METHOD = 6


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def fit_width(size: tuple[int, int], target_width: int) -> tuple[int, int]:
    src_w, src_h = size
    if src_w <= target_width:
        return src_w, src_h
    ratio = target_width / src_w
    target_height = max(1, int(round(src_h * ratio)))
    return target_width, target_height


def resize_and_save_webp(src_path: Path, dst_path: Path, target_width: int) -> tuple[int, int]:
    with Image.open(src_path) as im:
        im = ImageOps.exif_transpose(im)
        target_size = fit_width(im.size, target_width)
        if target_size != im.size:
            im = im.resize(target_size, Image.Resampling.LANCZOS)

        save_kwargs = {
            "format": "WEBP",
            "quality": WEBP_QUALITY,
            "method": WEBP_METHOD,
            "optimize": True,
        }

        # 透過 PNG にも対応
        if "A" in im.getbands():
            save_kwargs["alpha_quality"] = 90

        ensure_dir(dst_path.parent)
        im.save(dst_path, **save_kwargs)
        return im.size


def make_srcset(outputs: Iterable[dict[str, object]]) -> str:
    return ", ".join(
        f"{item['path']} {item['width']}w" for item in outputs
    )


def build_manifest() -> dict[str, dict[str, object]]:
    manifest: dict[str, dict[str, object]] = {}

    if not IMAGES_DIR.exists():
        raise SystemExit(f"images ディレクトリが見つかりません: {IMAGES_DIR}")

    for src_path in sorted(IMAGES_DIR.glob("*.png")):
        stem = src_path.stem
        widths = AVATAR_WIDTHS if stem == "user-image" else SHOWCASE_WIDTHS

        outputs: list[dict[str, object]] = []
        seen_actual_widths: set[int] = set()

        for requested_width in widths:
            with Image.open(src_path) as probe:
                probe = ImageOps.exif_transpose(probe)
                actual_width, actual_height = fit_width(probe.size, requested_width)

            if actual_width in seen_actual_widths:
                continue

            out_name = f"{stem}-{actual_width}.webp"
            out_path = OUT_DIR / out_name
            saved_width, saved_height = resize_and_save_webp(src_path, out_path, requested_width)
            seen_actual_widths.add(saved_width)
            outputs.append({
                "width": saved_width,
                "height": saved_height,
                "path": f"./images/optimized/{out_name}",
            })

        outputs.sort(key=lambda item: int(item["width"]))

        manifest[src_path.name] = {
            "original": f"./images/{src_path.name}",
            "outputs": outputs,
            "srcset": make_srcset(outputs),
            "smallest": outputs[0]["path"],
            "largest": outputs[-1]["path"],
        }

    return manifest


def main() -> None:
    manifest = build_manifest()
    manifest_path = OUT_DIR / "manifest.json"
    ensure_dir(manifest_path.parent)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Done: {len(manifest)} files optimized")
    print(f"Manifest: {manifest_path}")
    print("\nExample (showcase black/white pair):")
    for key in sorted(manifest):
        if key.endswith("_black.png"):
            dark_key = key.replace("_black.png", "_white.png")
            if dark_key in manifest:
                print(f"  light smallest: {manifest[key]['smallest']}")
                print(f"  light srcset  : {manifest[key]['srcset']}")
                print(f"  light preview : {manifest[key]['largest']}")
                print(f"  dark smallest : {manifest[dark_key]['smallest']}")
                print(f"  dark srcset   : {manifest[dark_key]['srcset']}")
                print(f"  dark preview  : {manifest[dark_key]['largest']}")
                break


if __name__ == "__main__":
    main()
