# Sprint 2 Journey Map - Container + Basic RAG

## 🎯 Sprint Goal
Build a working Docker container with basic RAG that can be distributed and used with Claude Desktop.

## 📋 Success Criteria
- [ ] `docker run census-mcp` works on any machine
- [ ] Claude Desktop integration functional
- [ ] Basic RAG enhances responses with R documentation
- [ ] Container size under 1GB
- [ ] Cold start under 30 seconds

---

## Week 1: Foundation & Core Components

### Day 1-2: Knowledge Base Foundation
**Goal**: Build minimal but functional RAG system

#### Tasks:
- [ ] **Create knowledge base structure**
  ```
  knowledge-base/
  ├── source-docs/          # Original documents
  ├── build-kb.py          # Build script
  └── README.md            # Documentation sources
  ```

- [ ] **Collect POC document set** (~50MB max):
  - [ ] tidycensus package documentation
  - [ ] ACS methodology guide (key sections)
  - [ ] Top 20 Census variables reference
  - [ ] Basic geographic concepts doc

- [ ] **Build simple vectorization script**:
  - [ ] OpenAI embeddings API integration
  - [ ] ChromaDB setup and indexing
  - [ ] Document chunking strategy

**Deliverable**: Working `build-kb.py` that creates vector DB from docs

---

### Day 3-4: Container Architecture
**Goal**: Get Docker containerization working reliably

#### Tasks:
- [ ] **Fix R integration for containers**:
  - [ ] Update `data_retrieval/r_engine.py` for container environment
  - [ ] Test R subprocess execution in Docker
  - [ ] Handle R package dependencies in Dockerfile

- [ ] **Create multi-stage Dockerfile**:
  - [ ] Stage 1: R environment + tidycensus
  - [ ] Stage 2: Python + MCP dependencies  
  - [ ] Stage 3: Knowledge base build
  - [ ] Stage 4: Final runtime image

- [ ] **Build and test scripts**:
  - [ ] `build_container.sh` - Build with progress tracking
  - [ ] `test_container.sh` - Integration tests

**Deliverable**: Container that builds successfully and passes basic tests

---

### Day 5: Integration Testing
**Goal**: End-to-end validation

#### Tasks:
- [ ] **Container functionality test**:
  - [ ] MCP server starts correctly
  - [ ] R engine retrieves Census data
  - [ ] Knowledge base responds to queries
  - [ ] Health checks pass

- [ ] **Claude Desktop integration test**:
  - [ ] Container works with Claude Desktop config
  - [ ] Test queries return enhanced responses
  - [ ] Error handling works gracefully

**Deliverable**: Working container that integrates with Claude Desktop

---

## Week 2: Polish & Distribution

### Day 6-7: Response Quality & Error Handling
**Goal**: Professional-grade user experience

#### Tasks:
- [ ] **Enhance MCP response formatting**:
  - [ ] Add knowledge base context to responses
  - [ ] Include source citations
  - [ ] Format margins of error clearly
  - [ ] Add methodology notes

- [ ] **Production error handling**:
  - [ ] Graceful degradation when KB unavailable
  - [ ] Clear error messages for users
  - [ ] Fallback to static responses if needed
  - [ ] Proper logging without stack traces

**Deliverable**: Responses that feel professional and informative

---

### Day 8-9: Performance & Optimization
**Goal**: Container ready for distribution

#### Tasks:
- [ ] **Performance optimization**:
  - [ ] Container startup time optimization
  - [ ] Memory usage profiling and optimization
  - [ ] Knowledge base query performance
  - [ ] Docker layer optimization

- [ ] **Documentation**:
  - [ ] User installation guide
  - [ ] Claude Desktop configuration guide
  - [ ] Troubleshooting guide
  - [ ] API key setup instructions

**Deliverable**: Optimized container with complete user documentation

---

### Day 10: Launch Preparation
**Goal**: Ready for public distribution

#### Tasks:
- [ ] **Final validation**:
  - [ ] Test on fresh machines (Mac/Linux/Windows)
  - [ ] Validate Claude Desktop integration
  - [ ] Performance benchmarks
  - [ ] Security review

- [ ] **Distribution setup**:
  - [ ] GitHub LFS for knowledge base
  - [ ] Container registry publishing
  - [ ] Release documentation
  - [ ] Demo video/screenshots

**Deliverable**: Shippable product ready for users

---

## 🚨 Focus Rules (When You Get Distracted)

### The Three Questions:
1. **Does this help users get Census data easier?** If no, skip it.
2. **Is this needed for the container to work?** If no, defer to Sprint 3.
3. **Can I ship without this?** If yes, add to backlog.

### Scope Boundaries:
**IN SCOPE** (Sprint 2):
- Container builds and runs
- Basic RAG with POC documents
- Claude Desktop integration
- Simple error handling

**OUT OF SCOPE** (Sprint 3+):
- Comprehensive document corpus
- Advanced RAG features
- HTTP API mode
- Performance optimization beyond basics
- Advanced geographic parsing

### Daily Check-in Questions:
- What did I complete yesterday?
- What's blocking me today?
- Am I on track for the weekly deliverable?
- Do I need to cut scope to stay focused?

---

## 🏆 Weekly Deliverables

### End of Week 1:
Working Docker container that:
- Builds successfully
- Runs MCP server
- Has basic knowledge base
- Integrates with Claude Desktop

### End of Week 2:
Production-ready container that:
- Users can install with one command
- Provides enhanced Census responses
- Handles errors gracefully
- Is documented and supported

---

## 🔥 Emergency Scope Cuts (If Behind Schedule)

**Week 1 Cuts**:
- Use static knowledge instead of RAG
- Simplify R integration (fewer features)
- Basic container without optimization

**Week 2 Cuts**:
- Ship with basic documentation
- Minimal error handling
- Skip performance optimization

**Nuclear Option**:
- Static responses only (no RAG)
- Basic container with R integration
- Manual installation guide

---

## 📞 Daily Standup Format

**What I completed**:
- [ ] Specific task from roadmap

**What I'm working on today**:
- [ ] Next task with specific outcome

**Blockers/Questions**:
- Any technical decisions needed
- Any scope clarification needed

**On track?**:
- Yes/No for weekly deliverable
- Any scope adjustments needed