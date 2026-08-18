# Page Specifications

## 1. Application Shell (Persistent)
- **Sidebar:** Left-aligned. Contains logo ("QuantPilot"), primary navigation links (`/`, `/market`, `/strategies`, `/backtests`, `/documents`).
- **Top Bar:** Contains a global command menu trigger (Search / ⌘K) to quickly jump to tickers or strategies, user profile avatar, and connection status (e.g., "API: Connected").

## 2. Research Workspace (Primary AI Screen) `[/]`
**Purpose:** The central hub where the user interacts with the AI agent to answer quantitative questions, analyze data, and run workflows.
**Layout:** 
- A large, scrollable conversation history pane.
- A fixed bottom input area (textarea with dynamic height, "Send" button).
**Components:**
- **User Message Bubble:** Simple, right-aligned or distinctly styled.
- **Agent Message Bubble:** Left-aligned. Renders markdown.
- **Tool Activity Block:** A subtle inline component showing tools called during the agent's turn. E.g., `[⚙ get_market_data: AAPL]` fading to `[✓ get_market_data 120ms]`.
- **Citations:** Inline clickable references `[Source: benchmark_report.pdf, Page: 5]` implemented via `CitationTag`. Clicking opens a drawer/sheet showing the filename, page, chunk text, and metadata.

## 3. Market Page `[/market]`
**Purpose:** Professional view for raw market data and indicators.
**Layout:**
- **Header:** Ticker search/dropdown (fixed universe), Date range picker.
- **Main Area (Split):**
  - *Top/Left:* Large TradingView chart displaying OHLCV candlesticks and overlaid indicators (SMA, EMA, Bollinger Bands).
  - *Bottom/Right:* Indicator control panel and raw data table (Date, Open, High, Low, Close, Volume). Oscillators (RSI, MACD, ATR) render in a sub-chart panel.

## 4. Strategies Page `[/strategies]`
**Purpose:** View and manage declarative JSON strategies. No drag-and-drop visual builder.
**Layout:**
- **List View:** Table of strategies (Name, Version, Creator, Created At). Actions: Create, View.
- **Detail/Create View:** 
  - Strategy Name input.
  - JSON Editor for declarative rules.
  - Validation feedback (from backend `422`).
  - Save button.
  - "Run Backtest with Strategy" action.

## 5. Backtests Page `[/backtests]`
**Purpose:** Submit backtests and review historical performance.
**Layout:**
- **Top Action Bar:** Button to "New Backtest".
- **List View:** Table of backtest runs showing Status (QUEUED, RUNNING, COMPLETED, FAILED), Strategy, Ticker, Date Range.
- **Detail View (Completed):**
  - *Configuration:* Shows reproducibility metadata (strategy, strategy version, symbol, start date, end date, initial capital, commission, slippage).
  - *Metrics Bar:* Cards for Total Return, CAGR, Volatility, Sharpe, Sortino, Max Drawdown, Win Rate.
  - *Chart:* Equity curve (TradingView or simpler line chart).
- **Detail View (Running/Queued):** Shows configuration and a loading spinner/time elapsed. **Never** displays performance metrics.

## 6. Documents Page `[/documents]`
**Purpose:** Upload and manage financial PDFs for RAG.
**Layout:**
- **Header:** "Upload Document" drag-and-drop zone or button.
- **List View:** Table of documents (Filename, Upload Date, Status).
- **Statuses:** `PROCESSING` (with spinner), `READY` (green badge), `FAILED` (red badge).
- **Actions:** Delete document. Preview (if supported natively by browser).
