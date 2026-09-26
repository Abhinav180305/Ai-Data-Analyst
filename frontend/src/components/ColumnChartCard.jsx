import React from "react";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  ComposedChart, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { AuthImage } from "./AuthImage";
import { PALETTE } from "./Chart";
import { API } from "../api/useApi";
import { bucketTopN, withCumulative, CHART_LABELS, COUNT_BASED } from "../utils/chartHelpers";

export function ColumnChartCard({ session, column, opt, barData, fetchImageBlobUrl }) {
  const title = `${CHART_LABELS[opt.type] || opt.type} — ${column}`;

  if (COUNT_BASED.includes(opt.type)) {
    if (!barData) return null;

    if (opt.type === "bar") {
      return (
        <div className="chart-card">
          <div className="chart-title">{title}</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={barData}>
              <CartesianGrid stroke="#2A3140" strokeDasharray="2 4" />
              <XAxis dataKey="value" stroke="#8B93A7" fontSize={11} />
              <YAxis stroke="#8B93A7" fontSize={11} />
              <Tooltip contentStyle={{ background: "#1C2230", border: "1px solid #2A3140" }} />
              <Bar dataKey="count" fill="#E8A33D" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
    }

    if (opt.type === "pie" || opt.type === "donut") {
      const data = bucketTopN(barData);
      return (
        <div className="chart-card">
          <div className="chart-title">{title}</div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={data}
                dataKey="count"
                nameKey="value"
                outerRadius={75}
                innerRadius={opt.type === "donut" ? 40 : 0}
              >
                {data.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: "#1C2230", border: "1px solid #2A3140" }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      );
    }

    if (opt.type === "pareto") {
      const data = withCumulative(barData);
      return (
        <div className="chart-card">
          <div className="chart-title">{title}</div>
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={data}>
              <CartesianGrid stroke="#2A3140" strokeDasharray="2 4" />
              <XAxis dataKey="value" stroke="#8B93A7" fontSize={11} />
              <YAxis yAxisId="left" stroke="#8B93A7" fontSize={11} />
              <YAxis yAxisId="right" orientation="right" stroke="#8B93A7" fontSize={11} domain={[0, 100]} />
              <Tooltip contentStyle={{ background: "#1C2230", border: "1px solid #2A3140" }} />
              <Bar yAxisId="left" dataKey="count" fill="#E8A33D" radius={[2, 2, 0, 0]} />
              <Line yAxisId="right" type="monotone" dataKey="cumPct" stroke="#4FD1C5" strokeWidth={2} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      );
    }
  }

  // image-based: kde, hist, box, violin — needs auth, so fetched as a blob
  return (
    <div className="chart-card">
      <div className="chart-title">{title}</div>
      <AuthImage
        className="result-chart"
        src={`${API}/distribution/${session}/${encodeURIComponent(column)}/${opt.type}`}
        alt={title}
        fetchImageBlobUrl={fetchImageBlobUrl}
      />
    </div>
  );
}
