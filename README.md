# FuSA AI Studio

AI-Powered Functional Safety Engineering Platform for ISO 26262

FuSA AI Studio is an intelligent engineering assistant that helps automotive safety engineers generate, manage, validate, and trace Functional Safety work products across the complete ISO 26262 lifecycle.

Built with Multi-LLM support, RAG architecture, ChromaDB, Project Memory, Workflow Automation, and AI-powered artifact generation.

---

## Key Features

### Functional Safety Lifecycle

- Item Definition
- Hazard Analysis and Risk Assessment (HARA)
- Safety Goals
- Functional Safety Concept (FSC)
- Technical Safety Concept (TSC)
- Safety Requirements
- FMEA
- FMEDA
- Fault Tree Analysis (FTA)
- Verification
- Validation
- Safety Case
- Confirmation Measures
- Tool Qualification

### AI-Powered Capabilities

- Multi-LLM Support
  - Gemini
  - OpenAI
  - Claude
  - Ollama
  - OpenRouter
  - Local Models

- AI Safety Engineering Agents
- Artifact Auto Generation
- Traceability Generation
- Safety Requirement Generation
- HARA Assistance
- FMEA Assistance
- Safety Case Assistance

### Knowledge Management

- Document Upload
- PDF Processing
- DOCX Processing
- Excel Processing
- Chunking Engine
- Embedding Engine
- ChromaDB Vector Store
- RAG-Based Search
- Project Memory

### Traceability

- End-to-End Safety Traceability
- Coverage Analysis
- Gap Detection
- Impact Analysis
- Interactive Graph View

### Automation

- Lifecycle Workflow Automation
- Auto Generation of Downstream Work Products
- Template Factory
- Document Factory
- Complete FuSA Package Generation

---

## Architecture

User Input
→ Project Memory
→ Knowledge Base
→ ChromaDB Vector Search
→ RAG Orchestrator
→ Multi-LLM Layer
→ Safety Agents
→ Artifact Generation
→ Traceability Engine
→ Export Engine

---

## Tech Stack

Frontend:
- Streamlit
- Plotly
- AG Grid

Backend:
- Python
- SQLAlchemy
- SQLite

AI:
- LangChain
- LlamaIndex

Vector Databases:
- ChromaDB
- FAISS
- Qdrant

Document Processing:
- PyMuPDF
- python-docx
- openpyxl

---

## Future Vision

Generate a complete ISO 26262 safety lifecycle package from a system description using AI-assisted engineering workflows and traceable safety evidence.

---

## Status

🚧 Active Development

Built for:
- Automotive Functional Safety
- ADAS Safety Engineering
- AI-Assisted Safety Analysis
- AMD AI Hackathon