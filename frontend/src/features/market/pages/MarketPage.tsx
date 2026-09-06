import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageContainer } from "@/components/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { marketApi } from "@/lib/api/resources";
import { Search, TrendingUp, TrendingDown, AlertCircle, Loader2 } from "lucide-react";

/** `GET /market-data/{symbol}` requires an explicit window. Five years back covers whatever has been
 *  ingested; the table still shows only the latest 10 bars. */
function defaultWindow() {
  const end = new Date();
  const start = new Date(end);
  start.setFullYear(start.getFullYear() - 5);
  return { start: start.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10) };
}

/**
 * Trading days of warm-up the indicator endpoint demands *strictly before* its `start` date.
 *
 * `IndicatorService._get_lookback_days` needs `period` rows for SMA and `2 * period` for RSI, and
 * rejects the request outright when they are missing. So the indicator window cannot simply reuse
 * the OHLCV window — asking from the earliest stored bar leaves zero rows ahead of it and 400s.
 */
const INDICATOR_WARMUP_BARS = 40;

export function MarketPage() {
  const [search, setSearch] = useState("AAPL");
  const [activeSymbol, setActiveSymbol] = useState("AAPL");
  // Memoised so the dates stay stable across renders — a fresh `end` every render would change the
  // query key each time and refetch forever.
  const { start, end } = useMemo(defaultWindow, []);

  const { isLoading: tickersLoading } = useQuery({
    queryKey: ["tickers"],
    queryFn: () => marketApi.getTickers(),
  });

  const { data: marketData, isLoading: ohlcvLoading, error: ohlcvError } = useQuery({
    queryKey: ["ohlcv", activeSymbol, start, end],
    queryFn: () => marketApi.getTickerData(activeSymbol, start, end),
    enabled: !!activeSymbol,
    retry: false,
  });

  // The response envelope wraps the series in `bars`, so unwrap before indexing.
  const bars = marketData?.bars ?? [];

  // Indicators start far enough into the stored history to satisfy the backend's warm-up check.
  const hasWarmup = bars.length > INDICATOR_WARMUP_BARS;
  const indicatorStart = hasWarmup ? bars[INDICATOR_WARMUP_BARS].date : undefined;
  const indicatorEnd = bars.length > 0 ? bars[bars.length - 1].date : undefined;

  const { data: sma, error: smaError } = useQuery({
    queryKey: ["indicator", activeSymbol, "sma", indicatorStart, indicatorEnd],
    queryFn: () => marketApi.getIndicators(activeSymbol, "sma", indicatorStart!, indicatorEnd!, { period: "20" }),
    enabled: hasWarmup,
    retry: false,
  });

  const { data: rsi, error: rsiError } = useQuery({
    queryKey: ["indicator", activeSymbol, "rsi", indicatorStart, indicatorEnd],
    queryFn: () => marketApi.getIndicators(activeSymbol, "rsi", indicatorStart!, indicatorEnd!, { period: "14" }),
    enabled: hasWarmup,
    retry: false,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (search.trim()) setActiveSymbol(search.trim().toUpperCase());
  };

  const latestOhlcv = bars.length > 0 ? bars[bars.length - 1] : null;
  const prevOhlcv = bars.length > 1 ? bars[bars.length - 2] : null;
  const isUp = latestOhlcv && prevOhlcv ? latestOhlcv.close >= prevOhlcv.close : true;

  const smaPoints = sma?.points ?? [];
  const rsiPoints = rsi?.points ?? [];
  const latestSma = smaPoints.length > 0 ? smaPoints[smaPoints.length - 1].value : null;
  const latestRsi = rsiPoints.length > 0 ? rsiPoints[rsiPoints.length - 1].value : null;
  // A pending indicator query only spins while it can actually run: with too little history the
  // backend would reject it, so show a dash instead of a spinner that never resolves.
  const smaPending = hasWarmup && sma === undefined && !smaError;
  const rsiPending = hasWarmup && rsi === undefined && !rsiError;

  return (
    <PageContainer title="Market Data" description="Explore OHLCV data and technical indicators.">
      <div className="flex gap-4 mb-6">
        <form onSubmit={handleSearch} className="relative w-72 flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search ticker (e.g. MSFT)..."
              className="pl-9 bg-background/50"
            />
          </div>
          <button type="submit" className="hidden" />
        </form>
        {tickersLoading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground mt-3" />}
      </div>

      {ohlcvError && (
        <div className="mb-6 flex items-center gap-2 text-destructive text-sm bg-destructive/10 rounded-lg p-3">
          <AlertCircle className="h-4 w-4 shrink-0" />
          Failed to load market data. Make sure "{activeSymbol}" has been ingested in the backend.
        </div>
      )}

      {/* Hero Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Card className="bg-background/50 border-border/50">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">Latest Close</p>
              {ohlcvLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : (
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-semibold">${latestOhlcv?.close.toFixed(2) || "—"}</span>
                  {latestOhlcv && prevOhlcv && (
                    <span className={`flex items-center text-xs font-medium ${isUp ? "text-emerald-500" : "text-destructive"}`}>
                      {isUp ? <TrendingUp className="h-3 w-3 mr-0.5" /> : <TrendingDown className="h-3 w-3 mr-0.5" />}
                      {Math.abs(((latestOhlcv.close - prevOhlcv.close) / prevOhlcv.close) * 100).toFixed(2)}%
                    </span>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-background/50 border-border/50">
          <CardContent className="p-4 flex flex-col justify-center h-full">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">Volume</p>
            {ohlcvLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : (
              <span className="text-lg font-medium">{latestOhlcv?.volume.toLocaleString() || "—"}</span>
            )}
          </CardContent>
        </Card>

        <Card className="bg-background/50 border-border/50">
          <CardContent className="p-4 flex flex-col justify-center h-full">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">SMA (20)</p>
            {/* Spin only while genuinely in flight: a failed query also leaves `data` undefined, and
                spinning on that looked like a hang rather than an error. */}
            {smaPending ? <Loader2 className="h-4 w-4 animate-spin" /> : (
              <span className="text-lg font-medium">{latestSma != null ? latestSma.toFixed(2) : "—"}</span>
            )}
          </CardContent>
        </Card>

        <Card className="bg-background/50 border-border/50">
          <CardContent className="p-4 flex flex-col justify-center h-full">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">RSI (14)</p>
            {rsiPending ? <Loader2 className="h-4 w-4 animate-spin" /> : (
              <span className="text-lg font-medium">{latestRsi != null ? latestRsi.toFixed(2) : "—"}</span>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Data Table */}
      <Card className="bg-background/50 border-border/50">
        <CardHeader className="border-b border-border/50 pb-4">
          <CardTitle className="text-sm font-medium">{activeSymbol} OHLCV (Latest 10 Days)</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/50 text-muted-foreground">
                  <th className="text-left font-medium p-4 py-3">Date</th>
                  <th className="text-right font-medium p-4 py-3">Open</th>
                  <th className="text-right font-medium p-4 py-3">High</th>
                  <th className="text-right font-medium p-4 py-3">Low</th>
                  <th className="text-right font-medium p-4 py-3">Close</th>
                  <th className="text-right font-medium p-4 py-3">Volume</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {ohlcvLoading && (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-muted-foreground"><Loader2 className="h-5 w-5 animate-spin mx-auto" /></td>
                  </tr>
                )}
                {!ohlcvLoading && bars.length === 0 && (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-muted-foreground">
                      {ohlcvError ? "Could not load bars." : `No bars stored for ${activeSymbol} yet.`}
                    </td>
                  </tr>
                )}
                {bars.slice(-10).reverse().map(row => (
                  <tr key={row.date} className="hover:bg-secondary/20 transition-colors">
                    <td className="p-4 py-3 text-muted-foreground">{row.date}</td>
                    <td className="p-4 py-3 text-right">${row.open.toFixed(2)}</td>
                    <td className="p-4 py-3 text-right">${row.high.toFixed(2)}</td>
                    <td className="p-4 py-3 text-right">${row.low.toFixed(2)}</td>
                    <td className="p-4 py-3 text-right font-medium">${row.close.toFixed(2)}</td>
                    <td className="p-4 py-3 text-right text-muted-foreground">{row.volume.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </PageContainer>
  );
}
