# Sprint 2 Container Architecture

## Container Build Process
```mermaid
flowchart TD
    A[Source Code + Docs] --> B[Multi-Stage Docker Build]
    
    B --> C[Stage 1: R Environment]
    C --> C1[Ubuntu + R + tidycensus]
    
    B --> D[Stage 2: Python Environment] 
    D --> D1[Python + MCP + sentence-transformers]
    
    B --> E[Stage 3: Knowledge Base Build]
    E --> E1[Collect POC Documents]
    E1 --> E2[OpenAI Embeddings API]
    E2 --> E3[Build ChromaDB]
    E3 --> E4[Pre-built Vector DB]
    
    B --> F[Stage 4: Final Container]
    C1 --> F
    D1 --> F  
    E4 --> F
    F --> G[census-mcp:latest<br/>~900MB Container]
```

## Runtime Container Architecture
```mermaid
graph TB
    subgraph "Docker Container: census-mcp"
        subgraph "MCP Server Layer"
            MCP[MCP Server<br/>STDIO Interface]
        end
        
        subgraph "Intelligence Layer"
            KB[Knowledge Base<br/>ChromaDB + Embeddings]
            VAR[Variable Mappings<br/>Static + RAG]
        end
        
        subgraph "Data Layer"
            R[R Engine<br/>tidycensus subprocess]
            API[Census Bureau APIs]
        end
        
        MCP --> KB
        MCP --> VAR
        MCP --> R
        R --> API
        KB --> VAR
    end
    
    subgraph "External Integration"
        CLAUDE[Claude Desktop]
        USER[User Queries]
    end
    
    USER --> CLAUDE
    CLAUDE --> MCP
    MCP --> CLAUDE
    CLAUDE --> USER
    
    style MCP fill:#e1f5fe
    style KB fill:#f3e5f5
    style R fill:#fff3e0
```

## Query Processing Flow
```mermaid
sequenceDiagram
    participant U as User
    participant C as Claude Desktop
    participant M as MCP Server
    participant K as Knowledge Base
    participant R as R Engine
    participant A as Census API
    
    U->>C: "What's the population of Baltimore?"
    C->>M: MCP tool call
    M->>K: Get variable context ("population")
    K-->>M: B01003_001 + definition + notes
    M->>K: Parse location ("Baltimore")
    K-->>M: Geography: place, State: MD
    M->>R: get_acs_data(place="Baltimore", state="MD", vars=["B01003_001"])
    R->>A: tidycensus API call
    A-->>R: ACS data + MOE
    R-->>M: Formatted response
    M->>K: Enhance response with context
    K-->>M: Add methodology notes
    M-->>C: Enhanced response with sources
    C-->>U: "Baltimore has 585,708 people (2022 ACS 5-year)"
```

## Container Deployment Model
```mermaid
graph LR
    subgraph "Development"
        DEV[Local Development]
        BUILD[docker build]
        TEST[Integration Tests]
    end
    
    subgraph "Distribution"
        HUB[Docker Hub<br/>census-mcp:latest]
        LFS[GitHub LFS<br/>Knowledge Base]
    end
    
    subgraph "User Deployment"
        PULL[docker pull]
        RUN[docker run -e ANTHROPIC_API_KEY=...]
        CONFIG[Claude Desktop Config]
    end
    
    DEV --> BUILD
    BUILD --> TEST
    TEST --> HUB
    LFS --> HUB
    HUB --> PULL
    PULL --> RUN
    RUN --> CONFIG
    
    style HUB fill:#e8f5e8
    style RUN fill:#fff3e0
```

## Key Architecture Decisions

### Build-Time vs Runtime
- **Knowledge Base**: Built during container build (OpenAI embeddings)
- **R Environment**: Pre-installed during build
- **MCP Server**: Starts immediately at runtime

### Data Flow
1. **User Query** → Claude Desktop → MCP Server
2. **Variable Mapping** → Knowledge Base (RAG or static)
3. **Data Retrieval** → R subprocess → Census API
4. **Response Enhancement** → Knowledge Base context
5. **Formatted Response** → Claude Desktop → User

### Container Size Budget
- Base Ubuntu + R + Python: ~400MB
- Knowledge Base (vector DB): ~300MB  
- Sentence transformer model: ~90MB
- Application code: ~50MB
- **Total: ~840MB**