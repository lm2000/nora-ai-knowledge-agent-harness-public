#!/usr/bin/env python3
"""Verify the conversion job image can process a real non-Markdown document.

Creates a synthetic DOCX in a writable task directory under the checkout, runs
the `job-convert` container from the ingestion profile, and asserts that
Docling-produced Markdown contains the expected text. This exercises the real
Docling dependency inside the conversion image; it does not use a conversion
fake.
"""

import json
import os
import subprocess
import zipfile
from pathlib import Path


def make_docx(path: Path, text: str) -> None:
    """Write a minimal DOCX that contains one paragraph of text."""
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r>
        <w:t>{text}</w:t>
      </w:r>
    </w:p>
  </w:body>
</w:document>"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    doc_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/_rels/document.xml.rels", doc_rels)
        zf.writestr("word/document.xml", document_xml)


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    expected_text = "Atlas ships on October 12, 2026."

    # Use a checkout-local task directory so Docker on this Mac shares the mount.
    task_root = repo / ".runtime" / "acceptance" / "tmp"
    task_root.mkdir(parents=True, exist_ok=True)
    source = task_root / "conversion-verify-source"
    source.mkdir(parents=True, exist_ok=True)
    make_docx(source / "atlas.docx", expected_text)
    output_host = task_root / "conversion-verify-out"

    env = os.environ.copy()
    env.setdefault("COMPOSE_PROJECT_NAME", "nora-conversion-verify")
    env.setdefault("NORA_CONVERSION_IMAGE", "nora-conversion:local")

    build = subprocess.run(
        ["docker", "compose", "--profile", "ingestion", "build", "job-convert"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )
    if build.returncode != 0:
        print(json.dumps({"pass": False, "stage": "build", "error": build.stderr}))
        return 1

    # Remove any stale output so Docling sees a clean, empty mount point.
    if output_host.exists():
        import shutil

        shutil.rmtree(output_host)

    run = subprocess.run(
        [
            "docker",
            "compose",
            "--profile",
            "ingestion",
            "run",
            "--rm",
            "-v",
            f"{source}:/source:ro",
            "-v",
            f"{output_host}:/out",
            "job-convert",
            "/source",
            "/out",
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )
    if run.returncode != 0:
        print(
            json.dumps(
                {"pass": False, "stage": "convert", "stdout": run.stdout, "stderr": run.stderr}
            )
        )
        return 1

    manifest = json.loads((output_host / "manifest.json").read_text())
    converted = list(output_host.glob("files/*.md"))
    if not converted:
        print(json.dumps({"pass": False, "stage": "verify", "error": "no markdown output"}))
        return 1
    markdown = converted[0].read_text(encoding="utf-8")
    if expected_text not in markdown:
        print(
            json.dumps(
                {
                    "pass": False,
                    "stage": "verify",
                    "error": "expected text not found",
                    "markdown": markdown,
                }
            )
        )
        return 1

    print(
        json.dumps(
            {
                "pass": True,
                "stage": "docx-conversion",
                "document": str(converted[0]),
                "manifest": manifest,
                "notes": [
                    "Used a synthetic DOCX and the real Docling dependency inside the conversion image.",
                    "Bind mounts used a checkout-local task directory, not an unshared host temp path.",
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
