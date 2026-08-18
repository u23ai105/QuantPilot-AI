# Component Architecture

## 1. UI Primitives (shadcn/ui based)
These are generic, stateless, accessible components wrapping Radix UI primitives.
- `Button`: Variations (default, outline, ghost, link). Sizes (sm, md, lg).
- `Input` / `Textarea`: Standard form fields with consistent border/focus logic.
- `Card`: A container with surface background and standard border.
- `Table`: A highly usable table component optimized for dense financial data.
- `Badge`: Status indicators (e.g., QUEUED, RUNNING).
- `Dialog` / `Sheet`: Used for modals and side-drawers (e.g., viewing a citation).

## 2. Layout Components
- `AppShell`: The root layout wrapping authenticated routes. Manages the grid for sidebar and main content.
- `SidebarNavigation`: The vertical navigation bar.
- `TopHeader`: The top bar with search and user profile.
- `PageContainer`: Standard wrapper for views, applying consistent padding and max-widths.

## 3. Feature Components

### Research / AI
- `ChatHistory`: Manages the scrollable list of messages.
- `MessageBubble`: Distinguishes between User and AI. Renders Markdown.
- `ToolActivityBanner`: An accordion or inline tag that expands to show what tools the AI used (e.g., `get_market_data`) and their status.
- `CitationTag`: A clickable inline `[Source: ...]` badge that triggers a document preview.
- `ChatInput`: A specialized textarea that handles `Enter` to submit, `Shift+Enter` for newline, and disables while streaming.

### Market
- `ChartContainer`: A wrapper around `TradingView Lightweight Charts`. Takes generic series data and handles resizing/theming.
- `IndicatorPanel`: A control interface to add SMA/EMA/RSI onto the chart.

### Backtests
- `BacktestMetricsGrid`: A layout displaying key stats (Sharpe, CAGR, etc.) in a grid of `MetricCard`s.
- `MetricCard`: A small card taking a label, value, and optionally a format type (currency, percentage) which colors it appropriately (green/red).

### Documents
- `DocumentUploadDropzone`: A drag-and-drop area for PDFs.
- `DocumentStatusIcon`: A visual indicator showing a spinner (processing), check (ready), or X (failed).

## 4. Hierarchy Principle
- **Dumb Components (UI/Primitives):** Receive data via props, emit events via callbacks. Zero API knowledge.
- **Smart Components (Feature/Pages):** Call API hooks (`useQuery`, `useMutation`), handle loading/error states, and pass data down to Dumb Components.
