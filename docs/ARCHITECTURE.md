# FuSA AI Studio Architecture

## Modules

- `app.py`: Streamlit entry point, navigation, session bootstrap.
- `fusa_ai_studio.core`: configuration, runtime services, sample data, trace helpers.
- `fusa_ai_studio.database`: SQLite schema execution and repository functions.
- `fusa_ai_studio.ai`: provider-neutral LLM layer, embeddings, chunking, RAG orchestration, prompt templates.
- `fusa_ai_studio.knowledge`: document ingestion, chunk persistence, indexing.
- `fusa_ai_studio.vectorstores`: ChromaDB default adapter plus SQLite and in-memory alternatives.
- `fusa_ai_studio.modules`: dashboard, item definition, HARA, safety goals, FSC, TSC, traceability, assistant, workflow, document factory, settings.
- `fusa_ai_studio.ui`: reusable Streamlit rendering helpers.

## Data Flow

1. Users create or update safety artifacts in Streamlit modules.
2. The repository persists artifacts and trace links in SQLite.
3. Knowledge documents and artifact summaries are chunked with the selected chunking strategy.
4. Chunks are embedded with the selected embedding model.
5. The selected vector database stores embeddings and metadata.
6. Every AI feature calls the RAG engine, which retrieves knowledge, project memory, and trace context before invoking the selected LLM.
7. AI interactions and generated outputs are stored for auditability.

## Production Defaults

- Database: SQLite at `data/fusa_ai_studio.db`.
- Vector database: ChromaDB at `data/chroma`.
- Embedding model: deterministic local hash embedding so the system runs without cloud credentials.
- LLM provider: local deterministic FuSA assistant unless the user configures a provider.
- Sample data: EV traction inverter safety case.

## Traceability

Trace links use a common table with typed endpoints. Supported artifact types include `item`, `hazard`, `safety_goal`, `fsc_requirement`, `tsc_requirement`, `knowledge_document`, `memory`, and `document`.
