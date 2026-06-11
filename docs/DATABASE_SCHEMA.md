# Database Schema

The canonical schema is implemented in `fusa_ai_studio/database/schema.sql`.

```mermaid
erDiagram
    projects ||--o{ items : owns
    projects ||--o{ hazards : analyzes
    projects ||--o{ safety_goals : defines
    projects ||--o{ fsc_requirements : allocates
    projects ||--o{ tsc_requirements : refines
    projects ||--o{ knowledge_documents : indexes
    projects ||--o{ project_memory : remembers
    projects ||--o{ workflow_tasks : tracks
    projects ||--o{ documents : generates
    knowledge_documents ||--o{ knowledge_chunks : contains
    hazards ||--o{ safety_goals : mitigated_by
    safety_goals ||--o{ fsc_requirements : refined_by
    fsc_requirements ||--o{ tsc_requirements : refined_by
    trace_links }o--|| projects : scoped_to
```

All artifacts include timestamps. AI interactions record provider, model, prompt, retrieved context, and response for traceability.
