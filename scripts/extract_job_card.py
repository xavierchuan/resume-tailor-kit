#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable

from routing import detect_archetype


ROLE_HINTS = (
    "engineer",
    "developer",
    "scientist",
    "trader",
    "researcher",
    "analyst",
    "architect",
    "consultant",
    "manager",
)

DOMAIN_TERMS = [
    "etf",
    "leveraged etf",
    "equities",
    "derivatives",
    "rates",
    "risk",
    "portfolio",
    "pricing",
    "llm",
    "genai",
    "rag",
    "agent",
    "python",
    "c++",
    "sql",
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
    "airflow",
    "snowflake",
    "bigquery",
    "prompt engineering",
    "evaluation",
    "monitoring",
]


def _clean_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw.strip())
        if line:
            lines.append(line)
    return lines


def _dedupe_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
    return out


def _extract_company(text: str, lines: list[str]) -> str:
    patterns = [
        r"Company logo for,\s*(.+?)\.",
        r"Company logo for,\s*(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    if len(lines) >= 2 and "company logo for" in lines[0].lower():
        return lines[1].strip()
    return lines[0] if lines else "Unknown Company"


def _extract_role(lines: list[str]) -> str:
    for line in lines:
        lower = line.lower()
        if any(hint in lower for hint in ROLE_HINTS):
            return line
    return "Unknown Role"


def _detect_family(text: str, role: str) -> str:
    corpus = f"{text} {role}".lower()
    role_lower = role.lower()
    strong_role_overrides = [
        ("data", ("data scientist", "data analyst", "data engineer", "analytics engineer")),
        ("ai", ("applied ai", "ai engineer", "machine learning engineer", "ml engineer")),
        ("quant", ("quant", "quantitative developer", "quant developer", "quant researcher", "trader")),
        ("software", ("backend engineer", "platform engineer", "software engineer", "full stack", "full-stack", "developer")),
    ]
    for family, phrases in strong_role_overrides:
        if any(phrase in role_lower for phrase in phrases):
            return family

    quant_terms = [
        "quant",
        "trader",
        "pricing",
        "derivatives",
        "portfolio",
        "equities",
        "etf",
        "risk model",
    ]
    ai_terms = [
        "llm",
        "genai",
        "prompt",
        "agent",
        "machine learning",
        "artificial intelligence",
        "rag",
        "model evaluation",
    ]
    data_terms = [
        "data engineer",
        "data scientist",
        "data analyst",
        "etl",
        "warehouse",
        "analytics",
        "statistics",
        "feature engineering",
        "ab testing",
        "snowflake",
        "bigquery",
        "dbt",
    ]
    software_terms = [
        "software engineer",
        "backend",
        "frontend",
        "full stack",
        "platform",
        "developer",
    ]
    scores = {
        "quant": sum(term in corpus for term in quant_terms),
        "ai": sum(term in corpus for term in ai_terms),
        "data": sum(term in corpus for term in data_terms),
        "software": sum(term in corpus for term in software_terms),
    }
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "software"
    return best


def _detect_seniority(text: str) -> str:
    corpus = text.lower()
    if any(token in corpus for token in ["entry level", "entry-level", "graduate", "fresh graduate", "0-1 years"]):
        return "entry"
    if any(token in corpus for token in ["junior", "0-2 years", "1-2 years", "1–2 years", "1-3 years", "1–3 years"]):
        return "junior"
    if any(token in corpus for token in ["senior", "staff", "principal", "lead", "head of"]):
        return "senior"
    if any(token in corpus for token in ["3+ years", "3 years", "2-6 years", "2–6 years", "mid-level"]):
        return "mid"
    return "mid"


def _extract_requirement_lists(lines: list[str]) -> tuple[list[str], list[str]]:
    must_headers = (
        "requirements",
        "what you'll need",
        "what you will bring",
        "must have",
        "required",
        "qualification",
    )
    nice_headers = (
        "nice to have",
        "nice-to-have",
        "preferred",
        "desirable",
        "bonus",
    )
    must_have: list[str] = []
    nice_to_have: list[str] = []
    mode: str | None = None
    bullet_pattern = re.compile(r"^(?:[-•*]|\d+[\.)])\s+(.+)$")

    for line in lines:
        lower = line.lower().strip(":")
        if any(header in lower for header in must_headers):
            mode = "must"
            continue
        if any(header in lower for header in nice_headers):
            mode = "nice"
            continue

        bullet_match = bullet_pattern.match(line)
        if not bullet_match:
            if len(line.split()) <= 14 and mode in {"must", "nice"} and not line.endswith("."):
                candidate = line
            else:
                continue
        else:
            candidate = bullet_match.group(1).strip()
        candidate = re.sub(r"^[-•*]\s*", "", candidate).strip()
        if candidate.lower() in {"nice-to-have", "nice to have"}:
            continue

        if mode == "must":
            must_have.append(candidate)
        elif mode == "nice":
            nice_to_have.append(candidate)

    if not must_have:
        fallback = []
        for line in lines:
            lower = line.lower()
            if any(token in lower for token in ["must", "required", "strong", "experience with", "proficient in"]):
                fallback.append(line)
        must_have = fallback[:10]

    return _dedupe_keep_order(must_have)[:12], _dedupe_keep_order(nice_to_have)[:10]


def _extract_domain_keywords(text: str) -> list[str]:
    corpus = text.lower()
    found = [term for term in DOMAIN_TERMS if term in corpus]
    normalized = [term.replace(" ", "-") if term in {"leveraged etf", "prompt engineering", "model evaluation"} else term for term in found]
    return _dedupe_keep_order(normalized)


def _detect_location_mode(text: str) -> str:
    corpus = text.lower()
    if "hybrid" in corpus:
        return "hybrid"
    if any(token in corpus for token in ["on-site", "onsite", "in person", "in-office"]):
        return "onsite"
    if "remote" in corpus:
        return "remote"
    return "hybrid"


def _detect_visa_requirement(text: str) -> str:
    corpus = text.lower()
    requires_existing_right = [
        "no need for visa sponsorship",
        "cannot offer visa sponsorship",
        "unable to sponsor",
        "must have right to work",
        "without requiring employer sponsorship",
    ]
    sponsorship_available = [
        "visa sponsorship available",
        "can sponsor visa",
        "sponsorship available",
    ]
    if any(term in corpus for term in requires_existing_right):
        return "required"
    if any(term in corpus for term in sponsorship_available):
        return "not_required"
    return "unknown"


def build_job_card(text: str) -> dict:
    lines = _clean_lines(text)
    company = _extract_company(text, lines)
    role = _extract_role(lines)
    family = _detect_family(text, role)
    archetype = detect_archetype(text, role, family)
    seniority = _detect_seniority(text)
    must_have, nice_to_have = _extract_requirement_lists(lines)
    domain_keywords = _extract_domain_keywords(text)
    location_mode = _detect_location_mode(text)
    visa_requirement = _detect_visa_requirement(text)
    return {
        "company": company,
        "role": role,
        "family": family,
        "archetype": archetype,
        "seniority": seniority,
        "must_have": must_have,
        "nice_to_have": nice_to_have,
        "domain_keywords": domain_keywords,
        "location_mode": location_mode,
        "visa_requirement": visa_requirement,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract a compressed Job Card JSON from full JD text.")
    parser.add_argument("--jd-file", type=Path, help="Path to raw job description text file.")
    parser.add_argument("--jd-text", type=str, help="Raw job description text.")
    parser.add_argument("--output", type=Path, help="Write JSON output to file.")
    args = parser.parse_args()

    if not args.jd_file and not args.jd_text:
        parser.error("Provide either --jd-file or --jd-text.")
    if args.jd_file and args.jd_text:
        parser.error("Use only one of --jd-file or --jd-text.")

    text = args.jd_text
    if args.jd_file:
        text = args.jd_file.read_text(encoding="utf-8")
    assert text is not None

    card = build_job_card(text)
    output = json.dumps(card, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
