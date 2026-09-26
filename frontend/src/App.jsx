import React, { useState, useRef, useCallback } from "react";
import html2canvas from "html2canvas";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import "./index.css";
import "./app.css";

import { API, useApi } from "./api/useApi";
import { useToasts } from "./hooks/useToasts";
import { ToastStack } from "./components/ToastStack";
import { AuthImage } from "./components/AuthImage";
import { AuthScreen } from "./components/AuthScreen";
import { Chart } from "./components/Chart";
import { ColumnChartCard } from "./components/ColumnChartCard";
import { FeatureImportanceChart } from "./components/FeatureImportanceChart";
import { WhatIfSimulator } from "./components/WhatIfSimulator";
import { chartOptionsFor, CHART_LABELS, COUNT_BASED } from "./utils/chartHelpers";

export default function App() {
  // Deliberately NOT reading a token from localStorage on init — every fresh
  // page load or refresh should require logging in again, no persisted session.
  const [token, setToken] = useState(null);
  const [userEmail, setUserEmail] = useState(null);
  const { toasts, showToast, dismissToast } = useToasts();

  const [session, setSession] = useState(null);
  const [profile, setProfile] = useState(null);
  const [dataHealth, setDataHealth] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState("chat");
  const [selectedChart, setSelectedChart] = useState(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [barData, setBarData] = useState(null);
  const [overviewCharts, setOverviewCharts] = useState(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [selectedColumn, setSelectedColumn] = useState("");
  const [columnBarData, setColumnBarData] = useState(null);
  const [columnLoading, setColumnLoading] = useState(false);
  const [mlTarget, setMlTarget] = useState("");
  const [mlResults, setMlResults] = useState(null);
  const [mlLoading, setMlLoading] = useState(false);
  const fileRef = useRef(null);
  const contentRef = useRef(null);

  // Clears every piece of state tied to a specific account's data — must run
  // on logout AND on forced logout (expired token), so switching accounts in
  // the same browser tab never shows a leftover session from the last user.
  const resetSessionState = useCallback(() => {
    setSession(null);
    setProfile(null);
    setDataHealth(null);
    setMessages([]);
    setInput("");
    setTab("chat");
    setSelectedChart(null);
    setBarData(null);
    setOverviewCharts(null);
    setSelectedColumn("");
    setColumnBarData(null);
    setMlTarget("");
    setMlResults(null);
  }, []);

  const handleAuthError = useCallback(() => {
    setToken(null);
    setUserEmail(null);
    resetSessionState();
  }, [resetSessionState]);

  const api = useApi(token, handleAuthError);

  const handleAuthed = (accessToken, email) => {
    resetSessionState();
    setToken(accessToken);
    setUserEmail(email);
  };

  const handleLogout = () => {
    handleAuthError();
    showToast("Logged out", "info");
  };

  const handleRunModels = async () => {
    if (!mlTarget) return;
    setMlLoading(true);
    setMlResults(null);
    try {
      const res = await api.trainModels(session, mlTarget);
      setMlResults(res);
    } catch (err) {
      showToast(err.message);
    }
    setMlLoading(false);
  };

  const handleDownloadPage = async () => {
    if (tab === "ml") {
      if (!mlResults) {
        showToast("Run the models first, then download.", "info");
        return;
      }
      const doc = new jsPDF({ unit: "pt", format: "a4" });
      doc.setFontSize(16);
      doc.text("AI Data Analyst — ML Insights", 40, 40);
      doc.setFontSize(11);
      doc.text(
        `${mlResults.task === "classification" ? "Classification" : "Regression"} task on "${mlResults.target}"`,
        40, 64
      );
      doc.text(
        `${mlResults.n_train} train / ${mlResults.n_test} test rows — ${mlResults.n_features} features`,
        40, 80
      );

      const head = mlResults.task === "classification"
        ? [["Model", "Accuracy", "Precision", "Recall", "F1"]]
        : [["Model", "R²", "RMSE", "MAE"]];

      const body = mlResults.results.map((r) => {
        if (r.error) {
          const cols = head[0].length;
          return [r.model, r.error, ...Array(cols - 2).fill("")];
        }
        return mlResults.task === "classification"
          ? [r.model, r.metrics.accuracy, r.metrics.precision, r.metrics.recall, r.metrics.f1]
          : [r.model, r.metrics.r2, r.metrics.rmse, r.metrics.mae];
      });

      let finalY = 100;
      autoTable(doc, {
        head, body,
        startY: 100,
        styles: { fontSize: 10, cellPadding: 6 },
        headStyles: { fillColor: [30, 34, 48], textColor: [232, 163, 61] },
        alternateRowStyles: { fillColor: [22, 27, 38] },
        didDrawPage: (data) => { finalY = data.cursor.y; },
      });

      if (mlResults.feature_importance) {
        doc.setFontSize(12);
        doc.text(`Top Feature Importance — ${mlResults.feature_importance.model}`, 40, finalY + 30);
        autoTable(doc, {
          head: [["Feature", "Importance"]],
          body: mlResults.feature_importance.features.map((f) => [f.feature, f.importance]),
          startY: finalY + 40,
          styles: { fontSize: 10, cellPadding: 6 },
          headStyles: { fillColor: [30, 34, 48], textColor: [79, 209, 197] },
          alternateRowStyles: { fillColor: [22, 27, 38] },
        });
      }

      doc.save(`ai-data-analyst-ml-${mlResults.target}.pdf`);
      return;
    }

    const el = contentRef.current;
    if (!el) return;

    const touched = [];
    const relax = (node) => {
      touched.push({
        node,
        overflow: node.style.overflow,
        height: node.style.height,
        width: node.style.width,
        flex: node.style.flex,
      });
      node.style.overflow = "visible";
      node.style.height = "auto";
      node.style.width = "max-content";
      node.style.flex = "none";
    };

    relax(el);
    el.querySelectorAll("*").forEach((node) => {
      const style = window.getComputedStyle(node);
      if (style.overflowY === "auto" || style.overflowY === "scroll" || parseFloat(style.flexGrow) > 0) {
        relax(node);
      }
    });

    await new Promise((r) => setTimeout(r, 60));

    try {
      const w = el.scrollWidth;
      const h = el.scrollHeight;
      const canvas = await html2canvas(el, {
        backgroundColor: "#10141C",
        scale: 2,
        width: w,
        height: h,
        windowWidth: w,
        windowHeight: h,
        scrollX: 0,
        scrollY: 0,
      });
      const imgData = canvas.toDataURL("image/png");
      const pdf = new jsPDF({ orientation: "portrait", unit: "px", format: [canvas.width, canvas.height] });
      pdf.addImage(imgData, "PNG", 0, 0, canvas.width, canvas.height);
      pdf.save(`ai-data-analyst-${tab}.pdf`);
    } catch (err) {
      showToast("Could not generate the PDF: " + err.message);
    } finally {
      touched.forEach(({ node, overflow, height, width, flex }) => {
        node.style.overflow = overflow;
        node.style.height = height;
        node.style.width = width;
        node.style.flex = flex;
      });
    }
  };

  const handleColumnSelect = async (colName) => {
    setSelectedColumn(colName);
    setColumnBarData(null);
    if (!colName || colName === "__correlation__") return;
    const colProfile = profile.columns.find((c) => c.name === colName);
    const options = chartOptionsFor(colProfile);
    const needsCounts = options.some((o) => COUNT_BASED.includes(o.type));
    if (needsCounts) {
      setColumnLoading(true);
      try {
        const res = await api.categoryCounts(session, colName);
        setColumnBarData(res.data);
      } catch (err) {
        showToast(err.message);
      }
      setColumnLoading(false);
    }
  };

  const openDashboardTab = async () => {
    setTab("dashboard");
    if (overviewCharts || !session) return;
    setOverviewLoading(true);
    try {
      const res = await api.dashboard(session);
      setOverviewCharts(res.charts);
    } catch (err) {
      showToast(err.message);
    }
    setOverviewLoading(false);
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setBusy(true);
    try {
      const data = await api.upload(file);
      setSession(data.session_id);
      setProfile(data.profile);
      setDataHealth(data.health || null);
      setMessages([{
        role: "system",
        text: `Loaded "${file.name}" — ${data.profile.n_rows.toLocaleString()} rows × ${data.profile.n_cols} columns. Ask me anything about it.`,
      }]);
      showToast(`Loaded "${file.name}"`, "success");
    } catch (err) {
      showToast(err.message);
    }
    setBusy(false);
  };

  const handleAsk = async () => {
    if (!input.trim() || !session) return;
    const question = input.trim();
    setMessages((m) => [...m, { role: "user", text: question }]);
    setInput("");
    setBusy(true);

    // Last few Q&A turns give the model short-term memory, so follow-ups
    // like "now break that down by region" resolve against prior context.
    const history = messages
      .filter((m) => m.role === "assistant" && m.data && m.data.code)
      .slice(-3)
      .map((m) => ({ question: m.question || "", code: m.data.code, explanation: m.data.explanation || "" }));

    const streamId = Date.now();
    setMessages((m) => [...m, { role: "assistant_streaming", id: streamId, raw: "" }]);

    try {
      const result = await api.streamQuery(session, question, history, (chunk) => {
        setMessages((m) => m.map((msg) =>
          msg.role === "assistant_streaming" && msg.id === streamId
            ? { ...msg, raw: msg.raw + chunk }
            : msg
        ));
      });

      if (!result.ok) {
        setMessages((m) => m.map((msg) =>
          msg.id === streamId ? { role: "error", text: result.error } : msg
        ));
        showToast(result.error);
        setBusy(false);
        return;
      }

      const msgData = { ...result.data, insight: "" };
      setMessages((m) => m.map((msg) =>
        msg.id === streamId ? { role: "assistant", id: streamId, question, data: msgData } : msg
      ));
      setBusy(false);

      await api.streamInsight(question, result.data.insight_context || "", (token) => {
        setMessages((m) => m.map((msg) =>
          msg.role === "assistant" && msg.id === streamId
            ? { ...msg, data: { ...msg.data, insight: msg.data.insight + token } }
            : msg
        ));
      });
    } catch (err) {
      setMessages((m) => m.map((msg) =>
        msg.id === streamId ? { role: "error", text: err.message } : msg
      ));
      showToast(err.message);
      setBusy(false);
    }
  };

  const selectChart = async (column, type) => {
    setSelectedChart({ column, type, title: `${CHART_LABELS[type] || type} — ${column}` });
    setBarData(null);
    setChartLoading(true);
    try {
      if (COUNT_BASED.includes(type)) {
        const res = await api.categoryCounts(session, column);
        setBarData(res.data);
      }
    } catch (err) {
      showToast(err.message);
    }
    setChartLoading(false);
  };

  if (!token) {
    return (
      <div className="app">
        <ToastStack toasts={toasts} onDismiss={dismissToast} />
        <header className="topbar">
          <div className="brand"><span className="brand-mark">◆</span> AI Data Analyst</div>
        </header>
        <AuthScreen onAuthed={handleAuthed} apiForAuth={api} showToast={showToast} />
      </div>
    );
  }

  return (
    <div className="app">
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">◆</span> AI Data Analyst
        </div>
        {session && (
          <>
            <nav className="tabs">
              <button className={tab === "chat" ? "tab active" : "tab"} onClick={() => setTab("chat")}>
                Analysis
              </button>
              <button className={tab === "dashboard" ? "tab active" : "tab"} onClick={openDashboardTab}>
                Dashboard
              </button>
              <button className={tab === "ml" ? "tab active" : "tab"} onClick={() => setTab("ml")}>
                ML Insights
              </button>
            </nav>
            <button className="download-btn" onClick={handleDownloadPage}>Download Page</button>
          </>
        )}
        <div className="account-info">
          <span className="account-email">{userEmail}</span>
          <button className="logout-btn" onClick={handleLogout}>Log out</button>
        </div>
      </header>

      <div ref={contentRef} className="page-content">
        {!session ? (
          <div className="upload-screen">
            <h1>Upload a CSV to start analyzing</h1>
            <p>Claude will write the SQL or Python, run it, and explain what it finds.</p>
            <label className="upload-drop">
              <input ref={fileRef} type="file" accept=".csv" onChange={handleUpload} hidden />
              {busy ? "Uploading…" : "Choose a CSV file"}
            </label>
          </div>
        ) : tab === "chat" ? (
          <div className="chat-layout">
            <aside className="schema-panel">
              {dataHealth && (
                <div className={`health-card health-grade-${dataHealth.grade[0]}`}>
                  <div className="health-grade">{dataHealth.grade}</div>
                  <div className="health-details">
                    <div className="health-score">Data Health: {dataHealth.score}/100</div>
                    <div className="health-row">{dataHealth.completeness_pct}% complete</div>
                    {dataHealth.duplicate_rows > 0 && (
                      <div className="health-row">{dataHealth.duplicate_rows} duplicate row{dataHealth.duplicate_rows === 1 ? "" : "s"}</div>
                    )}
                    {dataHealth.outlier_columns.length > 0 && (
                      <div className="health-row">Outliers: {dataHealth.outlier_columns.map((o) => o.column).join(", ")}</div>
                    )}
                    {dataHealth.high_cardinality_columns.length > 0 && (
                      <div className="health-row">High-cardinality: {dataHealth.high_cardinality_columns.join(", ")}</div>
                    )}
                  </div>
                </div>
              )}
              <div className="panel-label">Schema</div>
              {(() => {
                // A column has full stats (n_unique present) only if it made
                // the PCA/entropy top-10 cut for wide datasets — see profile_dataframe.
                const important = profile.columns.filter((c) => c.n_unique !== undefined);
                const rest = profile.columns.filter((c) => c.n_unique === undefined);
                const shown = important.length > 0 ? important : profile.columns;
                return (
                  <>
                    <div className="schema-list">
                      {shown.map((c) => (
                        <div className="schema-row" key={c.name}>
                          <span className="col-name">{c.name}</span>
                          <span className="col-type">{c.dtype}</span>
                        </div>
                      ))}
                    </div>
                    {rest.length > 0 && (
                      <div className="schema-note">
                        +{rest.length} more column{rest.length === 1 ? "" : "s"} — ask about any
                        of them by name and they'll still be used.
                      </div>
                    )}
                  </>
                );
              })()}
            </aside>

            <main className="chat-panel">
              <div className="messages">
                {messages.map((m, i) => (
                  <div key={i} className={`msg msg-${m.role}`}>
                    {m.role === "user" && <div className="bubble user-bubble">{m.text}</div>}
                    {m.role === "system" && <div className="bubble system-bubble">{m.text}</div>}
                    {m.role === "error" && <div className="bubble error-bubble">{m.text}</div>}
                    {m.role === "assistant_streaming" && (
                      <div className="bubble assistant-bubble">
                        <div className="code-block">
                          <div className="code-label">Generating…</div>
                          <pre>{m.raw}<span className="stream-cursor">▋</span></pre>
                        </div>
                      </div>
                    )}
                    {m.role === "assistant" && (
                      <div className="bubble assistant-bubble">
                        <div className="code-block">
                          <div className="code-label">{m.data.engine === "sql" ? "SQL" : "Python"}</div>
                          <pre>{m.data.code}</pre>
                        </div>
                        {m.data.chart_url && (
                          <AuthImage
                            className="result-chart"
                            src={`${API}${m.data.chart_url}`}
                            alt="Generated chart"
                            fetchImageBlobUrl={api.fetchImageBlobUrl}
                          />
                        )}
                        {m.data.rows && (
                          <div className="result-table-wrap">
                            <table className="result-table">
                              <thead>
                                <tr>{m.data.columns.map((c) => <th key={c}>{c}</th>)}</tr>
                              </thead>
                              <tbody>
                                {m.data.rows.slice(0, 20).map((row, ri) => (
                                  <tr key={ri}>
                                    {m.data.columns.map((c) => <td key={c}>{String(row[c])}</td>)}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                        <div className="insight">{m.data.insight}</div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
              <div className="composer">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAsk()}
                  placeholder="e.g. What are the top 5 categories by total revenue?"
                  disabled={busy}
                />
                <button onClick={handleAsk} disabled={busy || !input.trim()}>Ask</button>
              </div>
            </main>
          </div>
        ) : tab === "dashboard" ? (
          <div className="dashboard-view">
            <div className="column-select-bar">
              <label className="panel-label" htmlFor="col-select">Column</label>
              <select
                id="col-select"
                value={selectedColumn}
                onChange={(e) => handleColumnSelect(e.target.value)}
              >
                <option value="">General Overview</option>
                <option value="__correlation__">Correlation Heatmap</option>
                {profile.columns.map((c) => (
                  <option key={c.name} value={c.name}>{c.name}</option>
                ))}
              </select>
            </div>

            {selectedColumn === "__correlation__" ? (
              <div className="overview-section">
                <div className="chart-card chart-card-large">
                  <div className="chart-title">Correlation Heatmap</div>
                  <AuthImage
                    className="result-chart"
                    src={`${API}/correlation/${session}`}
                    alt="Correlation Heatmap"
                    fetchImageBlobUrl={api.fetchImageBlobUrl}
                  />
                </div>
              </div>
            ) : !selectedColumn ? (
              <div className="overview-section">
                {overviewLoading ? (
                  <div className="chart-placeholder">Generating overview…</div>
                ) : overviewCharts && overviewCharts.length > 0 ? (
                  <div className="chart-grid">
                    {overviewCharts.map((c, i) => <Chart key={i} spec={c} />)}
                  </div>
                ) : (
                  <div className="chart-placeholder">No overview charts yet.</div>
                )}
              </div>
            ) : (
              <div className="overview-section">
                {columnLoading ? (
                  <div className="chart-placeholder">Generating…</div>
                ) : (
                  <div className="chart-grid">
                    {chartOptionsFor(profile.columns.find((c) => c.name === selectedColumn)).map((opt) => (
                      <ColumnChartCard
                        key={opt.type}
                        session={session}
                        column={selectedColumn}
                        opt={opt}
                        barData={columnBarData}
                        fetchImageBlobUrl={api.fetchImageBlobUrl}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="ml-view">
            <div className="ml-controls">
              <label className="panel-label" htmlFor="ml-target">Predict column</label>
              <select id="ml-target" value={mlTarget} onChange={(e) => setMlTarget(e.target.value)}>
                <option value="">Choose a target column…</option>
                {profile.columns.map((c) => (
                  <option key={c.name} value={c.name}>{c.name} ({c.dtype})</option>
                ))}
              </select>
              <button onClick={handleRunModels} disabled={!mlTarget || mlLoading}>
                {mlLoading ? "Training…" : "Run Models"}
              </button>
            </div>

            {mlResults && (
              <div className="ml-results">
                <div className="ml-summary">
                  {mlResults.task === "classification" ? "Classification" : "Regression"} task on{" "}
                  <strong>{mlResults.target}</strong> — {mlResults.n_train} train / {mlResults.n_test} test rows,{" "}
                  {mlResults.n_features} features.
                </div>
                <table className="ml-table">
                  <thead>
                    <tr>
                      <th>Model</th>
                      {mlResults.task === "classification" ? (
                        <>
                          <th>Accuracy</th><th>Precision</th><th>Recall</th><th>F1</th>
                        </>
                      ) : (
                        <>
                          <th>R²</th><th>RMSE</th><th>MAE</th>
                        </>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {mlResults.results.map((r) => (
                      <tr key={r.model}>
                        <td>{r.model}</td>
                        {r.error ? (
                          <td colSpan={4} className="ml-error">{r.error}</td>
                        ) : mlResults.task === "classification" ? (
                          <>
                            <td>{r.metrics.accuracy}</td>
                            <td>{r.metrics.precision}</td>
                            <td>{r.metrics.recall}</td>
                            <td>{r.metrics.f1}</td>
                          </>
                        ) : (
                          <>
                            <td>{r.metrics.r2}</td>
                            <td>{r.metrics.rmse}</td>
                            <td>{r.metrics.mae}</td>
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>

                {mlResults.feature_importance && (
                  <div className="ml-importance">
                    <FeatureImportanceChart data={mlResults.feature_importance} />
                  </div>
                )}

                {mlResults.whatif_columns && mlResults.whatif_columns.length > 0 && (
                  <WhatIfSimulator
                    session={session}
                    target={mlResults.target}
                    columns={mlResults.whatif_columns}
                    api={api}
                    showToast={showToast}
                  />
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
