# Changelog

[Home](README.md) · [Roadmap](Plan.md)

This page records project milestones. Detailed private operating history and execution receipts are maintained separately.

## 2026-09-14 — Public source candidate and isolated container trial

- Consolidate duplicate backends and UIs into one installable Python package and one browser application.
- Add explicit credential/configuration handling, deterministic preparation, validated index imports, shared MCP and routing failure repairs.
- Supply fictional documents, adapter tests, a real BGE/MCP smoke test and a credential-free UI build.
- Reorganize public documentation around the application, target guides, evaluation and contribution paths; replace Obsidian-only diagram embeds with editable Mermaid and Excalidraw sources with matching SVG previews.
- Replace legacy packaging with one Compose configuration and pinned dependency/image references.
- Build an explicit public source snapshot; preserve private originals and commit history separately.
- Build both application images and run the five-service stack on ARM Linux with the public fictional documents.
- Verify four live Ollama question requests, same-conversation context, missing-evidence behavior, restart persistence and PostgreSQL restoration into a fresh volume.
- Forward UI allowed origins and MCP allowed hosts from Compose environment settings; verify accepted and rejected requests.
- Document Tailscale as the intended private access path. Access from another device and broader answer quality remain to test.

No production rollout or GitHub publication is included.

## 2026-09-09 — Repository consolidation

The reference application, architecture, setup guides and evaluation material were consolidated into one project. Documentation and syntax-check tooling were added.

## 2026-09-05 — Private reference implementation and experiments

A private single-VM application was implemented around Coordination, Retrieval MCP, Qdrant, PostgreSQL and a CopilotKit/AG-UI interface. Separate document-preparation, embedding and retrieval experiments were recorded.

Read [evaluation](evaluation/README.md) for experimental scope and [deployment status](setup/private-deployment/STATUS.md) for the current evidence boundary.
