import { fetchClient } from "./client";

// ─── Types ──────────────────────────────────────────────────────────────────

export interface StrategyResponse {
  id: number;
  user_id: string;
  name: string;
  rules_json: Record<string, unknown>;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface StrategyCreate {
  name: string;
  rules_json: Record<string, unknown>;
}

export interface BacktestCreate {
  strategy_id: number;
  symbol: string;
  start_date: string;
  end_date: string;
  initial_capital?: number;
  commission?: number;
  slippage?: number;
}

export interface BacktestResponse {
  id: number;
  strategy_id: number;
  ticker_id: number;
  start_date: string;
  end_date: string;
  initial_capital: number;
  commission: number;
  slippage: number;
  status: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface BacktestResultResponse {
  id: number;
  backtest_id: number;
  total_return: number;
  cagr: number;
  volatility: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  max_drawdown: number;
  win_rate: number | null;
  total_trades: number;
  equity_curve: Record<string, unknown>[];
  trades: Record<string, unknown>[];
  created_at: string;
}

export interface DocumentResponse {
  id: number;
  user_id: string;
  filename: string;
  file_size: number;
  page_count: number | null;
  status: string;
  error_message: string | null;
  uploaded_at: string;
  processed_at: string | null;
}

// ─── API ─────────────────────────────────────────────────────────────────────

export const strategiesApi = {
  list: () => fetchClient<StrategyResponse[]>("/strategies"),
  create: (data: StrategyCreate) =>
    fetchClient<StrategyResponse>("/strategies", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  get: (id: number) => fetchClient<StrategyResponse>(`/strategies/${id}`),
};

export const backtestsApi = {
  create: (data: BacktestCreate) =>
    fetchClient<BacktestResponse>("/backtests", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  get: (id: number) => fetchClient<BacktestResponse>(`/backtests/${id}`),
  getResults: (id: number) =>
    fetchClient<BacktestResultResponse>(`/backtests/${id}/results`),
};

export const documentsApi = {
  list: () => fetchClient<DocumentResponse[]>("/documents"),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    // fetchClient sets Content-Type: application/json by default, so bypass it for multipart
    const token = sessionStorage.getItem("access_token");
    return fetch(`${import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1"}/documents`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    }).then(r => r.json()) as Promise<DocumentResponse>;
  },
  delete: (id: number) =>
    fetchClient<void>(`/documents/${id}`, { method: "DELETE" }),
};

export interface TickerResponse {
  id: number;
  symbol: string;
  name: string;
}

export interface OHLCVResponse {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface IndicatorResponse {
  date: string;
  value: number | null;
}

export const marketApi = {
  getTickers: () => fetchClient<TickerResponse[]>("/market-data/tickers"),
  getTickerData: (symbol: string, start?: string, end?: string) => 
    fetchClient<OHLCVResponse[]>(`/market-data/${symbol}`, { 
      params: { ...(start && { start_date: start }), ...(end && { end_date: end }) } 
    }),
  getIndicators: (symbol: string, indicator: string, params: Record<string, string>) => 
    fetchClient<IndicatorResponse[]>(`/indicators/${symbol}`, { 
      params: { indicator, ...params } 
    }),
};

export interface ConversationResponse {
  id: string;
  title: string;
}

export interface MessageResponse {
  id: number;
  role: "user" | "assistant";
  content: string;
  citations_json: Record<string, unknown>[] | null;
  created_at: string;
}

export interface MessagesListResponse {
  conversation_id: string;
  messages: MessageResponse[];
}

export const conversationsApi = {
  create: (title: string) => fetchClient<ConversationResponse>("/conversations", {
    method: "POST",
    body: JSON.stringify({ title }),
  }),
  getMessages: (id: string) => fetchClient<MessagesListResponse>(`/conversations/${id}/messages`),
};
