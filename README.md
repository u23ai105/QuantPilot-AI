<div align="center">
  <h1>🚀 QuantPilot AI</h1>
  <p><strong>Agentic Financial Research Assistant</strong></p>
  
  [![Status: Phase 2 (Market Data & Indicators)](https://img.shields.io/badge/Status-Phase%202-blue.svg)](#)
  [![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
  [![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
</div>

<br />

## 📖 Overview

**QuantPilot AI** is an agentic financial research assistant built around deterministic financial tools, LangGraph, RAG over financial PDFs, async backtesting, and measurable AI evaluation. 

*Note: This project has completed Phase 2 (Market Data & Indicators), providing a robust SDE foundation, asynchronous yfinance integrations, and deterministic financial calculations.*

---

## ✨ Core Features (Planned)

### 🧠 AI Financial Research Assistant
*   **LangGraph Agent:** Tool-calling graph to execute financial queries deterministically.
*   **RAG Pipeline:** Chat directly with SEC filings using pgvector and gemini-embedding-2.
*   **Evaluation Harness:** Measurable RAG quality (retrieval and citation accuracy).

### 📈 Quantitative Backtesting
*   **Declarative Strategies:** JSON-based strategies executed asynchronously via Celery.
*   **Deterministic Tools:** SMA, EMA, RSI, MACD, Bollinger Bands, ATR.
*   **Performance Metrics:** Sharpe, Sortino, Max Drawdown, CAGR, Volatility, Win Rate.

### ⚙️ Infrastructure Foundation
*   **FastAPI & PostgreSQL:** Clean modular monolith architecture.
*   **Authentication:** Secure registration, password hashing (bcrypt), and JWT-based auth.
*   **Celery & Redis:** Asynchronous background tasks for backtesting and document embeddings.
*   **Alembic & Pytest:** Robust database migrations and testing foundation.

---

## 🛠️ Technology Stack

| Component | Technologies Used |
| :--- | :--- |
| **Backend API** | FastAPI, Python 3.11, SQLAlchemy Async, Pydantic |
| **Data** | PostgreSQL, pgvector, Alembic |
| **Background Tasks** | Celery, Redis |
| **AI / Machine Learning** | LangGraph, Gemini 3.6 Flash, gemini-embedding-2 |
| **Quantitative** | backtesting.py, yfinance |
| **DevOps & Infra** | Docker Compose, GitHub Actions, structlog, Ruff, Pytest |

---

## 💻 Local Development Setup

### Prerequisites
- Python 3.11+
- Docker & Docker Compose

### 1. Environment Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/quantpilot-ai.git
cd quantpilot-ai

# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Setup environment variables
cp .env.example .env
```

### 2. Running the Infrastructure

Use Docker Compose to start the API, Celery worker, PostgreSQL, and Redis:

```bash
docker compose up --build -d
```

### 3. Database Migrations

```bash
alembic upgrade head
```

### 4. Seed Market Data (Phase 2)

```bash
python -m scripts.ingest_market_data
```

### 5. Verification

```bash
# Check API health
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

### 5. Testing & Linting

```bash
ruff check .
ruff format --check .
pytest
```

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.
