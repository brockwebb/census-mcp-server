# Phase 3 System Architecture - Human Language Complexity Translation

## Core Concept: Division of Labor

**tidycensus (Kyle Walker's Domain):** Census API complexity - FIPS codes, API endpoints, MOE calculations, data formatting

**Census MCP Server (Our Domain):** Human language complexity - regional concepts, ambiguous terms, statistical reasoning

---

## Human Language Complexity Examples

### Geographic Complexity Translation
- **"the northeast"** → 6 specific states: CT, ME, MA, NH, RI, VT
- **"rural areas"** → urban-rural classification codes + geographic filtering
- **"major cities"** → population threshold + geography hierarchy decision
- **"Austin"** → Austin, TX (not Austin, MN or 20 other Austins)

### Variable Complexity Translation  
- **"teacher salaries"** → BLS not Census + methodology explanation + where to look
- **"income"** → median not mean + proper universe + statistical caveats
- **"poverty"** → which poverty measure + threshold definition + exclusions

### Statistical Complexity Translation
- **"average"** → median for skewed distributions, mean for normal distributions
- **"compare"** → proper geographic resolution + sample size adequacy  
- **"rate"** → proper denominator + universe definition + reliability checks

---

```mermaid
graph TB
    subgraph "User Layer"
        U[User Query: "How much do teachers make in Austin?"]
        CD[Claude Desktop]
        U --> CD
    end
    
    subgraph "MCP Protocol Layer"
        CD --> MCP[MCP Server Entry Point]
    end
    
    subgraph "Intelligence Layer - Phase 3 Enhanced"
        MCP --> QP[Query Parser & Router]
        QP --> SI[Semantic Index<br/>⚡ <100ms Core Queries]
        QP --> KB[Knowledge Base<br/>📚 RAG Vector Search]
        
        SI --> SM[Static Mappings<br/>🎯 Power Law Variables]
        SI --> FC[Fuzzy Concept Matcher<br/>🔍 Alias Expansion]
        
        KB --> VDB[Vector Database<br/>ChromaDB + Sentence Transformers]
        KB --> DOC[R Documentation Corpus<br/>Census Methodology]
    end
    
    subgraph "Data Retrieval Layer"
        SM --> RE[R Engine<br/>tidycensus Integration]
        FC --> RE
        KB --> RE
        
        RE --> GP[Geography Parser<br/>Location → FIPS Codes]
        RE --> VM[Variable Mapper<br/>Concepts → Census Variables]
        RE --> TC[tidycensus Core<br/>R Subprocess]
    end
    
    subgraph "External APIs"
        TC --> CAPI[Census Bureau APIs<br/>ACS/Decennial Data]
        TC --> TIGER[TIGER Geographic Data<br/>Shapefiles & Boundaries]
    end
    
    subgraph "Response Layer"
        RE --> SP[Statistical Processor<br/>MOE Calculations & Validation]
        SP --> RF[Response Formatter<br/>Context + Methodology Notes]
        RF --> MCP
    end
    
    style SI fill:#e1f5fe,stroke:#01579b,stroke-width:3px
    style SM fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    style FC fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style RE fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
```

## Semantic Index Architecture (Phase 3 Core Innovation)

```mermaid
graph LR
    subgraph "Query Processing Pipeline"
        Q[User Query] --> NLP[NLP Preprocessing<br/>Tokenization + Cleaning]
        NLP --> CR[Concept Recognition<br/>Statistical Concepts]
        CR --> AM[Alias Matching<br/>Fuzzy String Matching]
    end
    
    subgraph "Semantic Index Store"
        AM --> LU[Lookup Engine]
        LU --> SM[Static Mappings<br/>JSON/SQLite FTS]
        LU --> CM[Concept Map<br/>Hierarchical Variables]
        LU --> GM[Geography Map<br/>Place Name → FIPS]
    end
    
    subgraph "Power Law Optimization"
        SM --> CORE[Core Variables<br/>~20 Golden Variables<br/>Handle 64% of Queries]
        SM --> EXT[Extended Variables<br/>~145 Total Mappings<br/>Handle 80% of Queries]
        SM --> FALL[Dynamic Fallback<br/>tidycensus Variable Search<br/>Handle 100% of Queries]
    end
    
    subgraph "Performance Tiers"
        CORE --> T1[Tier 1: <50ms<br/>Direct JSON Lookup]
        EXT --> T2[Tier 2: <100ms<br/>SQLite FTS + Fuzzy Match]
        FALL --> T3[Tier 3: <3s<br/>Full tidycensus Search]
    end
    
    style CORE fill:#c8e6c9,stroke:#2e7d32,stroke-width:3px
    style EXT fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    style FALL fill:#ffcdd2,stroke:#c62828,stroke-width:2px
```

## Knowledge Base & RAG Architecture

```mermaid
graph TB
    subgraph "Document Corpus"
        RD[R Documentation<br/>tidycensus + tigris]
        CM[Census Methodology<br/>ACS Design & Procedures]
        VD[Variable Definitions<br/>Subject Definitions PDF]
        GP[Geography Concepts<br/>TIGER Documentation]
        ST[Statistical Guidance<br/>MOE + CV Best Practices]
    end
    
    subgraph "Vector Database Pipeline"
        RD --> CHUNK[Document Chunking<br/>Smart Structured Splitting]
        CM --> CHUNK
        VD --> CHUNK
        GP --> CHUNK
        ST --> CHUNK
        
        CHUNK --> EMB[Embedding Generation<br/>Sentence Transformers<br/>all-mpnet-base-v2]
        EMB --> STORE[ChromaDB Storage<br/>85MB Vector Index]
    end
    
    subgraph "Query Enhancement"
        UQ[User Query] --> QE[Query Expansion<br/>Add Statistical Context]
        QE --> VS[Vector Search<br/>Semantic Similarity]
        VS --> STORE
        STORE --> CTX[Context Retrieval<br/>Top-K Relevant Docs]
        CTX --> AUG[Response Augmentation<br/>Methodology + Caveats]
    end
    
    style CHUNK fill:#e1f5fe
    style EMB fill:#f3e5f5
    style VS fill:#fff3e0
```

## Phase 3 Performance Architecture

```mermaid
graph LR
    subgraph "Request Flow"
        REQ[Incoming Query] --> CACHE[Cache Check<br/>Redis/SQLite]
        CACHE --> HIT{Cache Hit?}
        HIT -->|Yes| FAST[Return Cached<br/><10ms]
        HIT -->|No| ROUTE[Query Router]
    end
    
    subgraph "Routing Logic"
        ROUTE --> STAT{Static Mappable?}
        STAT -->|Yes| STATIC[Static Lookup<br/><50ms]
        STAT -->|No| FUZZY{Fuzzy Matchable?}
        FUZZY -->|Yes| EXTEND[Extended Search<br/><100ms]
        FUZZY -->|No| DYNAMIC[Dynamic tidycensus<br/><3s]
    end
    
    subgraph "Caching Strategy"
        STATIC --> CACHE_LONG[Cache 24h<br/>Static Data]
        EXTEND --> CACHE_MED[Cache 4h<br/>Extended Lookups]
        DYNAMIC --> CACHE_SHORT[Cache 1h<br/>Dynamic Results]
    end
    
    subgraph "Performance Monitoring"
        FAST --> METRICS[Response Time Metrics]
        STATIC --> METRICS
        EXTEND --> METRICS
        DYNAMIC --> METRICS
        METRICS --> ALERT[Performance Alerts<br/>SLA Monitoring]
    end
    
    style STATIC fill:#c8e6c9,stroke:#2e7d32
    style EXTEND fill:#fff9c4,stroke:#f57f17
    style DYNAMIC fill:#ffcdd2,stroke:#c62828
```

## Phase 3 Design Specifications

### Semantic Index Structure
```json
{
  "core_variables": {
    "population": {
      "variable": "B01003_001",
      "aliases": ["pop", "people", "residents", "total_population"],
      "statistical_note": "Universe: Total population",
      "response_time_target": "30ms"
    },
    "median_income": {
      "variable": "B19013_001", 
      "aliases": ["income", "household_income", "earnings", "salary"],
      "statistical_note": "Inflation-adjusted, excludes group quarters",
      "response_time_target": "30ms"
    }
  },
  "extended_variables": { /* 125 additional mappings */ },
  "concept_hierarchies": {
    "income": ["median_income", "per_capita_income", "family_income"],
    "employment": ["unemployment_rate", "labor_force", "employment_ratio"]
  }
}
```

### Performance Targets
- **Tier 1 (Core):** <50ms for 20 golden variables (64% of queries)
- **Tier 2 (Extended):** <100ms for 145 total variables (80% of queries)  
- **Tier 3 (Dynamic):** <3s for comprehensive tidycensus search (100% coverage)
- **Cache Hit Rate:** >70% for repeated location/variable combinations
- **Uptime SLA:** 99.5% availability

### Geographic Disambiguation Enhancement
```mermaid
graph TD
    LOC[Location Input: "Springfield"] --> AMB{Ambiguous?}
    AMB -->|Yes| DIS[Disambiguation Logic]
    AMB -->|No| DIRECT[Direct FIPS Lookup]
    
    DIS --> MAJOR[Check Major Cities<br/>Population Ranking]
    DIS --> STATE[State Context Clues<br/>"Springfield, IL"]
    DIS --> USER[User Clarification<br/>Present Options]
    
    MAJOR --> RANK[Population-Weighted<br/>Preference]
    STATE --> FIPS[FIPS Code Resolution]
    USER --> SELECT[User Selection]
    
    RANK --> FIPS
    SELECT --> FIPS
    DIRECT --> FIPS
    FIPS --> VALID[Validate Geographic<br/>Hierarchy]
```

### Implementation Priority
1. **Core Variable Static Index** (Week 1)
2. **Fuzzy Matching Engine** (Week 2)  
3. **Caching Layer** (Week 3)
4. **Performance Monitoring** (Week 4)
5. **Geographic Disambiguation** (Week 5-6)

This architecture maintains the current functionality while adding the performance optimizations needed for production-scale deployment.