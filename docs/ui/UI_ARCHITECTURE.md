# UI Architecture

## 1. Overview
The QuantPilot frontend is a modern quantitative research workstation. It is built as a Single Page Application (SPA) utilizing a feature-first architecture, allowing modular development and strict logical boundaries matching the backend domain.

## 2. Technology Stack
- **Framework:** React 18+ (Vite)
- **Language:** TypeScript
- **Styling:** Tailwind CSS + custom CSS variables for design tokens
- **Component Library:** shadcn/ui (radix-ui primitives + tailwind)
- **State Management (Server):** TanStack Query (React Query)
- **State Management (Local):** React Context & Hooks (zustand only if strictly needed for complex shared UI state)
- **Routing:** React Router v6
- **Charting:** TradingView Lightweight Charts
- **Data Fetching:** Native `fetch` API wrapped in a typed API client (No Axios).
- **Streaming:** Server-Sent Events (SSE) via `fetch`/readable-stream or `@microsoft/fetch-event-source` for authenticated POST.

## 3. Frontend Project Structure
```text
frontend/
  ├── public/
  ├── src/
  │   ├── app/                # Global app setup, providers, main router
  │   ├── components/         # Shared, generic UI components (API-agnostic)
  │   │   ├── ui/             # shadcn primitives (Button, Input, Card)
  │   │   ├── layout/         # AppShell, Navigation, Header
  │   │   ├── charts/         # TradingView wrapper components
  │   │   └── data-display/   # Generic tables, metric cards
  │   ├── features/           # Feature-bound domains (Smart components owning queries/mutations)
  │   │   ├── auth/           # Login, JWT management, Guard routes
  │   │   ├── research/       # AI Workspace, Chat, Tool activity
  │   │   ├── market/         # Symbol selection, OHLCV charts
  │   │   ├── strategies/     # Strategy list, builder JSON viewer
  │   │   ├── backtests/      # Backtest runner, equity curves, metrics
  │   │   └── documents/      # Uploads, processing status, RAG sources
  │   ├── lib/                # Cross-feature utilities
  │   │   ├── api/            # Centralized API client (fetch), error normalization
  │   │   ├── streaming/      # SSE stream parser hooks
  │   │   └── utils.ts        # Tailwind cn(), formatting helpers
  │   └── types/              # Global TS interfaces, API DTOs
  ├── index.html
  ├── package.json
  ├── tsconfig.json
  ├── tailwind.config.js
  └── vite.config.ts
```

## 4. Application Shell
The main application shell consists of a persistent navigation layout that avoids wasting vertical space. 
- **Sidebar (Compact/Collapsible):** Contains primary navigation links (Research, Market, Strategies, Backtests, Documents).
- **Top Header (Minimal):** Contains Global Search (⌘K), User Profile, and current connection/status indicators.
- **Main Content Area:** The dynamic work area occupying maximum screen real estate.

## 5. Security & Authorization
- **Token Storage:** JWT tokens are strictly managed in memory and `sessionStorage` for persistence. No `localStorage`.
- **Interceptors:** A centralized API client automatically attaches the `Authorization: Bearer <token>` header and handles 401/403 responses by triggering a logout flow.
- **Guard Routes:** Protected routes ensure unauthenticated users are redirected to `/login`.

## 6. Performance Plan
- **Route-Level Code Splitting:** React `lazy` and `Suspense` will be used for major routes (e.g., `/backtests`, `/research`) to keep the initial bundle small.
- **Memoization:** Heavy chart components and data tables will be wrapped in `React.memo` to prevent unnecessary re-renders when parent states (like SSE streaming logs) update frequently.
- **Efficient Streaming:** AI responses are streamed directly into local component state to decouple them from global React context, ensuring 60fps responsiveness.
- **Stale-While-Revalidate:** TanStack Query handles caching, preventing redundant fetches for static entities like strategies and past backtest metrics.

## 7. Responsive Strategy
- **Desktop First:** As a quantitative workstation, complex data tables and charts target 1080p+ displays.
- **Graceful Degradation:** On tablets and smaller screens, the sidebar collapses into a hamburger menu. Charts become vertically scrollable or swap to simplified list views. Data tables implement horizontal scrolling.
- **Not Mobile Optimized (Intentionally):** We will not sacrifice desktop density. While usable, mobile browsers will see horizontal scrolling on heavy data views rather than fundamentally altering the layout.

## 8. Accessibility Plan
- **Semantic HTML:** Correct use of `<nav>`, `<main>`, `<article>`, `<aside>`.
- **Focus Management:** Visible focus rings on all interactive elements. Modal dialogs and the command menu will trap focus.
- **Aria Labels:** Screen-reader accessible labels for icon-only buttons (e.g., "Run Backtest", "Close Document").
- **Contrast:** Ensure all text, especially subdued metadata, meets WCAG AA contrast standards against the background.

## 9. Visual Quality Verification Strategy
Before finalizing a feature:
1. **Consistency Check:** Verify fonts, colors, and radii strictly pull from Tailwind config (no arbitrary `text-[#123456]` values).
2. **Alignment:** Ensure grid layouts align with the 4px/8px standard spacing system.
3. **Empty/Loading/Error:** Force the component into `isLoading`, `isError`, and `isEmpty` states via React DevTools to confirm they look intentionally designed.
4. **Data Density:** Verify that large numbers (e.g., billions) fit in metric cards without text wrapping or layout shifting.
