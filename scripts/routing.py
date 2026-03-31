#!/usr/bin/env python3
from __future__ import annotations

import re
from typing import Any


ARCHETYPE_CONFIGS: dict[str, dict[str, Any]] = {
    "data_analyst": {
        "family": "data",
        "terms": [
            "data analyst",
            "business intelligence",
            "reporting",
            "dashboard",
            "excel",
            "visualization",
            "kpi",
            "stakeholder",
            "insight",
        ],
        "preferred_tags": ["reporting", "analytics", "sql", "excel", "validation", "dashboard", "stakeholder"],
        "target_density": "balanced",
        "target_tone": "analytical, concise, reporting-oriented, stakeholder-aware",
        "avoid_terms": ["research-heavy", "deep-learning-heavy", "novel model research"],
        "must_preserve_terms": ["sql", "excel", "reporting", "validation"],
        "project_bullet_targets": [4, 3, 2],
    },
    "data_scientist": {
        "family": "data",
        "terms": [
            "data scientist",
            "machine learning",
            "modelling",
            "modeling",
            "statistics",
            "experimentation",
            "predictive",
            "feature engineering",
            "ab test",
        ],
        "preferred_tags": ["ml", "model", "analysis", "python", "experimentation", "feature", "validation"],
        "target_density": "balanced",
        "target_tone": "modeling-oriented, evidence-driven, experimentation-aware",
        "avoid_terms": ["dashboard-only", "pure reporting", "ops-heavy"],
        "must_preserve_terms": ["python", "sql", "analysis", "validation"],
        "project_bullet_targets": [4, 4, 3],
    },
    "data_engineer": {
        "family": "data",
        "terms": [
            "data engineer",
            "etl",
            "pipeline",
            "warehouse",
            "airflow",
            "dbt",
            "ingestion",
            "bigquery",
            "snowflake",
        ],
        "preferred_tags": ["pipeline", "etl", "sql", "docker", "api", "warehouse", "monitoring", "validation"],
        "target_density": "dense",
        "target_tone": "pipeline-reliability-focused, production-minded, data-platform-oriented",
        "avoid_terms": ["research-heavy", "pure reporting", "front-end emphasis"],
        "must_preserve_terms": ["python", "sql", "pipeline", "validation"],
        "project_bullet_targets": [5, 4, 3],
    },
    "applied_ai": {
        "family": "ai",
        "terms": [
            "ai engineer",
            "machine learning engineer",
            "applied ai",
            "llm",
            "genai",
            "rag",
            "prompt",
            "evaluation",
            "agent",
        ],
        "preferred_tags": ["llm", "agent", "automation", "evaluation", "python", "reliability", "validation"],
        "target_density": "dense",
        "target_tone": "applied-ai-delivery-focused, product-minded, evaluation-aware",
        "avoid_terms": ["research-only", "pure academic framing", "generic ai copy"],
        "must_preserve_terms": ["python", "llm", "automation", "validation"],
        "project_bullet_targets": [5, 4, 3],
    },
    "backend_platform": {
        "family": "software",
        "terms": [
            "backend",
            "platform",
            "api",
            "distributed",
            "infra",
            "microservice",
            "observability",
            "reliability",
            "service",
        ],
        "preferred_tags": ["backend", "api", "docker", "linux", "monitoring", "reliability", "platform", "sql"],
        "target_density": "dense",
        "target_tone": "backend-platform-focused, reliability-oriented, implementation-heavy",
        "avoid_terms": ["front-end emphasis", "research-heavy", "reporting-only"],
        "must_preserve_terms": ["python", "api", "validation", "monitoring"],
        "project_bullet_targets": [5, 4, 3],
    },
    "software_general": {
        "family": "software",
        "terms": [
            "software engineer",
            "developer",
            "full stack",
            "full-stack",
            "frontend",
            "web",
            "product engineering",
        ],
        "preferred_tags": ["software", "api", "testing", "python", "javascript", "delivery", "validation"],
        "target_density": "balanced",
        "target_tone": "implementation-focused, product-aware, ownership-oriented",
        "avoid_terms": ["quant-heavy", "research-heavy", "ops-only"],
        "must_preserve_terms": ["python", "delivery", "validation"],
        "project_bullet_targets": [4, 4, 3],
    },
    "quant_dev": {
        "family": "quant",
        "terms": [
            "quant",
            "pricing",
            "derivatives",
            "portfolio",
            "trading",
            "backtesting",
            "risk",
            "execution",
            "alpha",
        ],
        "preferred_tags": ["quant", "trading", "risk", "python", "c++", "validation", "monitoring"],
        "target_density": "dense",
        "target_tone": "systematic-research-oriented, risk-aware, execution-minded",
        "avoid_terms": ["generic software copy", "dashboard-heavy", "product-generalist wording"],
        "must_preserve_terms": ["python", "validation", "risk", "monitoring"],
        "project_bullet_targets": [5, 4, 3],
    },
}


DEFAULT_ARCHETYPE_BY_FAMILY = {
    "data": "data_engineer",
    "ai": "applied_ai",
    "software": "software_general",
    "quant": "quant_dev",
}


ROLE_TOKEN_ALLOWLIST = {
    "data",
    "analyst",
    "scientist",
    "engineer",
    "engineering",
    "ai",
    "ml",
    "software",
    "backend",
    "platform",
    "quant",
    "trading",
    "automation",
    "llm",
    "research",
    "reporting",
    "pipeline",
    "frontend",
    "fullstack",
    "full",
    "stack",
}


def normalize_token(text: str) -> str:
    return re.sub(r"[^a-z0-9+]+", "-", text.lower()).strip("-")


def tokenize_loose(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9+_-]*", text.lower())


def _score_terms(corpus: str, terms: list[str]) -> int:
    score = 0
    for term in terms:
        if term in corpus:
            score += 3 if " " in term or "-" in term else 1
    return score


def family_for_archetype(archetype: str, fallback_family: str = "software") -> str:
    return ARCHETYPE_CONFIGS.get(archetype, {}).get("family", fallback_family)


def detect_archetype(text: str, role: str, family: str) -> str:
    corpus = f"{text} {role}".lower()
    candidates = [name for name, config in ARCHETYPE_CONFIGS.items() if config["family"] == family]
    if not candidates:
        return DEFAULT_ARCHETYPE_BY_FAMILY.get(family, "software_general")

    scores = {name: _score_terms(corpus, ARCHETYPE_CONFIGS[name]["terms"]) for name in candidates}
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return DEFAULT_ARCHETYPE_BY_FAMILY.get(family, best)
    return best


def get_archetype_config(archetype: str, family: str | None = None) -> dict[str, Any]:
    if archetype in ARCHETYPE_CONFIGS:
        return ARCHETYPE_CONFIGS[archetype]
    fallback_family = family or "software"
    return ARCHETYPE_CONFIGS[DEFAULT_ARCHETYPE_BY_FAMILY.get(fallback_family, "software_general")]


def project_bullet_targets_for_archetype(archetype: str, fallback: list[int]) -> list[int]:
    config = get_archetype_config(archetype)
    targets = config.get("project_bullet_targets", fallback)
    return list(targets) if isinstance(targets, list) and targets else list(fallback)


def infer_source_role_tokens(*texts: str) -> list[str]:
    collected: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for token in tokenize_loose(text):
            normalized = token.replace("_", "").replace("-", "")
            if token in ROLE_TOKEN_ALLOWLIST or normalized in ROLE_TOKEN_ALLOWLIST:
                key = token.lower()
                if key not in seen:
                    seen.add(key)
                    collected.append(key)
    return collected

