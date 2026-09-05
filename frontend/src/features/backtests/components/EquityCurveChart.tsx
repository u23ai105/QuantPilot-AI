import { useId } from "react";
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

/**
 * One point of the equity curve as the backend serialises it.
 *
 * Produced by `PerformanceCalculator` (`app/domain/metrics.py`) as
 * `{"date": <isoformat>, "value": <equity>}` and stored in `backtest_results.equity_curve_json`.
 */
export interface EquityPoint {
  date: string;
  value: number;
}

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const currencyPrecise = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});

/** Short axis label — the curve can span years, so keep it to month + year. */
function formatAxisDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
}

function formatFullDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function EquityTooltip({ active, payload, initialCapital }: { active?: boolean; payload?: { payload: EquityPoint }[]; initialCapital: number }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  const change = initialCapital > 0 ? (point.value - initialCapital) / initialCapital : 0;
  return (
    <div className="rounded border border-border bg-background/95 px-3 py-2 text-xs shadow-lg">
      <div className="text-muted-foreground">{formatFullDate(point.date)}</div>
      <div className="mt-1 font-medium text-foreground">{currencyPrecise.format(point.value)}</div>
      <div className={change >= 0 ? "text-emerald-500" : "text-destructive"}>
        {change >= 0 ? "+" : ""}
        {(change * 100).toFixed(2)}% vs. initial
      </div>
    </div>
  );
}

/**
 * Equity curve for a completed backtest.
 *
 * The fill colour follows the final outcome (green if the run ended above its initial capital, red
 * otherwise) and a dashed reference line marks break-even, so a chart is readable without also
 * reading the return number next to it.
 */
export function EquityCurveChart({ data, initialCapital, startDate }: { data: EquityPoint[]; initialCapital: number; startDate?: string }) {
  // Gradient ids are document-global. Two charts open at once with a shared id would both resolve to
  // whichever `<defs>` mounted first, so the second chart could render the wrong colour.
  const gradientId = useId();

  // The worker loads ~100 warmup days before `start_date` so indicators are primed, and those bars
  // end up in the stored curve as a flat run at the initial capital. Plotting them would stretch the
  // axis well before the backtest window shown next to the chart, so drop them here.
  const points = startDate ? data.filter(p => p.date.slice(0, 10) >= startDate) : data;

  if (points.length === 0) {
    return <p className="py-8 text-center text-xs text-muted-foreground">No equity curve was recorded for this run.</p>;
  }

  const finalValue = points[points.length - 1].value;
  const isUp = finalValue >= initialCapital;
  const stroke = isUp ? "hsl(160 84% 39%)" : "hsl(0 72% 51%)";

  // Pad the domain so the line never sits flush against the plot edges.
  const values = points.map(p => p.value).concat(initialCapital);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = (max - min) * 0.08 || Math.max(max * 0.01, 1);

  return (
    <div className="h-64 w-full" role="img" aria-label={`Equity curve: ${currency.format(initialCapital)} at start, ${currency.format(finalValue)} at end`}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={stroke} stopOpacity={0.28} />
              <stop offset="100%" stopColor={stroke} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="hsl(240 3.7% 15.9%)" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={formatAxisDate}
            minTickGap={40}
            tick={{ fill: "hsl(240 5% 64.9%)", fontSize: 11 }}
            stroke="hsl(240 3.7% 15.9%)"
          />
          <YAxis
            domain={[min - pad, max + pad]}
            tickFormatter={v => currency.format(v as number)}
            width={70}
            tick={{ fill: "hsl(240 5% 64.9%)", fontSize: 11 }}
            stroke="hsl(240 3.7% 15.9%)"
          />
          <Tooltip content={<EquityTooltip initialCapital={initialCapital} />} />
          <ReferenceLine
            y={initialCapital}
            stroke="hsl(240 5% 64.9%)"
            strokeDasharray="4 4"
            label={{ value: "Initial capital", position: "insideBottomRight", fill: "hsl(240 5% 64.9%)", fontSize: 10 }}
          />
          {/* Animation off: recharts reveals the area by growing a clip rect, and when the chart
              mounts inside a freshly expanded row that clip stays stuck a few pixels wide, leaving
              the curve invisible. The data is static, so there is nothing to gain from the reveal. */}
          <Area
            type="monotone"
            dataKey="value"
            stroke={stroke}
            strokeWidth={2}
            fill={`url(#${gradientId})`}
            // A one-bar curve has no segment to stroke, so it would render as an empty plot unless
            // the single point is drawn as a dot.
            dot={points.length === 1 ? { r: 3, fill: stroke, stroke } : false}
            activeDot={{ r: 3 }}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
