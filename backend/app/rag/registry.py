"""Citeste galaxy-bank-knowledge/ — niciodata nu scrie in acest folder (interzis explicit de utilizator)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

_EXCLUDED_FILES = {"DOCUMENT-INDEX.md", "README.md"}


@dataclass(frozen=True)
class KnowledgeDocument:
    document_id: str
    source_path: str
    language: str
    document_type: str
    version: int
    checksum: str
    content: str
    audience: str = "customer"


def _parse_frontmatter(raw: str) -> tuple[dict, str]:
    if not raw.startswith("---"):
        return {}, raw

    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw

    metadata = yaml.safe_load(parts[1]) or {}
    body = parts[2].lstrip("\n")
    return metadata, body


def load_knowledge_documents(knowledge_dir: Path) -> list[KnowledgeDocument]:
    documents: list[KnowledgeDocument] = []

    for path in sorted(knowledge_dir.rglob("*.md")):
        if path.name in _EXCLUDED_FILES:
            continue

        raw = path.read_text(encoding="utf-8")
        metadata, body = _parse_frontmatter(raw)

        document_id = path.relative_to(knowledge_dir).with_suffix("").as_posix()
        checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        version = int(float(metadata.get("versiune", 1)))

        documents.append(
            KnowledgeDocument(
                document_id=document_id,
                source_path=str(path.relative_to(knowledge_dir)),
                language=metadata.get("limba", "ro"),
                document_type=metadata.get("tip_document", "necunoscut"),
                version=version,
                checksum=checksum,
                content=body,
            )
        )

    return documents
