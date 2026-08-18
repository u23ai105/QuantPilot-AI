# QuantPilot AI — Low-Level Design (LLD)

## 1. Package Structure

```text
app/
├── main.py                      # FastAPI application entry point
├── config.py                    # Pydantic BaseSettings configuration
│
├── api/                         # HTTP layer — routes + request/response schemas
│   ├── __init__.py
│   ├── deps.py                  # FastAPI dependencies (get_db, get_current_user)
│   ├── middleware.py            # Request ID, error handling middleware
│   ├── v1/
│   │   ├── __init__.py
│   │   ├── router.py            # Aggregates all v1 routers
│   │   ├── auth.py              # /auth routes
│   │   ├── market_data.py       # /market-data routes
│   │   ├── indicators.py        # /indicators routes
│   │   ├── strategies.py        # /strategies routes
│   │   ├── backtests.py         # /backtests routes
│   │   ├── documents.py         # /documents routes
│   │   ├── conversations.py     # /conversations routes
│   │   └── evaluation.py        # /evaluation routes
│   └── health.py                # /health, /health/ready
│
├── schemas/                     # Pydantic schemas (request/response models)
│   ├── __init__.py
│   ├── auth.py                  # RegisterRequest, LoginRequest, TokenResponse
│   ├── market_data.py           # OHLCVResponse, OHLCVBar
│   ├── indicators.py            # IndicatorRequest, IndicatorResponse
│   ├── strategies.py            # StrategyCreate, StrategyResponse
│   ├── backtests.py             # BacktestCreate, BacktestResponse, BacktestResultResponse
│   ├── documents.py             # DocumentResponse
│   ├── conversations.py         # ConversationCreate, MessageCreate, MessageResponse
│   ├── evaluation.py            # EvalRunResponse, EvalReportResponse
│   └── common.py                # ErrorResponse, PaginatedResponse
│
├── services/                    # Application service layer
│   ├── __init__.py
│   ├── auth_service.py
│   ├── market_data_service.py
│   ├── indicator_service.py
│   ├── strategy_service.py
│   ├── backtest_service.py
│   ├── document_service.py
│   ├── retrieval_service.py
│   ├── conversation_service.py
│   ├── agent_service.py
│   └── evaluation_service.py
│
├── domain/                      # Domain logic — pure computation, no I/O
│   ├── __init__.py
│   ├── indicators/
│   │   ├── __init__.py
│   │   ├── sma.py
│   │   ├── ema.py
│   │   ├── rsi.py
│   │   ├── macd.py
│   │   ├── bollinger.py
│   │   └── atr.py
│   ├── metrics.py               # MetricsCalculator
│   ├── strategy_validator.py    # JSON schema validation
│   ├── strategy_interpreter.py  # JSON → backtesting.py Strategy
│   ├── text_chunker.py          # Page text → chunks
│   └── exceptions.py            # Domain exceptions
│
├── models/                      # SQLAlchemy ORM models
│   ├── __init__.py
│   ├── user.py
│   ├── ticker.py
│   ├── ohlcv.py
│   ├── strategy.py
│   ├── backtest.py
│   ├── document.py
│   ├── conversation.py
│   └── evaluation.py
│
├── repositories/                # Database access layer
│   ├── __init__.py
│   ├── base.py                  # Base repository with common CRUD
│   ├── user_repository.py
│   ├── market_data_repository.py
│   ├── strategy_repository.py
│   ├── backtest_repository.py
│   ├── document_repository.py
│   ├── conversation_repository.py
│   └── evaluation_repository.py
│
├── infrastructure/              # External system adapters
│   ├── __init__.py
│   ├── database.py              # AsyncSession factory, engine
│   ├── redis.py                 # Redis connection
│   ├── yfinance_adapter.py      # Market data provider
│   ├── gemini_llm_adapter.py    # LLM provider
│   ├── gemini_embedding_adapter.py  # Embedding provider
│   └── pdf_extractor.py         # PyMuPDF wrapper
│
├── ai/                          # AI agent layer
│   ├── __init__.py
│   ├── graph.py                 # LangGraph StateGraph definition
│   ├── state.py                 # AgentState TypedDict
│   ├── nodes.py                 # agent_node, tool_node
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── market_data_tool.py
│   │   ├── indicators_tool.py
│   │   ├── backtest_tool.py
│   │   ├── metrics_tool.py
│   │   └── documents_tool.py
│   └── prompts.py               # System prompt
│
├── workers/                     # Celery tasks
│   ├── __init__.py
│   ├── celery_app.py            # Celery application factory
│   ├── backtest_task.py         # run_backtest task
│   └── embedding_task.py        # embed_document task
│
└── scripts/                     # One-off scripts
    ├── seed_tickers.py          # Seed fixed ticker universe
    └── seed_eval_questions.py   # Seed evaluation Q/A set
```

### Directory Responsibilities

| Directory | Responsibility | Depends On |
|---|---|---|
| `api/` | HTTP handlers, routing, request parsing, response formatting | `schemas/`, `services/` |
| `schemas/` | Pydantic request/response models, validation | Nothing |
| `services/` | Application workflows, business orchestration | `domain/`, `repositories/`, `infrastructure/` |
| `domain/` | Pure business logic, calculations, validation | Nothing (no I/O) |
| `models/` | SQLAlchemy ORM model definitions | SQLAlchemy |
| `repositories/` | Database queries, persistence | `models/`, `infrastructure/database` |
| `infrastructure/` | External system connections and adapters | External SDKs |
| `ai/` | LangGraph agent graph, tool definitions | `services/` |
| `workers/` | Celery task definitions | `services/`, `domain/`, `infrastructure/` |

### Dependency Flow

```text
api/  →  services/  →  domain/       (pure logic)
                    →  repositories/  (persistence)
                    →  infrastructure/ (external systems)
ai/   →  services/                    (tools delegate to services)
workers/ → services/ → domain/        (tasks delegate to services)
```

**Critical rule**: `domain/` has **zero** imports from `api/`, `models/`, `repositories/`, `infrastructure/`, `ai/`, or `workers/`.

---

## 2. Class/Interface Definitions

### 2.1 AuthService

```python
class AuthService:
    """User registration, login, and token management."""

    def __init__(self, user_repository: UserRepository):
        self.user_repo = user_repository

    async def register(self, email: str, password: str) -> User:
        """
        1. Check email uniqueness
        2. Hash password
        3. Create user record
        Returns: User
        Raises: ConflictError if email exists
        """

    async def login(self, email: str, password: str) -> str:
        """
        1. Find user by email
        2. Verify password
        3. Generate JWT
        Returns: JWT access token string
        Raises: AuthenticationError if invalid
        """
```

### 2.2 MarketDataService

```python
class MarketDataService:
    """OHLCV data ingestion and retrieval."""

    def __init__(
        self,
        market_data_repo: MarketDataRepository,
        yfinance_adapter: YFinanceAdapter,
    ):
        self.repo = market_data_repo
        self.provider = yfinance_adapter

    async def get_ohlcv(self, symbol: str, start: date, end: date) -> list[OHLCVBar]:
        """
        1. Validate symbol is in universe
        2. Query PostgreSQL for cached data
        3. If data missing, fetch from yfinance and store
        4. Return OHLCV bars
        Raises: ValidationError, DataProviderError
        """

    async def ingest_ticker(self, symbol: str, start: date, end: date) -> int:
        """
        Fetch from yfinance and upsert into PostgreSQL.
        Returns: number of rows upserted
        """
```

### 2.3 IndicatorService

```python
class IndicatorService:
    """Dispatches indicator calculations to domain calculators."""

    def __init__(self, market_data_service: MarketDataService):
        self.market_data = market_data_service

    async def calculate(self, symbol: str, indicator: str, params: dict) -> IndicatorResult:
        """
        1. Fetch OHLCV data for symbol (full available range or recent)
        2. Dispatch to appropriate calculator (SMA, EMA, RSI, etc.)
        3. Return calculated values with dates
        Raises: ValidationError (invalid indicator/params/insufficient data)
        """
```

### 2.4 StrategyService

```python
class StrategyService:
    """Strategy CRUD and validation."""

    def __init__(
        self,
        strategy_repo: StrategyRepository,
        strategy_validator: StrategyValidator,
    ):
        self.repo = strategy_repo
        self.validator = strategy_validator

    async def create(self, user_id: UUID, name: str, rules_json: dict) -> Strategy:
        """
        1. Validate rules_json against schema
        2. Create strategy record
        Raises: ValidationError
        """

    async def get(self, strategy_id: int, user_id: UUID) -> Strategy:
        """
        Raises: NotFoundError, AuthorizationError
        """

    async def list_for_user(self, user_id: UUID) -> list[Strategy]:
        """Return all strategies owned by user."""
```

### 2.5 BacktestService

```python
class BacktestService:
    """Backtest submission, status, and results."""

    def __init__(
        self,
        backtest_repo: BacktestRepository,
        strategy_repo: StrategyRepository,
        market_data_repo: MarketDataRepository,
        celery_app: Celery,
    ): ...

    async def submit(
        self,
        user_id: UUID,
        strategy_id: int,
        symbol: str,
        start_date: date,
        end_date: date,
        initial_capital: float = 10000.0,
        commission: float = 0.001,
    ) -> Backtest:
        """
        1. Verify strategy exists + user owns it
        2. Verify ticker exists
        3. Create backtest record (QUEUED)
        4. Dispatch Celery task
        Returns: Backtest with status=QUEUED
        Raises: NotFoundError, AuthorizationError, ValidationError
        """

    async def get_status(self, backtest_id: int, user_id: UUID) -> Backtest:
        """Raises: NotFoundError, AuthorizationError"""

    async def get_results(self, backtest_id: int, user_id: UUID) -> BacktestResult:
        """Raises: NotFoundError, AuthorizationError"""
```

### 2.6 DocumentService

```python
class DocumentService:
    """Document upload and ingestion pipeline."""

    def __init__(
        self,
        document_repo: DocumentRepository,
        pdf_extractor: PDFExtractor,
        text_chunker: TextChunker,
        embedding_adapter: EmbeddingProvider,
    ): ...

    async def ingest(self, user_id: UUID, file: UploadFile) -> Document:
        """
        1. Validate file (type, size)
        2. Save to disk with safe name
        3. Create document record (PROCESSING)
        4. Dispatch Celery task (embed_document)
        5. Return Document (PROCESSING)
        Raises: ValidationError, DocumentProcessingError
        """

    async def list_for_user(self, user_id: UUID) -> list[Document]:
        """Return user's documents."""
```

### 2.7 RetrievalService

```python
class RetrievalService:
    """Semantic search over document chunks."""

    def __init__(
        self,
        document_repo: DocumentRepository,
        embedding_adapter: EmbeddingProvider,
    ): ...

    async def search(self, query: str, document_id: int | None = None, top_k: int = 5) -> list[ChunkWithCitation]:
        """
        1. Embed query (RETRIEVAL_QUERY)
        2. Cosine similarity search in pgvector
        3. Return top-K chunks with (document_id, page_number, text, score)
        Raises: RetrievalError
        """
```

### 2.8 ConversationService

```python
class ConversationService:
    """Conversation and message management."""

    def __init__(self, conversation_repo: ConversationRepository):
        self.repo = conversation_repo

    async def create(self, user_id: UUID) -> Conversation:
        """Create a new conversation."""

    async def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        tool_calls_json: dict | None = None,
        citations_json: list | None = None,
    ) -> Message:
        """Append a message to a conversation."""

    async def get_history(self, conversation_id: UUID, user_id: UUID) -> list[Message]:
        """
        Raises: NotFoundError, AuthorizationError
        """
```

### 2.9 AgentService

```python
class AgentService:
    """Entry point for AI agent interactions."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        market_data_service: MarketDataService,
        indicator_service: IndicatorService,
        backtest_service: BacktestService,
        retrieval_service: RetrievalService,
        conversation_service: ConversationService,
    ): ...

    async def handle_message(self, conversation_id: UUID, user_id: UUID, content: str) -> AsyncIterator[StreamEvent]:
        """
        1. Persist user message
        2. Load conversation history
        3. Invoke LangGraph with streaming
        4. Yield events (tool_start, tool_end, token, done)
        5. Persist assistant response
        """
```

### 2.10 EvaluationService

```python
class EvaluationService:
    """RAG evaluation harness."""

    def __init__(
        self,
        eval_repo: EvaluationRepository,
        retrieval_service: RetrievalService,
        agent_service: AgentService,
    ): ...

    async def run_evaluation(self) -> list[EvalRun]:
        """
        For each eval_question:
        1. Run search_documents with question
        2. Check if expected page is in top-K (retrieval_hit_at_k)
        3. Run agent with question
        4. Check if response cites expected page (citation_correct)
        5. Score answer quality (heuristic)
        6. Persist eval_run
        Returns: list of EvalRun results
        """

    async def get_report(self) -> EvalReport:
        """Aggregate metrics from latest eval runs."""
```

---

## 3. Adapter Interfaces

### 3.1 YFinanceAdapter

```python
class YFinanceAdapter:
    """Wraps yfinance library. Normalizes output."""

    def fetch(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """
        Returns: DataFrame with columns [date, open, high, low, close, volume]
        Raises: DataProviderError on network/API failure
        Handles: NaN removal, date normalization, column standardization
        """
```

### 3.2 LLMProvider (Protocol)

```python
class LLMProvider(Protocol):
    def bind_tools(self, tools: list[BaseTool]) -> ChatModel: ...
```

### 3.3 EmbeddingProvider (Protocol)

```python
class EmbeddingProvider(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...
```

---

## 4. Error Hierarchy

```python
# app/domain/exceptions.py


class QuantPilotError(Exception):
    """Base exception for all QuantPilot errors."""

    pass


class ValidationError(QuantPilotError):
    """Invalid input or business rule violation."""

    pass


class AuthenticationError(QuantPilotError):
    """Invalid credentials or token."""

    pass


class AuthorizationError(QuantPilotError):
    """User not authorized for this resource."""

    pass


class NotFoundError(QuantPilotError):
    """Resource not found."""

    pass


class ConflictError(QuantPilotError):
    """Duplicate resource (e.g., email already exists)."""

    pass


class DataProviderError(QuantPilotError):
    """External data source failure (yfinance)."""

    pass


class BacktestError(QuantPilotError):
    """Backtest execution failure."""

    pass


class AIToolError(QuantPilotError):
    """LLM or AI tool failure."""

    pass


class DocumentProcessingError(QuantPilotError):
    """PDF extraction or embedding failure."""

    pass


class RetrievalError(QuantPilotError):
    """Vector search failure."""

    pass
```

### Exception-to-HTTP Mapping (in middleware)

```python
EXCEPTION_STATUS_MAP = {
    ValidationError: 400,
    AuthenticationError: 401,
    AuthorizationError: 403,
    NotFoundError: 404,
    ConflictError: 409,
    DataProviderError: 502,
    BacktestError: 500,
    AIToolError: 502,
    DocumentProcessingError: 500,
    RetrievalError: 500,
}
```

---

## 5. Indicator Engine Design

Each indicator follows a consistent interface:

```python
class BaseIndicator(Protocol):
    @staticmethod
    def calculate(data: pd.DataFrame, **params) -> pd.Series | pd.DataFrame:
        """
        Args:
            data: OHLCV DataFrame with columns [open, high, low, close, volume]
            **params: Indicator-specific parameters
        Returns:
            Series (single-value indicators) or DataFrame (multi-value like MACD)
        """
        ...
```

### SMA

**Convention:** Simple rolling mean on close prices. `min_periods = period` (pandas default).

```python
class SMACalculator:
    @staticmethod
    def calculate(data: pd.DataFrame, period: int = 20) -> pd.Series:
        return data["close"].rolling(window=period, min_periods=period).mean()
```

### EMA

**Convention:** Exponential weighted mean using `span=period, adjust=False`. This matches Wilder's convention used by most charting platforms.

```python
class EMACalculator:
    @staticmethod
    def calculate(data: pd.DataFrame, period: int = 20) -> pd.Series:
        return data["close"].ewm(span=period, adjust=False).mean()
```

### RSI

**Convention:** Wilder's smoothed RSI. Uses EWM with `com=(period-1)` for smoothing (equivalent to Wilder's smoothing factor `1/period`).

```python
class RSICalculator:
    @staticmethod
    def calculate(data: pd.DataFrame, period: int = 14) -> pd.Series:
        delta = data["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.ewm(com=period - 1, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
```

### MACD

**Convention:** Fast EMA(12), Slow EMA(26), Signal EMA(9). All EMA use `adjust=False`.

Returns DataFrame with columns: `macd`, `signal`, `histogram`.

```python
class MACDCalculator:
    @staticmethod
    def calculate(data: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        ema_fast = data["close"].ewm(span=fast, adjust=False).mean()
        ema_slow = data["close"].ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return pd.DataFrame({"macd": macd_line, "signal": signal_line, "histogram": histogram})
```

### Bollinger Bands

**Convention:** Middle band = SMA(period). Standard deviation uses `ddof=1` (pandas default for `.std()`). Upper = middle + std_dev × σ. Lower = middle − std_dev × σ.

```python
class BollingerCalculator:
    @staticmethod
    def calculate(data: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
        sma = data["close"].rolling(window=period).mean()
        std = data["close"].rolling(window=period).std(ddof=1)
        return pd.DataFrame(
            {
                "middle": sma,
                "upper": sma + (std * std_dev),
                "lower": sma - (std * std_dev),
            }
        )
```

### ATR

**Convention:** True Range smoothed with Wilder's method (EWM with `com=period-1, adjust=False`).

```python
class ATRCalculator:
    @staticmethod
    def calculate(data: pd.DataFrame, period: int = 14) -> pd.Series:
        high_low = data["high"] - data["low"]
        high_close = (data["high"] - data["close"].shift()).abs()
        low_close = (data["low"] - data["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.ewm(com=period - 1, min_periods=period, adjust=False).mean()
```

---

## 5.1 Indicator Warm-Up / Lookback Policy

Indicators require historical data before the requested start date to produce valid values. The `IndicatorService` must internally extend the data query range backward by the indicator's lookback period.

**Lookback periods:**

| Indicator | Lookback (trading days) |
|---|---|
| SMA(n) | n |
| EMA(n) | 2 × n (for EWM convergence) |
| RSI(n) | 2 × n |
| MACD(f, s, sig) | 2 × (slow + signal) |
| Bollinger(n) | n |
| ATR(n) | 2 × n |

**Warm-up flow:**

```text
User requests indicator for [start, end]
    ↓
IndicatorService computes lookback_date = start − lookback_days
    ↓
Fetch OHLCV from [lookback_date, end]
    ↓
Calculate indicator on full range
    ↓
Trim result to [start, end]
    ↓
Return trimmed result
```

**Rules:**
- Warm-up rows must NEVER appear in API responses.
- If insufficient historical data exists for the warm-up period, return a `ValidationError` with a clear message.
- The lookback policy is deterministic and documented here.

---

## 5.2 yfinance Event-Loop Safety

`yfinance` is a synchronous blocking library. It must NEVER be called directly on the FastAPI async event loop.

**Required approach:**

```python
import asyncio


class YFinanceAdapter:
    def _fetch_sync(self, symbol, start, end) -> pd.DataFrame:
        """Synchronous yfinance call."""
        ...

    async def fetch(self, symbol, start, end) -> pd.DataFrame:
        """Run blocking yfinance in a thread executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_sync, symbol, start, end)
```

This delegates the blocking network call to the default thread-pool executor, keeping the event loop responsive. No Celery required for Phase 2 ingestion.

---

## 5.3 Ingestion Validation Flow

Data validation must occur BEFORE persistence.

```text
yfinance response (raw DataFrame)
    ↓
Normalize columns to [date, open, high, low, close, volume]
    ↓
Drop rows with NaN in any OHLCV column
    ↓
Validate: high >= low for every row
    ↓
Validate: volume >= 0 for every row
    ↓
Cast types: date=Date, OHLC=Decimal, volume=int
    ↓
Upsert to PostgreSQL (ON CONFLICT DO UPDATE)
```

Invalid rows are dropped, never fabricated. If the entire response is invalid or empty, raise `DataProviderError`.

---

## 6. Frontend Design Specification (Not Implemented)

### Screen 1: AI Research

```text
┌─────────────────────────────────────────────┐
│  QuantPilot AI                    [User ▾]  │
├─────────────────────────────────────────────┤
│                                              │
│  ┌─ Conversation ──────────────────────────┐ │
│  │ User: What's AAPL's RSI?                │ │
│  │                                          │ │
│  │ 🔧 Calling: calculate_indicators(AAPL)  │ │
│  │                                          │ │
│  │ Assistant: Based on the calculation,     │ │
│  │ AAPL's current RSI(14) is 62.3, which   │ │
│  │ indicates neutral momentum...            │ │
│  │                                          │ │
│  │ 📄 Citation: Apple 10-K, Page 47        │ │
│  └──────────────────────────────────────────┘ │
│                                              │
│  ┌─ Input ─────────────────────────────────┐ │
│  │ Ask a question...                [Send] │ │
│  └──────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### Screen 2: Backtesting

```text
┌─────────────────────────────────────────────┐
│  Strategy: SMA Crossover (10/30)            │
├──────────────────┬──────────────────────────┤
│  Symbol: AAPL    │  Status: ✅ COMPLETED    │
│  Start: 2023-01  │  Total Return: 15.2%     │
│  End: 2024-01    │  Sharpe: 1.34            │
│  Capital: $10K   │  Max Drawdown: -8.7%     │
│                  │  Win Rate: 58%           │
├──────────────────┴──────────────────────────┤
│         [Equity Curve Chart]                 │
│  $12,500 ─────────────────╱─               │
│  $10,000 ───────╱──╱─────╱──               │
│   $9,000 ──────────────────────              │
└─────────────────────────────────────────────┘
```

### Screen 3: Documents

```text
┌─────────────────────────────────────────────┐
│  Documents                    [Upload PDF]   │
├─────────────────────────────────────────────┤
│  📄 Apple_10K_2023.pdf    147 pages  ✅     │
│  📄 Microsoft_10K_2023.pdf  152 pages  ✅    │
│  📄 Google_10K_2023.pdf    Processing...    │
└─────────────────────────────────────────────┘
```

### Design Principles

- Professional, analytical, information-dense
- Restrained — no excessive gradients or animation
- Appropriate for financial research software
- Not a fintech consumer product
