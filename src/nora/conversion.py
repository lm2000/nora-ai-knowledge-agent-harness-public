"""Optional Docling extraction; originals remain untouched."""

import json
from pathlib import Path

from nora.common import digest


def convert(source: Path, output: Path, converter=None) -> dict:
    if not source.is_file() or source.is_symlink():
        raise ValueError("Source must be a regular readable document")
    if output.exists():
        raise FileExistsError("Choose a new conversion output directory")
    if converter is None:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
    raw = source.read_bytes()
    result = converter.convert(source)
    text = result.document.export_to_markdown()
    if not text.strip():
        raise ValueError("Conversion produced no readable text")
    output.mkdir(parents=True, exist_ok=False)
    (output / "document.md").write_text(text, encoding="utf-8")
    (output / "document.json").write_text(
        json.dumps(result.document.export_to_dict(), ensure_ascii=False), encoding="utf-8"
    )
    provenance = {
        "source_sha256": digest(raw),
        "text_sha256": digest(text.encode()),
        "source_name": source.name,
    }
    (output / "source.json").write_text(json.dumps(provenance, indent=2) + "\n")
    return provenance
