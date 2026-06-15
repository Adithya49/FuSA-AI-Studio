from __future__ import annotations

from fusa_ai_studio.core.asil import calculate_asil
from fusa_ai_studio.core.config import AppConfig
from fusa_ai_studio.database.repository import Repository

SAMPLE_KNOWLEDGE = """# ISO 26262 Practical Notes for EV Inverter Safety

Functional safety work products shall preserve traceability from item definition through HARA, safety goals, functional safety concept, technical safety concept, verification, and safety case evidence.

For an EV traction inverter, unintended positive torque, unintended negative torque, loss of torque, and failure to transition to a safe state are representative hazardous events. Safe states often include torque inhibit, controlled torque ramp-down, or opening the high-voltage contactors when appropriate.

Safety goals should be concise, verifiable, and assigned the highest ASIL from linked hazardous events. Functional safety requirements refine safety goals into system-level behavior. Technical safety requirements allocate mechanisms to components such as gate driver, current sensor, rotor position sensor, microcontroller, power stage, watchdog, and communication interface.

RAG responses shall cite retrieved project knowledge and memory so safety engineers can inspect the rationale behind generated text.
"""


def seed_sample_data(repo: Repository, config: AppConfig) -> None:
    project_id = config.default_project_id
    if repo.get_project(project_id):
        return

    repo.upsert_project(
        project_id,
        "EV Traction Inverter Safety Case",
        "Demo ISO 26262 project for an electric vehicle traction inverter and torque control path.",
        "ISO 26262:2018",
    )
    repo.set_setting("active_project_id", project_id)
    repo.set_setting("llm_provider", config.llm.provider)
    repo.set_setting("llm_model", config.llm.model)
    repo.set_setting("vector_backend", config.vector_backend)
    repo.set_setting("embedding_model", config.embedding_model)
    repo.set_setting("chunking_strategy", config.chunking_strategy)

    item_id = repo.insert(
        "items",
        {
            "project_id": project_id,
            "name": "Traction inverter torque control item",
            "purpose": "Convert driver torque request into controlled three-phase motor torque.",
            "boundaries": "Includes inverter control software, microcontroller, gate driver, current sensing, DC-link monitoring, and motor phase actuation. Excludes vehicle dynamics controller and battery management system.",
            "interfaces": "CAN torque request, rotor position sensor, phase current sensors, DC-link voltage sensor, PWM gate drive outputs, diagnostic communication, shutdown line.",
            "assumptions": "ASIL decomposition is not claimed in the baseline sample. Vehicle-level arbitration can request torque inhibit. High-voltage contactors are available as a controlled safe-state actuator.",
        },
    )

    hazards = [
        (
            "Torque command execution",
            "Unintended positive torque",
            "Urban driving near pedestrians",
            "Vehicle accelerates without driver intent",
            3,
            4,
            3,
            "Unexpected acceleration can cause life-threatening collision; exposure is frequent in urban operation; controllability is difficult.",
        ),
        (
            "Regenerative braking",
            "Unintended negative torque",
            "Highway driving on low-friction road",
            "Abrupt deceleration destabilizes the vehicle",
            3,
            3,
            3,
            "Abrupt braking torque can cause loss of control, especially on low friction surfaces.",
        ),
        (
            "Torque availability",
            "Loss of requested torque",
            "Left turn across traffic",
            "Vehicle cannot clear intersection",
            2,
            3,
            2,
            "Loss of propulsion may create exposure to side impact traffic.",
        ),
    ]
    hazard_ids: list[int] = []
    for function_name, malfunction, situation, event, s, e, c, rationale in hazards:
        hazard_id = repo.insert(
            "hazards",
            {
                "project_id": project_id,
                "item_id": item_id,
                "function_name": function_name,
                "malfunction": malfunction,
                "operational_situation": situation,
                "hazardous_event": event,
                "severity": s,
                "exposure": e,
                "controllability": c,
                "asil": calculate_asil(s, e, c),
                "rationale": rationale,
            },
        )
        hazard_ids.append(hazard_id)
        repo.add_trace(project_id, "item", str(item_id), "hazard", str(hazard_id), "analyzed_by", "Hazard derived from item function and operational situation.")

    sg_id = repo.insert(
        "safety_goals",
        {
            "project_id": project_id,
            "hazard_id": hazard_ids[0],
            "goal_code": "SG-001",
            "statement": "The inverter shall prevent unintended positive propulsion torque above a calibrated threshold.",
            "asil": "D",
            "safe_state": "Torque inhibit followed by controlled transition to zero torque.",
            "fault_tolerant_time": "100 ms",
            "verification": "HIL fault injection, torque monitor tests, and vehicle integration test.",
        },
    )
    repo.add_trace(project_id, "hazard", str(hazard_ids[0]), "safety_goal", str(sg_id), "mitigated_by", "Safety goal directly mitigates unintended positive torque.")

    fsc_id = repo.insert(
        "fsc_requirements",
        {
            "project_id": project_id,
            "safety_goal_id": sg_id,
            "req_code": "FSC-001",
            "statement": "The system shall compare requested torque and estimated delivered torque and command torque inhibit when the deviation exceeds the safety threshold.",
            "asil": "D",
            "allocation": "Inverter control software and independent torque monitor.",
            "rationale": "An independent monitor detects unintended torque regardless of the primary control path.",
            "verification": "Requirements-based test and injected sensor/control faults.",
        },
    )
    repo.add_trace(project_id, "safety_goal", str(sg_id), "fsc_requirement", str(fsc_id), "refined_by", "Functional requirement refines SG-001 into monitor behavior.")

    tsc_id = repo.insert(
        "tsc_requirements",
        {
            "project_id": project_id,
            "fsc_requirement_id": fsc_id,
            "req_code": "TSC-001",
            "statement": "The microcontroller safety task shall execute the torque monitor every 10 ms and assert the hardware shutdown line within 30 ms after threshold confirmation.",
            "asil": "D",
            "component": "Microcontroller safety task and gate driver shutdown input.",
            "diagnostic_mechanism": "Program-flow monitor, watchdog supervision, shutdown line readback.",
            "verification": "Timing analysis, watchdog fault injection, and shutdown line electrical test.",
        },
    )
    repo.add_trace(project_id, "fsc_requirement", str(fsc_id), "tsc_requirement", str(tsc_id), "refined_by", "Technical requirement allocates FSC-001 to concrete hardware/software mechanisms.")

    doc_id = repo.insert(
        "knowledge_documents",
        {
            "project_id": project_id,
            "title": "EV Inverter Safety Engineering Notes",
            "source": "Generated sample knowledge base",
            "content": SAMPLE_KNOWLEDGE,
            "doc_type": "guidance",
        },
    )
    repo.add_trace(project_id, "knowledge_document", str(doc_id), "safety_goal", str(sg_id), "supports", "Knowledge note explains representative safety goal structure.")

    repo.add_memory(project_id, "decision", "Baseline project uses ISO 26262:2018 terminology and treats unintended positive torque as ASIL D.", 5)
    repo.add_memory(project_id, "assumption", "Default safe state for torque faults is torque inhibit with controlled transition to zero torque.", 4)
    repo.insert(
        "workflow_tasks",
        {
            "project_id": project_id,
            "title": "Review HARA severity/exposure/controllability ratings",
            "owner": "Safety Manager",
            "status": "In Progress",
            "due_date": "2026-06-30",
            "evidence": "Peer review minutes and HARA checklist.",
        },
    )
    repo.insert(
        "workflow_tasks",
        {
            "project_id": project_id,
            "title": "Complete torque monitor HIL fault injection campaign",
            "owner": "Verification Lead",
            "status": "Open",
            "due_date": "2026-07-15",
            "evidence": "HIL logs, test report, and anomalies.",
        },
    )
    repo.insert(
        "doc_templates",
        {
            "name": "Safety Case Summary",
            "doc_type": "markdown",
            "template": "# {project_name}\n\n## Scope\n{description}\n\n## Key Safety Artifacts\n{artifact_summary}\n\n## Traceability Summary\n{trace_summary}\n",
        },
    )
