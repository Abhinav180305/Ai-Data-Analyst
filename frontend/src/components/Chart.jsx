import React from "react";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";

export const PALETTE = ["#E8A33D", "#4FD1C5", "#E8697D", "#8B93A7", "#7C9EFF", "#C792EA"];

export function Chart({ spec }) {
  const { chart_type, x, y, data, title } = spec;
  if (!data || data.length === 0) return null;

  return (
    <div className="chart-card">
      <div className="chart-title">{title}</div>
      <ResponsiveContainer width="100%" height={220}>
        {chart_type === "line" ? (
          <LineChart data={data}>
            <CartesianGrid stroke="#2A3140" strokeDasharray="2 4" />
            <XAxis dataKey={x} stroke="#8B93A7" fontSize={11} />
            <YAxis stroke="#8B93A7" fontSize={11} />
            <Tooltip contentStyle={{ background: "#1C2230", border: "1px solid #2A3140" }} />
            <Line type="monotone" dataKey={y} stroke="#4FD1C5" strokeWidth={2} dot={false} />
          </LineChart>
        ) : chart_type === "pie" ? (
          <PieChart>
            <Pie data={data} dataKey={y} nameKey={x} outerRadius={80}>
              {data.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
            </Pie>
            <Tooltip contentStyle={{ background: "#1C2230", border: "1px solid #2A3140" }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
          </PieChart>
        ) : chart_type === "scatter" ? (
          <ScatterChart>
            <CartesianGrid stroke="#2A3140" strokeDasharray="2 4" />
            <XAxis dataKey={x} stroke="#8B93A7" fontSize={11} />
            <YAxis dataKey={y} stroke="#8B93A7" fontSize={11} />
            <Tooltip contentStyle={{ background: "#1C2230", border: "1px solid #2A3140" }} />
            <Scatter data={data} fill="#E8A33D" />
          </ScatterChart>
        ) : (
          <BarChart data={data}>
            <CartesianGrid stroke="#2A3140" strokeDasharray="2 4" />
            <XAxis dataKey={x} stroke="#8B93A7" fontSize={11} />
            <YAxis stroke="#8B93A7" fontSize={11} />
            <Tooltip contentStyle={{ background: "#1C2230", border: "1px solid #2A3140" }} />
            <Bar dataKey={y} fill="#E8A33D" radius={[2, 2, 0, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
