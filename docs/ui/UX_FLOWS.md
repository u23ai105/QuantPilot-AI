# UX Flows

## 1. Authentication Flow
- **Unauthenticated User:** Accesses `/`. Redirected to `/login`.
- **Login:** User enters credentials. On success, JWT is stored, and user is redirected to `/` (Research Workspace).
- **Session Expiry:** During any API call, if a 401 is returned, the user is immediately routed to `/login` with an "expired session" toast message.

## 2. Research to Action Flow (The Core Journey)
1. User lands on `/` (Research Workspace). A default conversation is active.
2. User asks: *"How did AAPL perform vs MSFT?"*
3. The UI appends a "User" bubble.
4. An "AI" bubble appears with a pulsating cursor indicating streaming.
5. A subtle `[get_market_data]` tag appears in the AI bubble. It spins, then shows a checkmark.
6. The AI starts streaming text: *"Based on the data..."*
7. User decides they want a strategy. They click the `Strategies` navigation link.
8. They click "Create Strategy", paste a JSON payload, and save.
9. They navigate to `Backtests`, click "New Backtest", select the strategy and AAPL.
10. The backtest appears in the list as `QUEUED`, then `RUNNING`. The UI polls the backend status.
11. The list auto-polls until it reaches `COMPLETED` or `FAILED`, then stops polling. (Timers are strictly cleaned up on unmount or navigation).
12. User clicks the backtest to view the Equity Curve and Metrics (Sharpe, CAGR).
13. User returns to `/` (Research Workspace) and asks the AI to analyze the backtest ID.

## 3. RAG / Document Ingestion Flow
1. User goes to `/documents`.
2. Drops a 10-K PDF into the dropzone.
3. The file appears in the list with a `PROCESSING` status spinner.
4. Polling occurs every 3 seconds only while `PROCESSING`.
5. The status turns to `READY` (green badge) or `FAILED` (red badge), and polling stops.
6. User goes to `/` (Research) and asks a question about the 10-K.
7. AI responds with text and a citation: `[Source: 10-K.pdf, Page: 42]`.
8. User clicks the citation. A modal opens showing the chunk text or rendering the PDF specifically at page 42 (if PDF viewer implemented).

## 4. Market Research Flow
1. User navigates to `/market`.
2. The page loads with default AAPL data.
3. User types `MSFT` in the search box.
4. Chart rerenders with MSFT OHLCV data.
5. User clicks "Add Indicator", selects `RSI`.
6. A sub-chart panel appears below the main chart showing the RSI oscillator.
7. User selects "Add Indicator" -> `SMA`.
8. An overlay line appears on the main candlestick chart.

## 5. Error & Edge Case Flows
- **Invalid Strategy JSON:** User pastes malformed JSON into the Strategy creation form. The UI leverages the `422 Unprocessable Entity` response from the backend to show a red inline error under the editor.
- **Empty RAG Results:** AI tool `search_documents` returns no results. The AI streams: *"I could not find that information in the uploaded documents."* No fake citations are generated.
- **Rate Limit (429):** If the AI provider hits a rate limit, the API returns an error. The stream terminates with an error event. The UI displays: *"Error: AI Provider rate limit exceeded. Please try again in a few seconds."* within the chat bubble (styled as an error block, not a system toast).
