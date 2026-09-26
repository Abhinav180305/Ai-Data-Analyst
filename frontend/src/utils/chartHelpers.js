export function chartOptionsFor(col) {
  const numeric = col.dtype.startsWith("int") || col.dtype.startsWith("float");
  if (numeric) {
    if (col.n_unique <= 8) {
      return [
        { label: "Bar", type: "bar" },
        { label: "Pie", type: "pie" },
        { label: "Boxplot", type: "box" },
        { label: "Histogram", type: "hist" },
      ];
    }
    return [
      { label: "Histogram", type: "hist" },
      { label: "KDE", type: "kde" },
      { label: "Boxplot", type: "box" },
      { label: "Violin", type: "violin" },
    ];
  }
  return [
    { label: "Bar", type: "bar" },
    { label: "Pie", type: "pie" },
    { label: "Pareto", type: "pareto" },
    { label: "Donut", type: "donut" },
  ];
}

export function bucketTopN(data, n = 9) {
  if (!data || data.length <= n) return data;
  const top = data.slice(0, n);
  const restSum = data.slice(n).reduce((s, d) => s + d.count, 0);
  return [...top, { value: "Other", count: restSum }];
}

export function withCumulative(data) {
  const total = data.reduce((s, d) => s + d.count, 0);
  let running = 0;
  return data.map((d) => {
    running += d.count;
    return { ...d, cumPct: total ? Math.round((running / total) * 1000) / 10 : 0 };
  });
}

export const CHART_LABELS = {
  kde: "Distribution (KDE)", box: "Boxplot", hist: "Histogram", violin: "Violin",
  bar: "Counts", pie: "Share", pareto: "Pareto", donut: "Share (donut)",
};

export const COUNT_BASED = ["bar", "pie", "pareto", "donut"];
