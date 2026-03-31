#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from extract_job_card import build_job_card


STOPWORDS = {
    "and", "the", "with", "for", "from", "into", "that", "this", "your", "will", "have", "you",
    "our", "are", "using", "work", "role", "data", "engineer", "engineering", "software", "junior",
    "experience", "strong", "workflows", "working", "build", "built", "deliver", "delivery", "team",
    "teams", "systems", "system", "application", "applications", "skills", "knowledge", "good", "great",
    "required", "requirements", "preferred", "plus", "related", "degree", "ability", "support", "would",
}
KEEP_SHORT = {"sql", "api", "llm", "rag", "etl", "c++", "ml", "ai"}


def run_cmd(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def read_pdf_pages(pdf_path: Path) -> int | None:
    if not command_exists("pdfinfo"):
        return None
    output = run_cmd(["pdfinfo", str(pdf_path)])
    match = re.search(r"^Pages:\s+(\d+)$", output, flags=re.MULTILINE)
    if not match:
        raise RuntimeError("Failed to parse page count from pdfinfo output.")
    return int(match.group(1))


def render_preview_png(pdf_path: Path, output_dir: Path, base_name: str) -> Path | None:
    if not command_exists("pdftoppm"):
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / base_name
    subprocess.check_call(["pdftoppm", "-png", "-f", "1", "-singlefile", str(pdf_path), str(prefix)])
    return prefix.with_suffix(".png")


def render_preview_pgm(pdf_path: Path, output_dir: Path, base_name: str) -> Path | None:
    if not command_exists("pdftoppm"):
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / f"{base_name}-gray"
    subprocess.check_call(["pdftoppm", "-gray", "-f", "1", "-singlefile", str(pdf_path), str(prefix)])
    return prefix.with_suffix(".pgm")


def parse_pgm(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    if not data.startswith(b"P5"):
        raise RuntimeError(f"Unsupported PGM format in {path}.")
    pos = 2

    def next_token() -> bytes:
        nonlocal pos
        while pos < len(data) and data[pos] in b" \t\r\n":
            pos += 1
        if pos < len(data) and data[pos] == 35:
            while pos < len(data) and data[pos] != 10:
                pos += 1
            return next_token()
        start = pos
        while pos < len(data) and data[pos] not in b" \t\r\n":
            pos += 1
        return data[start:pos]

    width = int(next_token())
    height = int(next_token())
    maxval = int(next_token())
    if maxval > 255:
        raise RuntimeError("16-bit PGM is unsupported.")
    while pos < len(data) and data[pos] in b" \t\r\n":
        pos += 1
    pixels = data[pos:pos + width * height]
    return width, height, pixels


def bottom_whitespace_ratio(pgm_path: Path, threshold: int = 245) -> tuple[float, float]:
    width, height, pixels = parse_pgm(pgm_path)
    first_nonwhite = None
    last_nonwhite = None
    for row in range(height):
        offset = row * width
        row_pixels = pixels[offset:offset + width]
        if any(pixel < threshold for pixel in row_pixels):
            if first_nonwhite is None:
                first_nonwhite = row
            last_nonwhite = row
    if first_nonwhite is None or last_nonwhite is None:
        return 1.0, 0.0
    bottom_ratio = (height - 1 - last_nonwhite) / max(height, 1)
    occupied_ratio = (last_nonwhite - first_nonwhite + 1) / max(height, 1)
    return bottom_ratio, occupied_ratio


def extract_text(pdf_path: Path) -> str | None:
    if not command_exists("pdftotext"):
        return None
    return run_cmd(["pdftotext", str(pdf_path), "-"])


def tokenize(text: str) -> list[str]:
    found = re.findall(r"[a-z0-9][a-z0-9+_-]*", text.lower())
    out = []
    for token in found:
        if token in STOPWORDS:
            continue
        if len(token) < 4 and token not in KEEP_SHORT:
            continue
        out.append(token)
    return out


def derive_terms_from_job_card(job_card: dict[str, Any]) -> list[str]:
    raw = []
    raw.extend(job_card.get("must_have", []))
    raw.extend(job_card.get("domain_keywords", []))
    raw.append(job_card.get("role", ""))
    seen: set[str] = set()
    out: list[str] = []
    for part in raw:
        for token in tokenize(str(part)):
            if token in seen:
                continue
            seen.add(token)
            out.append(token)
    return out[:20]


def compute_keyword_coverage(text: str | None, terms: list[str]) -> dict[str, Any]:
    if not terms:
        return {"terms": [], "matched_terms": [], "ratio": 1.0, "classification": "pass"}
    if not text:
        return {"terms": terms, "matched_terms": [], "ratio": 0.0, "classification": "unavailable"}
    text_tokens = set(tokenize(text))
    lower = text.lower()
    matched = [term for term in terms if term in text_tokens or term in lower]
    ratio = len(matched) / max(len(terms), 1)
    if ratio < 0.28 and len(matched) < min(3, len(terms)):
        classification = "fail"
    elif ratio < 0.45:
        classification = "warn"
    else:
        classification = "pass"
    return {
        "terms": terms,
        "matched_terms": matched,
        "ratio": ratio,
        "classification": classification,
    }


def classify_layout(page_count: int | None, bottom_ratio: float | None, occupied_ratio: float | None) -> str:
    if page_count and page_count > 1:
        return "overflow"
    if bottom_ratio is None or occupied_ratio is None:
        return "unknown"
    if bottom_ratio > 0.20:
        return "sparse"
    if bottom_ratio < 0.015 and occupied_ratio > 0.93:
        return "overflow-tight"
    return "balanced"


def compute_score(
    *,
    status: str,
    layout_classification: str,
    keyword_ratio: float,
    bottom_whitespace_ratio: float | None,
) -> float:
    score = 100.0 if status == "pass" else 0.0
    if layout_classification == "balanced":
        score += 10.0
    elif layout_classification == "unknown":
        score += 4.0
    elif layout_classification == "overflow-tight":
        score += 2.0
    elif layout_classification == "sparse":
        score -= 10.0
    score += keyword_ratio * 10.0
    if bottom_whitespace_ratio is not None:
        score += max(0.0, 1.0 - bottom_whitespace_ratio)
    return score


def run_contract_check(
    output_dir: Path,
    base_name: str,
    include_cover: bool,
    cover_base_name: str | None,
) -> dict[str, Any]:
    script = Path(__file__).with_name("check_output_contract.py")
    cmd = [
        "python3",
        str(script),
        "--output-dir",
        str(output_dir),
        "--base-name",
        base_name,
    ]
    if include_cover:
        if not cover_base_name:
            raise RuntimeError("--include-cover requires --cover-base-name.")
        cmd.extend(["--include-cover", "--cover-base-name", cover_base_name])
    output = run_cmd(cmd)
    return json.loads(output)


def resolve_job_card(job_card_path: Path | None, jd_file: Path | None) -> dict[str, Any] | None:
    if job_card_path and job_card_path.exists():
        return json.loads(job_card_path.read_text(encoding="utf-8"))
    if jd_file and jd_file.exists():
        return build_job_card(jd_file.read_text(encoding="utf-8"))
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Quality checks for tailored resume outputs.")
    parser.add_argument("--pdf", type=Path, required=True, help="CV PDF path.")
    parser.add_argument("--max-pages", type=int, default=1, help="Maximum allowed pages for CV.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output directory to contract-check.")
    parser.add_argument("--base-name", required=True, help="CV base name without extension.")
    parser.add_argument("--include-cover", action="store_true", help="Validate CV+cover contract.")
    parser.add_argument("--cover-base-name", help="Cover base name when include-cover is enabled.")
    parser.add_argument("--job-card", type=Path, help="Optional job_card.json for keyword coverage.")
    parser.add_argument("--jd-file", type=Path, help="Optional raw JD text for keyword coverage if job card is absent.")
    parser.add_argument("--unsupported-count", type=int, default=0, help="Unsupported claim count propagated from rewrite stage.")
    args = parser.parse_args()

    pages = read_pdf_pages(args.pdf)
    contract = run_contract_check(
        output_dir=args.output_dir,
        base_name=args.base_name,
        include_cover=args.include_cover,
        cover_base_name=args.cover_base_name,
    )

    warnings: list[str] = []
    qa_tmp_dir = Path(tempfile.gettempdir()) / "resume-tailor-qa"
    png_path = render_preview_png(args.pdf, qa_tmp_dir, args.base_name)
    pgm_path = render_preview_pgm(args.pdf, qa_tmp_dir, args.base_name)
    bottom_ratio = None
    occupied_ratio = None
    if pgm_path and pgm_path.exists():
        bottom_ratio, occupied_ratio = bottom_whitespace_ratio(pgm_path)
    else:
        warnings.append("layout preview unavailable; pdftoppm not found")

    text = extract_text(args.pdf)
    if text is None:
        warnings.append("text extraction unavailable; pdftotext not found")
    text_sample = "\n".join((text or "").splitlines()[:40]).strip()

    if pages is None:
        warnings.append("page count unavailable; pdfinfo not found")

    job_card = resolve_job_card(args.job_card, args.jd_file)
    keyword_coverage = compute_keyword_coverage(text, derive_terms_from_job_card(job_card or {}))
    if keyword_coverage["classification"] == "unavailable":
        warnings.append("keyword coverage unavailable")

    layout_class = classify_layout(pages, bottom_ratio, occupied_ratio)
    status = "pass"
    page_check_pass = pages is None or pages <= args.max_pages
    contract_check_pass = contract.get("status") == "pass"

    if not page_check_pass or not contract_check_pass:
        status = "fail"
    if layout_class == "sparse":
        status = "fail"
        warnings.append("page underfilled")
    elif layout_class == "overflow-tight":
        warnings.append("page is very dense")
    if keyword_coverage["classification"] == "fail":
        status = "fail"
        warnings.append("keyword coverage below threshold")
    elif keyword_coverage["classification"] == "warn":
        warnings.append("keyword coverage is modest")
    if args.unsupported_count > 0:
        status = "fail"
        warnings.append("unsupported claims detected")

    score = compute_score(
        status=status,
        layout_classification=layout_class,
        keyword_ratio=float(keyword_coverage.get("ratio", 0.0)),
        bottom_whitespace_ratio=bottom_ratio,
    )

    result = {
        "status": status,
        "score": score,
        "pdf": str(args.pdf),
        "pages": pages,
        "max_pages": args.max_pages,
        "page_check_pass": page_check_pass,
        "contract_check_pass": contract_check_pass,
        "contract": contract,
        "preview_png": str(png_path) if png_path else None,
        "preview_pgm": str(pgm_path) if pgm_path else None,
        "render_check_pass": bool(png_path and pgm_path and pgm_path.exists()),
        "text_check_pass": bool(text_sample),
        "text_sample": text_sample,
        "layout": {
            "classification": layout_class,
            "bottom_whitespace_ratio": bottom_ratio,
            "occupied_height_ratio": occupied_ratio,
        },
        "keyword_coverage": keyword_coverage,
        "unsupported_count": args.unsupported_count,
        "warnings": warnings,
    }

    print(json.dumps(result, indent=2))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
