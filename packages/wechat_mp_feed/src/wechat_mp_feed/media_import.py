"""Optional OCR helpers for screenshot/video imports."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .paths import default_home


class OCRDependencyError(RuntimeError):
    """Raised when optional OCR dependencies are not installed."""


UI_TEXT = {
    "公众号",
    "订阅号",
    "服务号",
    "微信",
    "通讯录",
    "发现",
    "我",
    "搜索",
    "新的朋友",
    "公众号消息",
    "已关注公众号",
    "私信",
    "全部",
    "贴图",
}


def extract_account_names_from_video(
    video_path: str | Path,
    fps: float = 1.0,
    ocr: str = "paddle",
    crop: str | None = None,
    scale_width: int | None = None,
    lang: str = "ch",
    save_frames: str | Path | None = None,
    dedupe_threshold: float = 0.92,
    min_occurrences: int = 1,
) -> dict[str, Any]:
    if fps <= 0:
        raise ValueError("fps must be greater than 0")
    if ocr != "paddle":
        raise ValueError("Only --ocr paddle is currently supported for local OCR")

    video = Path(video_path).expanduser()
    if not video.exists():
        raise FileNotFoundError(f"Video not found: {video}")

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if save_frames:
        frame_dir = Path(save_frames).expanduser()
        frame_dir.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir = tempfile.TemporaryDirectory(prefix="mpfeed-frames-")
        frame_dir = Path(temp_dir.name)

    try:
        frames = extract_frames(video, frame_dir=frame_dir, fps=fps, crop=crop, scale_width=scale_width)
        image_result = extract_account_names_from_images(
            frames,
            ocr=ocr,
            lang=lang,
            dedupe_threshold=dedupe_threshold,
            min_occurrences=min_occurrences,
        )
        return {
            "ok": True,
            "video": str(video),
            "fps": fps,
            "crop": crop,
            "scale_width": scale_width,
            "ocr": ocr,
            "lang": lang,
            "min_occurrences": min_occurrences,
            "frames_seen": len(frames),
            "frame_dir": str(frame_dir) if save_frames else None,
            **image_result,
        }
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


def extract_account_names_from_images(
    image_paths: list[Path] | list[str],
    ocr: str = "paddle",
    lang: str = "ch",
    dedupe_threshold: float = 0.92,
    min_occurrences: int = 1,
) -> dict[str, Any]:
    if ocr != "paddle":
        raise ValueError("Only --ocr paddle is currently supported for local OCR")

    engine = make_paddle_ocr(lang=lang)
    raw_lines: list[dict[str, Any]] = []
    for image_path in image_paths:
        path = Path(image_path)
        try:
            result = engine.ocr(str(path), cls=True)
        except TypeError:
            result = engine.ocr(str(path))
        for line in parse_paddle_result(result):
            raw_lines.append({"image": str(path), **line})

    candidates = [line["text"] for line in raw_lines if line.get("confidence", 0) >= 0.45]
    names = clean_account_names(candidates, dedupe_threshold=dedupe_threshold, min_occurrences=min_occurrences)
    return {"names": names, "count": len(names), "raw_lines": raw_lines}


def extract_frames(
    video_path: Path,
    frame_dir: Path,
    fps: float,
    crop: str | None = None,
    scale_width: int | None = None,
) -> list[Path]:
    ffmpeg = find_ffmpeg()
    output_pattern = frame_dir / "frame_%06d.png"
    filters = [f"fps={fps:g}"]
    if crop:
        filters.append(normalize_crop_filter(crop))
    if scale_width:
        filters.append(normalize_scale_filter(scale_width))

    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-vf",
        ",".join(filters),
        str(output_pattern),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.strip() or result.stdout.strip()}")

    return sorted(frame_dir.glob("frame_*.png"))


def find_ffmpeg() -> str:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise OCRDependencyError(
            "ffmpeg was not found. Install system ffmpeg or install OCR extras with: "
            'python3 -m pip install -e "packages/wechat_mp_feed[ocr]"'
        ) from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def make_paddle_ocr(lang: str):
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(default_home() / "cache" / "paddlex"))
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise OCRDependencyError(
            "PaddleOCR is not installed. Install OCR extras with: "
            'python3 -m pip install -e "packages/wechat_mp_feed[ocr]"'
        ) from exc
    init_options = [
        {
            "lang": lang,
            "text_detection_model_name": os.environ.get("MPFEED_PADDLE_TEXT_DET_MODEL", "PP-OCRv5_mobile_det"),
            "text_recognition_model_name": os.environ.get("MPFEED_PADDLE_TEXT_REC_MODEL", "PP-OCRv5_mobile_rec"),
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
        },
        {"use_angle_cls": True, "lang": lang},
        {"lang": lang},
    ]
    last_error = None
    for options in init_options:
        try:
            return PaddleOCR(**options)
        except (TypeError, ValueError) as exc:
            last_error = exc
    raise RuntimeError(f"Could not initialize PaddleOCR: {last_error}")


def parse_paddle_result(result: Any) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    pages = result if isinstance(result, list) else [result]
    for page in pages:
        if not page:
            continue
        if isinstance(page, dict) and "rec_texts" in page:
            scores = page.get("rec_scores") or []
            for index, text in enumerate(page.get("rec_texts") or []):
                text = str(text).strip()
                if not text:
                    continue
                try:
                    confidence = float(scores[index])
                except (IndexError, TypeError, ValueError):
                    confidence = 0.0
                lines.append({"text": text, "confidence": confidence})
            continue
        for item in page:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            payload = item[1]
            if not isinstance(payload, (list, tuple)) or len(payload) < 2:
                continue
            text = str(payload[0]).strip()
            if not text:
                continue
            try:
                confidence = float(payload[1])
            except (TypeError, ValueError):
                confidence = 0.0
            lines.append({"text": text, "confidence": confidence})
    return lines


def clean_account_names(lines: list[str], dedupe_threshold: float = 0.92, min_occurrences: int = 1) -> list[str]:
    if min_occurrences < 1:
        raise ValueError("min_occurrences must be at least 1")

    occurrence_counts: dict[str, int] = {}
    normalized_lines: list[str] = []
    for line in lines:
        name = normalize_account_name(line)
        if not is_plausible_account_name(name):
            continue
        normalized_lines.append(name)
        occurrence_counts[name] = occurrence_counts.get(name, 0) + 1

    names: list[str] = []
    for name in normalized_lines:
        if occurrence_counts[name] < min_occurrences:
            continue
        if any(is_duplicate_name(name, existing, dedupe_threshold) for existing in names):
            continue
        names.append(name)
    return names


def normalize_account_name(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value)).strip()
    text = text.strip("·•丨|[]【】()（）:：,，.。")
    return text


def is_plausible_account_name(value: str) -> bool:
    if not value or value in UI_TEXT:
        return False
    if len(value) < 2 or len(value) > 40:
        return False
    if re.fullmatch(r"[A-Z#]+", value):
        return False
    if re.fullmatch(r"[0-9:：/\-_. ]+", value):
        return False
    if re.fullmatch(r"\d+\s*个公众号", value):
        return False
    if re.fullmatch(r"\d+\s*篇原创内容", value):
        return False
    if value.startswith("视频号"):
        return False
    if "已关注" in value:
        return False
    if not re.search(r"[A-Za-z\u4e00-\u9fff]", value):
        return False
    if len(value) > 18 and re.search(r"[，,、；;。]", value):
        return False
    if len(value) <= 6 and value.endswith("等"):
        return False
    if re.search(r"(关注|消息|联系人|聊天|扫一扫|朋友圈)$", value) and len(value) <= 6:
        return False
    return True


def is_duplicate_name(left: str, right: str, threshold: float) -> bool:
    if left == right:
        return True
    return SequenceMatcher(a=left, b=right).ratio() >= threshold


def normalize_crop_filter(crop: str) -> str:
    parts = [part.strip() for part in crop.split(",")]
    if len(parts) != 4 or not all(re.fullmatch(r"\d+", part) for part in parts):
        raise ValueError("--crop must be x,y,w,h")
    x, y, width, height = parts
    return f"crop={width}:{height}:{x}:{y}"


def normalize_scale_filter(width: int) -> str:
    if width < 160:
        raise ValueError("--scale-width must be at least 160")
    return f"scale={width}:-1"


def write_ocr_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
