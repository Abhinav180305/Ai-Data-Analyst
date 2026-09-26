import React, { useCallback, useEffect, useState } from "react";

// Live-updating prediction as the user drags sliders / picks dropdown values
// for the top features of the model just trained.
export function WhatIfSimulator({ session, target, columns, api, showToast }) {
  const [values, setValues] = useState(() =>
    Object.fromEntries(columns.map((c) => [c.name, c.default]))
  );
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(false);

  const runPredict = useCallback(async (nextValues) => {
    setLoading(true);
    try {
      const res = await api.predict(session, nextValues);
      setPrediction(res.prediction);
    } catch (err) {
      showToast(err.message);
    }
    setLoading(false);
  }, [session, api, showToast]);

  useEffect(() => {
    runPredict(values);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleChange = (name, value) => {
    const next = { ...values, [name]: value };
    setValues(next);
    runPredict(next);
  };

  return (
    <div className="whatif-card">
      <div className="chart-title">What-If Simulator — predicting {target}</div>
      <div className="whatif-grid">
        {columns.map((col) => (
          <div className="whatif-control" key={col.name}>
            <label>{col.name}</label>
            {col.type === "numeric" ? (
              <>
                <input
                  type="range"
                  min={col.min}
                  max={col.max}
                  step={(col.max - col.min) / 100 || 1}
                  value={values[col.name]}
                  onChange={(e) => handleChange(col.name, parseFloat(e.target.value))}
                />
                <span className="whatif-value">{Number(values[col.name]).toLocaleString()}</span>
              </>
            ) : (
              <select value={values[col.name]} onChange={(e) => handleChange(col.name, e.target.value)}>
                {col.options.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
              </select>
            )}
          </div>
        ))}
      </div>
      <div className="whatif-result">
        {loading ? "Calculating…" : prediction !== null ? (
          <>Predicted <strong>{target}</strong>: <span className="whatif-prediction">
            {typeof prediction === "number" ? prediction.toLocaleString(undefined, { maximumFractionDigits: 2 }) : prediction}
          </span></>
        ) : "Adjust a control to see a live prediction."}
      </div>
    </div>
  );
}
