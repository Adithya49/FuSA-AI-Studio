from __future__ import annotations

from datetime import datetime

import streamlit as st

from fusa_ai_studio.core.services import Services


SAMPLE_INPUTS = {
    "Item Definition": """# Item Definition Input Pack

## Vehicle Context
Electric SUV with front axle traction inverter. The inverter receives torque requests from the vehicle control unit over CAN-FD.

## Item Boundary
Includes torque request handling, inverter control software, MCU, gate driver, current sensing, DC-link sensing, resolver interface, PWM generation, and shutdown path.

## External Interfaces
- Vehicle control unit torque request
- Battery management system high-voltage availability
- Resolver position input
- Phase current sensors
- Gate driver diagnostics
- High-voltage contactor feedback

## Assumptions
The vehicle controller can request torque inhibit. The inverter can command a controlled zero-torque state.
""",
    "HARA": """# HARA Input Pack

## Operating Situations
- Urban driving near pedestrians
- Highway driving on low-friction road
- Left turn across traffic
- Parking maneuver near obstacles

## Candidate Malfunctions
- Unintended positive torque
- Unintended negative torque
- Loss of requested torque
- Delayed transition to safe state

## Rating Guidance
Unintended positive torque during urban operation may be S3/E4/C3. Loss of requested torque during left-turn maneuver may be S2/E3/C2.
""",
    "Safety Goals": """# Safety Goal Input Pack

## Hazard Linkage
Use the highest ASIL from linked hazardous events. Each safety goal must state the unsafe behavior prevented, safe state, fault tolerant time, and verification concept.

## Candidate Safe States
- Torque inhibit
- Controlled ramp-down to zero torque
- Gate driver shutdown
- High-voltage contactor opening when vehicle-level conditions permit
""",
    "FSC": """# Functional Safety Concept Input Pack

## Functional Mechanisms
- Independent torque monitoring
- Plausibility check between requested torque and estimated delivered torque
- Sensor plausibility checks for current and rotor position
- Watchdog-supervised safety task

## Allocation Candidates
Inverter application software, safety monitor software, MCU safety island, gate driver shutdown input, vehicle controller torque arbitration.
""",
    "TSC": """# Technical Safety Concept Input Pack

## Technical Mechanisms
- 10 ms safety monitor task
- ADC range and plausibility diagnostics
- Resolver signal plausibility
- Gate driver fault feedback
- Hardware shutdown line readback
- Watchdog and program-flow supervision

## Verification Inputs
Timing analysis, HIL fault injection, software unit tests, diagnostic coverage analysis, electrical shutdown validation.
""",
    "Traceability": """# Traceability Input Pack

## Required Chains
Item function -> hazardous event -> safety goal -> FSC requirement -> TSC requirement -> verification evidence.

## Audit Criteria
Every ASIL-rated hazardous event needs at least one safety goal. Every safety goal needs one or more FSC requirements. Every FSC requirement needs technical allocation or a documented rationale.
""",
    "Workflow Automation": """# Workflow Input Pack

## Standard Review Steps
- Item definition review
- HARA moderation
- Safety goal approval
- FSC/TSC consistency review
- Verification evidence collection
- Safety case release review
""",
    "Document Factory": """# Document Factory Input Pack

## Expected Documents
- Item definition report
- HARA report
- Safety goals and FSC report
- Technical safety concept report
- Traceability matrix
- Safety case summary
""",
}


def render_workproduct_inputs(services: Services, project_id: str, workproduct: str) -> None:
    repo = services.repo
    with st.expander(f"Inputs for {workproduct}", expanded=False):
        st.caption("Upload or paste source material for this work product. It is saved to the project knowledge base, chunked, embedded, and used by RAG.")
        uploaded = st.file_uploader(
            "Upload source data",
            type=["txt", "md", "csv", "log"],
            key=f"{workproduct}_upload",
        )
        title = st.text_input("Input title", f"{workproduct} input pack", key=f"{workproduct}_title")
        manual = st.text_area("Paste source data", SAMPLE_INPUTS.get(workproduct, ""), key=f"{workproduct}_manual", height=180)
        cols = st.columns(3)
        if cols[0].button("Save pasted input", key=f"{workproduct}_save_manual"):
            services.knowledge.add_document(project_id, title, f"{workproduct} manual input", manual, workproduct)
            repo.add_memory(project_id, "workproduct_input", f"Added {workproduct} manual input: {title}", 3)
            st.success("Input saved and indexed.")
        if cols[1].button("Upload and index", key=f"{workproduct}_save_upload", disabled=uploaded is None):
            if uploaded is not None:
                content = uploaded.read().decode("utf-8", errors="replace")
                services.knowledge.add_document(project_id, title or uploaded.name, uploaded.name, content, workproduct)
                repo.add_memory(project_id, "workproduct_input", f"Uploaded {uploaded.name} for {workproduct}.", 3)
                st.success("Upload saved and indexed.")
        if cols[2].button("Create sample input", key=f"{workproduct}_sample"):
            sample = SAMPLE_INPUTS.get(workproduct, f"# {workproduct} Sample Input\n\nGenerated sample input for {workproduct}.")
            sample_title = f"{workproduct} sample input {datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            services.knowledge.add_document(project_id, sample_title, "Generated sample work-product input", sample, workproduct)
            repo.add_memory(project_id, "sample_input", f"Generated sample input for {workproduct}.", 2)
            st.success("Sample input created and indexed.")
