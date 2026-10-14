"""Create the initial evidence manifest from files already retrieved, offline.

Do not rerun to bless changed sources; a new retrieval requires a new version.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT.parents[1]
URLS = {
    "responses-create": "https://developers.openai.com/api/reference/resources/responses/methods/create",
    "structured-outputs": "https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses",
    "reasoning": "https://developers.openai.com/api/docs/guides/reasoning",
    "migrate-to-responses": "https://developers.openai.com/api/docs/guides/migrate-to-responses",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    target = ROOT / "manifest.json"
    if target.exists():
        raise SystemExit("Pin already exists; create a new version instead.")
    sources = []
    for name, url in URLS.items():
        html = ROOT / "sources" / (name + ".html")
        readable = html.with_suffix(".txt")
        retrieved = datetime.fromtimestamp(html.stat().st_mtime, timezone.utc)
        sources.append({
            "source_id": name,
            "official_url": url,
            "retrieved_at_utc": retrieved.isoformat(),
            "retrieval_date": retrieved.date().isoformat(),
            "retrieval_method": "Public HTTPS GET using PowerShell Invoke-WebRequest; no authentication",
            "hash_scope": "Exact downloaded HTML bytes; not a server release or semantic contract hash",
            "files": [
                {"path": str(p.relative_to(ROOT)).replace("\\", "/"),
                 "sha256": digest(p), "bytes": p.stat().st_size}
                for p in (html, readable)
            ],
        })
    baseline = {
        str(p.relative_to(PACKAGE)).replace("\\", "/"): digest(p)
        for p in sorted([*PACKAGE.glob("*.py"), *PACKAGE.glob("*.md"),
                         *PACKAGE.joinpath("tests").glob("*.py")])
        if p.name != "AI_R3A_R1_HANDOFF_v1.md"
    }
    manifest = {
        "reference_version": "AI-R3A-R1-RESPONSES-CONTRACT-1",
        "retrieval_date": "2026-10-14",
        "scope": "Pinned documentation for offline R2 work; no live compatibility or readiness grant",
        "sources": sources,
        "existing_ai_research_sha256": baseline,
        "baseline_scope": "Existing implementation, tests and documents at pin creation; no R2 edits",
    }
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
