from __future__ import annotations

import argparse
import json
from pathlib import Path

import av
from PIL import Image, ImageDraw


def inspect_video(path: Path) -> tuple[dict, Image.Image]:
    with av.open(str(path)) as container:
        video = container.streams.video[0]
        audio = container.streams.audio[0] if container.streams.audio else None
        frames = []
        for frame in container.decode(video=0):
            frames.append(frame.to_image().convert("RGB"))
        if not frames:
            raise RuntimeError(f"No video frames in {path}")
        selected = frames[len(frames) // 2]
        info = {
            "path": str(path),
            "bytes": path.stat().st_size,
            "decoded_frames": len(frames),
            "width": video.width,
            "height": video.height,
            "average_rate": float(video.average_rate) if video.average_rate else None,
            "duration_seconds": float(video.duration * video.time_base) if video.duration is not None else None,
            "has_audio": audio is not None,
            "audio_rate": audio.rate if audio is not None else None,
            "audio_channels": audio.channels if audio is not None else None,
        }
        return info, selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    source = root / "data/output/minimax-h3-tests"
    cases = [
        ("Baseline 20-step", "benchmark-baseline_00001_.mp4"),
        ("FBC Safe 20-step", "benchmark-safe_00001_.mp4"),
        ("FBC Fast 20-step", "benchmark-fast_00001_.mp4"),
        ("Turbo 4-step", "benchmark-turbo_00001_.mp4"),
    ]
    results: list[dict] = []
    panels: list[Image.Image] = []
    panel_width, panel_height = 640, 390
    for label, filename in cases:
        info, frame = inspect_video(source / filename)
        info["label"] = label
        results.append(info)
        frame.thumbnail((panel_width, panel_height - 38), Image.Resampling.LANCZOS)
        panel = Image.new("RGB", (panel_width, panel_height), (22, 24, 29))
        x = (panel_width - frame.width) // 2
        y = 38 + (panel_height - 38 - frame.height) // 2
        panel.paste(frame, (x, y))
        ImageDraw.Draw(panel).text((12, 10), label, fill=(245, 245, 248))
        panels.append(panel)

    sheet = Image.new("RGB", (panel_width * 2, panel_height * 2), (16, 18, 22))
    for index, panel in enumerate(panels):
        sheet.paste(panel, ((index % 2) * panel_width, (index // 2) * panel_height))
    output_dir = root / "tests/results"
    output_dir.mkdir(parents=True, exist_ok=True)
    sheet_path = output_dir / "benchmark-contact-sheet.png"
    sheet.save(sheet_path)
    report = {"ok": all(item["decoded_frames"] == 56 and item["has_audio"] for item in results), "videos": results, "contact_sheet": str(sheet_path)}
    final_path = source / "final-fl2va-fast_00001_.mp4"
    if final_path.exists():
        final_info, final_frame = inspect_video(final_path)
        final_info["label"] = "Final FL2VA Fast 25-step"
        final_midpoint = output_dir / "final-midpoint.png"
        final_frame.save(final_midpoint)
        final_info["midpoint_image"] = str(final_midpoint)
        report["final"] = final_info
        report["ok"] = bool(report["ok"] and final_info["decoded_frames"] == 124 and final_info["has_audio"])
    (root / "state/output-inspection.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
