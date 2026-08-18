# API Integration Plan

## 1. Core Principles
- **No Duplication of Logic:** The frontend strictly relies on the backend for validation, calculation, and data integrity.
- **Typed Layer:** All API responses will have TypeScript interfaces exactly matching the FastAPI Pydantic schemas.
- **TanStack Query:** Used for fetching, caching, and invalidating server state.
- **Native Fetch:** The frontend will use the native `fetch` API exclusively. No Axios. A centralized typed client will handle headers, 401s, and JSON parsing.

## 2. API Endpoints Mapping

### Authentication
- `POST /api/v1/auth/register` -> `useRegisterMutation`
- `POST /api/v1/auth/login` -> `useLoginMutation` (Stores JWT securely)
- `GET /api/v1/auth/me` -> `useCurrentUserQuery`

### Market Data & Indicators
- `GET /api/v1/market-data/tickers` -> `useTickersQuery`
- `GET /api/v1/market-data/{symbol}` -> `useMarketDataQuery` (OHLCV chart data)
- `POST /api/v1/market-data/{symbol}/ingest` -> `useIngestMarketDataMutation`
- `GET /api/v1/indicators/{symbol}` -> `useIndicatorsQuery` (Fetches SMA, EMA, RSI, MACD, Bollinger, ATR)

### Strategies
- `POST /api/v1/strategies` -> `useCreateStrategyMutation`
- `GET /api/v1/strategies` -> `useStrategiesQuery`
- `GET /api/v1/strategies/{strategy_id}` -> `useStrategyQuery`

### Backtests
- `POST /api/v1/backtests` -> `useRunBacktestMutation`
- `GET /api/v1/backtests/{backtest_id}` -> `useBacktestQuery` (Polls status if `QUEUED` or `RUNNING`. Stops polling on `COMPLETED` or `FAILED`)
- `GET /api/v1/backtests/{backtest_id}/results` -> `useBacktestResultsQuery` (Only called when status is `COMPLETED`)

### Documents
- `POST /api/v1/documents` -> `useUploadDocumentMutation`
- `GET /api/v1/documents` -> `useDocumentsQuery` (Polls status if `PROCESSING`. Stops polling on `READY` or `FAILED`)
- `GET /api/v1/documents/{document_id}` -> `useDocumentQuery`
- `DELETE /api/v1/documents/{document_id}` -> `useDeleteDocumentMutation`

### Conversations & AI
- `POST /api/v1/conversations` -> `useCreateConversationMutation`
- `GET /api/v1/conversations/{conversation_id}/messages` -> `useMessagesQuery`
- `POST /api/v1/conversations/{conversation_id}/messages` -> Native `fetch` with ReadableStream or `@microsoft/fetch-event-source` to handle SSE.

## 3. Streaming (SSE) Integration Contract
The backend exposes a streaming endpoint that yields exactly these chunks:
```json
event: tool_start
data: {"tool": "get_market_data", "args": {"symbol": "AAPL"}}

event: tool_end
data: {"tool": "get_market_data", "result_summary": "Retrieved 252 items"}

event: token
data: {"content": "The RSI is 42."}

event: done
data: {"message_id": null}

event: error
data: {"message": "An error occurred processing your request."}
```
**Frontend Handling:**
A custom hook `useAIStream(conversationId)` will be implemented to parse these exact events and update a local React state for the active message, preventing full re-renders on every token.

## 4. Authentication Token Lifecycle
To preserve the backend's JWT bearer-token contract without compromising security via `localStorage`:
- The access token will be stored in memory within a centralized auth module.
- For persistence across tabs/refreshes, `sessionStorage` will be used as a tradeoff (more secure against XSS than `localStorage` since it's tab-isolated, but still requires careful XSS prevention in React).
- All API calls will automatically attach the `Authorization: Bearer <token>` header.
- A 401 response will clear the token and redirect to `/login`.
