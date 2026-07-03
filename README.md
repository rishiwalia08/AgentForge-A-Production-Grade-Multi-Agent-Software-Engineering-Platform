# AgentForge: A Production-Grade Multi-Agent Software Engineering Platform

AgentForge is a production-hardened, horizontally scalable, multi-agent software development platform modeled after modern AI workspaces like Devin and Cursor. It leverages **LangGraph**, **FastAPI**, **Next.js**, and a distributed broker architecture to orchestrate collaborative agent networks that plan, search, code, test, secure, and debug software repositories.

---

## 🚀 Core Capabilities

- **LangGraph Orchestrator Network**: Adaptive routing coordinated by a centralized **Supervisor Agent** that dynamically delegates subtasks to dedicated specialist nodes.
- **Restricted Tool Execution (RBAC)**: Fine-grained Role-Based Access Control (RBAC) mapping context-specific permissions (e.g. the `TestingAgent` is locked to a restricted `TestRunnerTool` and denied generic shell tools).
- **Hybrid Security Guardrails**: Code modifications and terminal commands pass a multi-layered check combining static rule analysis, permission policies, and real-time LLM risk classification.
- **Safe Workspace Checkpointing**: Tracked modifications are saved as discrete agent checkpoints. The rollback engine ignores clean workspace assets, restores changed files, and deletes untracked files generated since the agent run began.
- **AST-Based Codebase RAG**: AST code parsers extract classes, functions, and import references to generate hierarchical code dependency graphs and power hybrid keyword/semantic search.
- **Dual SQL & Vector Memory**: SQLite/PostgreSQL for relational schemas (history, preferences, trace telemetry) + FAISS Vector database for semantic context retrieval.
- **Human-in-the-Loop Interrupts**: Pauses on dangerous commands or policy warnings, serializes the exact execution state, and resumes once approved by the user.

---

## 📐 Architecture Overview

```
                      +-------------------+
                      |   Next.js UI      |
                      +---------+---------+
                                | (WebSockets & JSON REST)
                      +---------v---------+
                      |   FastAPI REST    |
                      +---------+---------+
                                | (Enqueue Jobs)
                      +---------v---------+
                      |    Redis Broker   |
                      +---------+---------+
                                | (Worker Queue)
                      +---------v---------+
                      |   Celery Workers  |
                      +---------+---------+
                                | (Compile Graph)
                    +-----------v-----------+
                    |  LangGraph Agent Loop |
                    +-----------+-----------+
                                |
    +---------------------------+---------------------------+
    |                           |                           |
+---v---+                   +---v---+                   +---v---+
| Memory|                   | Tools |                   |  RAG  |
+-------+                   +-------+                   +-------+
```

### 1. Collaborative Agent Network
* **Supervisor Agent**: Receives goals, develops high-level plans, delegates tasks, and synthesizes final solutions.
* **Research Agent**: Scans directories, processes symbols, and evaluates dependencies using Codebase RAG.
* **Developer Agent**: A ReAct loop executing filesystem writes, directory updates, and Git operations.
* **Testing Agent**: Executes restricted testing routines (`pytest`, `vitest`, `npm test`) and captures execution trace outputs.
* **Debugging Agent**: Analyzes stack trace outputs and historical memory logs to build structural repair plans.
* **Security Agent**: Reviews plans and checks commands against safety rules and policies to prevent malicious activity.
* **Reflection Agent**: Inspects finalized execution graphs to extract lessons and save them to memory.

---

## 🛠️ Technology Stack

* **Backend Orchestration**: Python 3.11/3.12, FastAPI, LangGraph, Pydantic V2, SQLAlchemy.
* **Database & Cache**: PostgreSQL (persisted volumes), SQLite (local profiling), Redis (job queues and real-time event bus).
* **Job Queue / Worker**: Celery (horizontal task worker architecture).
* **AI & Embeddings**: Ollama (local model inference), Gemini API / OpenAI API (via cloud Colab adapters).
* **Vector Store**: FAISS (Facebook AI Similarity Search) index wrapper.
* **Frontend Interface**: Next.js 14, TypeScript, Tailwind CSS, shadcn/ui.
* **Docker Deployment**: Multi-stage Docker builds compiled with healthcheck dependencies.

---

## 📁 Repository Directory Structure

```
├── backend/
│   ├── app/
│   │   ├── agents/          # Specialist node implementations & LLM interfaces
│   │   ├── api/             # REST routing & authentication endpoints
│   │   ├── core/            # System config, logger, metric models, and event bus
│   │   ├── db/              # SQLAlchemy schemas, checkpoints, and repositories
│   │   ├── graph/           # Centralized LangGraph supervisor and state configuration
│   │   ├── knowledge/       # AST indexer, document parsers, and RAG retriever
│   │   ├── observability/   # AgentTracer, reflection manager, and telemetry
│   │   ├── schemas/         # REST response/request validation schemas
│   │   ├── services/        # Business logic, memory manager, and runner engine
│   │   └── tools/           # File, terminal, testing, and Git wrappers (RBAC)
│   ├── tests/               # 60+ unit, integration, and performance tests
│   └── Dockerfile           # Multi-stage python:3.11-slim API container
├── frontend/
│   ├── app/                 # Next.js page routing (dashboard, workspace, login)
│   ├── hooks/               # WebSocket event connection handlers
│   └── Dockerfile           # Next.js multi-stage container
├── docker-compose.yml       # Production orchestration file
├── main.ipynb               # Google Colab runner & interactive demo adapter
└── README.md                # Documentation
```

---

## 🚀 Getting Started

### Option A: Local Production Mode (Docker Compose)
To run the complete production microservices stack (Next.js, FastAPI, Redis, PostgreSQL, Celery):

1. **Clone the repository**:
   ```bash
   git clone https://github.com/rishiwalia08/AgentForge-A-Production-Grade-Multi-Agent-Software-Engineering-Platform.git
   cd AgentForge-A-Production-Grade-Multi-Agent-Software-Engineering-Platform
   ```

2. **Configure Environment Variables**:
   Create a `.env` file in the root folder with configuration settings matching your providers (see `backend/.env.example`).

3. **Start the services**:
   ```bash
   docker-compose up --build
   ```

4. **Access the platform**:
   - Next.js UI: `http://localhost:3000`
   - FastAPI REST API: `http://localhost:8000`

---

### Option B: Google Colab Runner Mode
If you lack a local GPU or want to test the platform without installing Docker:

1. Open a Google Colab notebook and load **[main.ipynb](main.ipynb)**.
2. Select your provider (`MODEL_PROVIDER = "gemini"` or `"openai"`).
3. Set your API keys in Colab's left-hand Userdata panel.
4. Run the health check, index files into SQLite, and execute scenarios like adding features or analyzing code.

---

## 🧪 Testing & Verification

We maintain a comprehensive, offline test suite powered by `pytest`. To run tests using the local SQLite in-memory configuration:

```bash
# Add backend to path and execute pytest
PYTHONPATH=backend ENVIRONMENT=test DATABASE_URL=sqlite:///:memory: .venv/bin/pytest
```

All 60+ unit and integration assertions will run, validating tool execution context, safety checkpoints, memory managers, and specialist agent nodes.

---

## 🛡️ License

This project is licensed under the MIT License - see the LICENSE file for details.
