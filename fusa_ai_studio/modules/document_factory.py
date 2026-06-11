from __future__ import annotations

from pathlib import Path

import streamlit as st

from fusa_ai_studio.core.services import Services
from fusa_ai_studio.database.repository import now_iso
from fusa_ai_studio.ui.components import data_table, source_list
from fusa_ai_studio.ui.genai import run_genai_action
from fusa_ai_studio.ui.workproduct_inputs import render_workproduct_inputs


def _artifact_summary(services: Services, project_id: str) -> str:
    repo = services.repo
    lines: list[str] = []
    for table, title in [
        ("items", "Items"),
        ("hazards", "HARA"),
        ("safety_goals", "Safety Goals"),
        ("fsc_requirements", "FSC Requirements"),
        ("tsc_requirements", "TSC Requirements"),
    ]:
        rows = repo.list_table(table, project_id)
        lines.append(f"### {title}")
        lines.extend(f"- {row}" for row in rows[:20])
    return "\n".join(lines)


def _trace_summary(services: Services, project_id: str) -> str:
    links = services.repo.list_table("trace_links", project_id)
    return "\n".join(f"- {link['source_type']}:{link['source_id']} -> {link['target_type']}:{link['target_id']} ({link['link_type']})" for link in links)


def _write_docx(path: Path, title: str, content: str) -> None:
    from docx import Document

    doc = Document()
    doc.add_heading(title, level=1)
    for line in content.splitlines():
        if line.startswith("### "):
            doc.add_heading(line[4:], level=3)
        elif line.startswith("## "):
            doc.add_heading(line[3:], level=2)
        elif line.startswith("# "):
            doc.add_heading(line[2:], level=1)
        elif line.startswith("- "):
            doc.add_paragraph(line[2:], style="List Bullet")
        elif line.strip():
            doc.add_paragraph(line)
    doc.save(path)


def render(services: Services, project_id: str) -> None:
    repo = services.repo
    st.title("Document Factory")
    input_tab, generation_tab, templates_tab, records_tab = st.tabs(["Inputs", "Generate", "Templates", "Records"])
    with input_tab:
        render_workproduct_inputs(services, project_id, "Document Factory")
    with generation_tab:
        project = repo.get_project(project_id) or {}
        doc_type = st.selectbox("Document", ["Item Definition Report", "HARA Report", "Safety Goals Report", "FSC Report", "TSC Report", "Traceability Matrix", "Safety Case Summary", "AI Gap Assessment"])
        output_format = st.selectbox("Format", ["Markdown", "DOCX", "TXT"])
        if st.button("Generate document", type="primary"):
            artifact_summary = _artifact_summary(services, project_id)
            trace_summary = _trace_summary(services, project_id)
            if doc_type == "AI Gap Assessment":
                answer = run_genai_action(
                    "Document Factory",
                    lambda: services.rag.ask(project_id, "Document Factory", "Generate an auditable safety case gap assessment with cited project context."),
                )
                body = answer.text
                source_list(answer.sources)
            else:
                body = f"# {doc_type}\n\n## Project\n{project.get('name', project_id)}\n\n{project.get('description', '')}\n\n## Artifact Summary\n{artifact_summary}\n\n## Traceability Summary\n{trace_summary}\n"
            safe_name = doc_type.lower().replace(" ", "_")
            suffix = {"Markdown": "md", "DOCX": "docx", "TXT": "txt"}[output_format]
            path = services.config.export_dir / f"{safe_name}_{now_iso().replace(':', '').replace('Z', '')}.{suffix}"
            if output_format == "DOCX":
                _write_docx(path, doc_type, body)
            else:
                path.write_text(body, encoding="utf-8")
            repo.insert(
                "documents",
                {
                    "project_id": project_id,
                    "title": doc_type,
                    "doc_type": output_format,
                    "content": body,
                    "file_path": str(path),
                },
            )
            repo.add_memory(project_id, "document", f"Generated {doc_type} at {path.name}.", 2)
            st.success(f"Generated {path}")
            st.download_button("Download document", data=path.read_bytes(), file_name=path.name)
    with templates_tab:
        data_table(repo.list_table("doc_templates"), "No document templates recorded.")
    with records_tab:
        data_table(repo.list_table("documents", project_id), "No generated documents recorded.")
