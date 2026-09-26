import React from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

export function FeatureImportanceChart({ data }) {
  if (!data || !data.features || data.features.length === 0) return null;
  const chartData = [...data.features].reverse();
  return (
    <div className="chart-card chart-card-large">
      <div className="chart-title">Top Feature Importance — {data.model}</div>
      <ResponsiveContainer width="100%" height={Math.max(220, chartData.length * 34)}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 20 }}>
          <CartesianGrid stroke="#2A3140" strokeDasharray="2 4" />
          <XAxis type="number" stroke="#8B93A7" fontSize={11} />
          <YAxis type="category" dataKey="feature" stroke="#8B93A7" fontSize={11} width={160} />
          <Tooltip contentStyle={{ background: "#1C2230", border: "1px solid #2A3140" }} />
          <Bar dataKey="importance" fill="#4FD1C5" radius={[0, 2, 2, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
