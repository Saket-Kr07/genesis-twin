
import json
import os
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError


RESEARCH_DIR = Path(__file__).resolve().parent

PAPERS_FILE = RESEARCH_DIR / "data" / "papers.json"
EXTRACTED_FILE = RESEARCH_DIR / "data" / "llm_extracted_parameters.json"

MODEL_VERSION = os.getenv("MODEL_VERSION", "v0.1.0")


def get_active_model_version():
    """Get the latest approved version from the database."""

    try:
        from app.db import SessionLocal
        from app.routers.model_versions import get_current_approved_version

        db = SessionLocal()
        try:
            return get_current_approved_version(db) or MODEL_VERSION
        finally:
            db.close()

    except (ImportError, SQLAlchemyError):
        return MODEL_VERSION


def load_json(file_path):
    """Read a JSON file safely."""

    if not file_path.exists():
        return []

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []

    except (OSError, json.JSONDecodeError):
        return []


def find_extraction(paper, extractions):
    """Find extracted information using DOI or title."""

    doi = (paper.get("doi") or "").strip().lower()
    title = (paper.get("title") or "").strip().lower()

    for item in extractions:
        item_doi = (item.get("doi") or "").strip().lower()
        item_title = (item.get("title") or "").strip().lower()

        if doi and item_doi == doi:
            return item

        if title and item_title == title:
            return item

    return {}


def count_numeric_parameters(extraction):
    """Count parameters with actual numeric values."""

    count = 0

    for parameter in extraction.get("parameters", []):
        value = parameter.get("value")

        if value is None:
            continue

        try:
            float(value)
            count += 1
        except (ValueError, TypeError):
            continue

    return count


def get_sources():

    papers = load_json(PAPERS_FILE)
    extractions = load_json(EXTRACTED_FILE)
    active_version = get_active_model_version()

    sources = []

    for paper in papers:

        extraction = find_extraction(paper, extractions)

        is_preprint = paper.get("isPreprint", False)

        paper_type = (
            "preprint" if is_preprint else "peer_reviewed"
        )

        numeric_count = count_numeric_parameters(extraction)

        if numeric_count > 0:
            change = (
                f"{numeric_count} numeric candidate parameter(s) "
                "extracted; not applied to the model. "
                "No model change has been approved."
            )
        else:
            change = (
                "Paper indexed; no usable numeric parameters extracted. "
                "No model change has been approved."
            )

        sources.append({
            "title": paper.get("title", ""),
            "doi": paper.get("doi", ""),
            "date": paper.get("date", ""),
            "type": paper_type,
            "change": change,
            "model_version": active_version
        })

    return sorted(
        sources,
        key=lambda item: item["date"],
        reverse=True
    )


if __name__ == "__main__":

    for source in get_sources():
        print(source)
