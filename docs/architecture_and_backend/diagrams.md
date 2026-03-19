# Integronix System Diagrams

This document contains all the architectural, pipeline, and data model diagrams for the Integronix system.

## 1. Use Case Diagram

This diagram illustrates the primary actors and their interactions with the Integronix system, from initial setup to the final coding and auditing process.

```mermaid
graph TD
    subgraph "Integronix Platform"
        A[Hospital Administrator] -->|1. Signs up and configures organization| B(Organization Setup)
        B -->|2. Sets ICD version (10/11), claim scheme, API keys| C(System Configuration)
        
        D[Medical Coder / Auditor] -->|3. Uploads clinical document (PDF/Text)| E(API Endpoint: /code/run-pdf)
        E --> F{Coding & Auditing Pipeline}
        
        F -->|4. Processes Document| G(Document Processing Node)
        G -->|5. Extracts Clinical Entities| H(Clinical Extraction Node - LLM)
        H -->|6. Resolves CPT Codes| I(CPT Resolver Node)
        I -->|7. Resolves SNOMED-CT Concepts| J(SNOMED Resolver Node)
        
        J --> K{ICD Version Routing}
        K -- ICD-11 --> L(WHO API Service)
        K -- ICD-10 --> M(SNOMED-ICD10 Mapping Service)
        
        L --> N(Candidate Generation)
        M --> N
        
        subgraph "Fallback Mechanism"
            direction LR
            N -- No candidates found --> O(Vector Embedding Search)
            O --> P(Similarity Search in DB)
            P --> N
        end

        N -->|8. Selects final code| Q(Deterministic ICD Decision Node)
        Q -->|9. Compares with original codes| R(Audit Comparison Node)
        R -->|10. Scores risk| S(Risk Scoring Node)
        S -->|11. Calculates financial impact| T(Financial Calculator Node)
        
        T -->|12. Generates final report| U(Final JSON Output)
        U -->|13. Returns detailed analysis to user| D
    end

    subgraph "External Systems"
        V(WHO ICD-11 API)
        L --> V
    end

    classDef actor fill:#ff9,stroke:#333,stroke-width:2px;
    class A,D actor;
```

## 2. System Architecture Diagram

This diagram provides a comprehensive overview of the entire Integronix system, including the frontend, backend, database, and external services.

```mermaid
graph TD
    subgraph "User Interface"
        A[User Browser] -->|Interacts via Next.js App| B(Frontend: Next.js)
    end

    subgraph "Backend Infrastructure (FastAPI)"
        B -->|API Requests (HTTPS)| C{API Gateway / Load Balancer}
        C --> D(FastAPI Application)
        
        subgraph "Core Services"
            D --> E(Routes: /code, /cases, etc.)
            E --> F(Agentic Pipeline: LangGraph)
            D --> G(Services: ICD Provider, PDF Service, etc.)
            D --> H(Authentication & Authorization)
        end

        subgraph "Agentic Pipeline (LangGraph)"
            direction LR
            F --> F1(Doc Processor)
            F1 --> F2(Clinical Extractor)
            F2 --> F3(SNOMED/CPT Resolvers)
            F3 --> F4(ICD Mapping/WHO API)
            F4 --> F5(Vector Search Fallback)
            F5 --> F6(Deterministic Decision Engine)
            F6 --> F7(Auditing & Financial Analysis)
        end
    end

    subgraph "Data & Storage Layer"
        I(Supabase: PostgreSQL)
        I --> J(pgvector: For Embeddings)
        I --> K(Tables: Cases, Claims, Users, SNOMED-ICD Map)
        
        G --> I
        F5 --> J
    end

    subgraph "External Services & APIs"
        L(Groq API) -->|Provides LLM for Extraction| F2
        M(WHO ICD API) -->|Provides ICD-11/10 Data| F4
        N(SentenceTransformers) -->|Generates Embeddings| O(Embedding Generation Scripts)
        O --> J
    end

    subgraph "DevOps & Deployment"
        P(Docker/Docker Compose) -->|Containerizes Backend| D
        Q(GitHub Actions) -->|CI/CD| P
    end

    classDef fe fill:#cde4ff,stroke:#333;
    class A,B fe;
    classDef be fill:#d5e8d4,stroke:#333;
    class C,D,E,F,G,H,F1,F2,F3,F4,F5,F6,F7 be;
    classDef db fill:#ffe6cc,stroke:#333;
    class I,J,K,O db;
    classDef ext fill:#f8cecc,stroke:#333;
    class L,M,N ext;
    classDef devops fill:#e1d5e7,stroke:#333;
    class P,Q devops;
```

## 3. Agent Architecture Diagram (LangGraph Pipeline)

This diagram details the flow of control and data within the LangGraph-based agentic pipeline.

```mermaid
graph TD
    A[Start: CodingState Input] --> B(Doc_Processor_Node);
    B --> C(Clinical_Extractor_Node);
    C --> D(CPT_Resolver_Node);
    D --> E(SNOMED_Resolver_Node);
    E --> F{Route after SNOMED};

    F --"use_who_api is true"--> G[WHO_ICD_Service_Call];
    F --"use_who_api is false"--> H(SNOMED_ICD_Mapping_Node);

    G --> I{Route after Mapping};
    H --> I;

    I --"Candidates Found"--> J(ICD_Decision_Node);
    I --"No Candidates Found"--> K(ICD_Embedding_Node);
    K --> J;

    J --> L(Audit_Comparison_Node);
    L --> M(Risk_Scoring_Node);
    M --> N(Financial_Calculator_Node);
    N --> O[End: Final CodingState Output];

    subgraph "State Modification"
        direction LR
        B --"Updates state.document_chunks"--> B
        C --"Updates state.clinical_summary"--> C
        D --"Updates state.cpt_codes"--> D
        E --"Updates state.snomed_concepts"--> E
        G --"Updates state.candidate_icd_codes"--> G
        H --"Updates state.candidate_icd_codes"--> H
        K --"Updates state.candidate_icd_codes"--> K
        J --"Updates state.final_icd_code"--> J
        L --"Updates state.audit_results"--> L
        M --"Updates state.risk_score"--> M
        N --"Updates state.financial_impact"--> N
    end

    style A fill:#cde4ff,stroke:#333,stroke-width:2px
    style O fill:#cde4ff,stroke:#333,stroke-width:2px
    style F fill:#ffe6cc,stroke:#333,stroke-width:2px
    style I fill:#ffe6cc,stroke:#333,stroke-width:2px
```

## 4. Database ER Diagram

This diagram shows the entity relationships within the PostgreSQL database managed by Supabase.

```mermaid
erDiagram
    USERS ||--o{ ORGANIZATIONS : "has"
    ORGANIZATIONS ||--o{ CASES : "owns"
    ORGANIZATIONS {
        uuid id PK
        string name
        json settings "ICD version, claim scheme"
    }
    USERS {
        uuid id PK
        string email
        uuid organization_id FK
    }
    CASES {
        uuid id PK
        uuid organization_id FK
        text clinical_document
        jsonb coding_state "Full LangGraph state"
        timestamptz created_at
    }
    CLAIMS ||--o{ CASES : "relates to"
    CLAIMS {
        uuid id PK
        uuid case_id FK
        string status
        jsonb claim_details
    }
    CPT_CODES {
        int id PK
        string code
        string description
        vector embedding "384-dim"
    }
    ICD10_CODES {
        int id PK
        string code
        string description
        vector embedding "384-dim"
    }
    SNOMED_ICD_MAP {
        bigint snomed_concept_id PK
        string icd_10_code PK
    }

    CASES }o--|| CPT_CODES : "references"
    CASES }o--|| ICD10_CODES : "references"
```

## 5. Class Diagram (Python Backend)

This diagram outlines the key Python classes and their relationships in the backend.

```mermaid
classDiagram
    direction LR

    class ICDProvider {
        <<Service>>
        +get_icd_results(text, org_settings) Result
    }

    class WhoIcdService {
        <<Service>>
        -client_id: str
        -client_secret: str
        -token: str
        -_get_access_token()
        +search_icd(text, version) Result
    }

    class IcdService {
        <<Service>>
        +search_icd_by_text(text) Result
        +get_snomed_mappings(snomed_id) Result
    }

    class EmbeddingService {
        <<Service>>
        -model: SentenceTransformer
        +generate_embedding(text) Vector
    }
    
    ICDProvider ..> WhoIcdService : uses
    ICDProvider ..> IcdService : uses

    class Graph {
        <<Agent>>
        -graph: CompiledGraph
        +build_integronix_graph() CompiledGraph
        +run(state) CodingState
    }

    class CodingState {
        <<TypedDict>>
        organization_id: str
        clinical_summary: str
        snomed_concepts: list
        candidate_icd_codes: list
        final_icd_code: dict
        ...
    }

    Graph o-- CodingState : manages

    class SnomedResolverNode {
        <<Agent Node>>
        -icd_provider: ICDProvider
        +run(state) CodingState
    }

    class IcdDecisionNode {
        <<Agent Node>>
        -_specificity_score(code)
        -_negation_penalty(summary, code)
        +run(state) CodingState
    }

    Graph ..> SnomedResolverNode : contains
    Graph ..> IcdDecisionNode : contains
    SnomedResolverNode ..> ICDProvider : uses
```
