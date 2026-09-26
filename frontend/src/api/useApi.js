import { useCallback } from "react";

export const API = "/api";

// --- Auth-aware API layer ---------------------------------------------------
export function useApi(token, onAuthError) {
  const authHeaders = useCallback(
    (extra = {}) => ({ Authorization: `Bearer ${token}`, ...extra }),
    [token]
  );

  const handleRes = useCallback(async (res) => {
    if (res.status === 401) {
      onAuthError();
      throw new Error("Your session expired — please log in again.");
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed (${res.status})`);
    }
    return res;
  }, [onAuthError]);

  const signup = useCallback(async (email, password) => {
    const res = await fetch(`${API}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "Signup failed");
    return res.json();
  }, []);

  const login = useCallback(async (email, password) => {
    const res = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "Login failed");
    return res.json();
  }, []);

  const upload = useCallback(async (file) => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${API}/upload`, { method: "POST", headers: authHeaders(), body: fd });
    await handleRes(res);
    return res.json();
  }, [authHeaders, handleRes]);

  const query = useCallback(async (session_id, question) => {
    const res = await fetch(`${API}/query`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ session_id, question }),
    });
    await handleRes(res);
    return res.json();
  }, [authHeaders, handleRes]);

  const dashboard = useCallback(async (session_id) => {
    const res = await fetch(`${API}/dashboard`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ session_id }),
    });
    await handleRes(res);
    return res.json();
  }, [authHeaders, handleRes]);

  const categoryCounts = useCallback(async (session_id, column) => {
    const res = await fetch(`${API}/category-counts/${session_id}/${encodeURIComponent(column)}`, {
      headers: authHeaders(),
    });
    await handleRes(res);
    return res.json();
  }, [authHeaders, handleRes]);

  const trainModels = useCallback(async (session_id, target) => {
    const res = await fetch(`${API}/ml/train`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ session_id, target }),
    });
    await handleRes(res);
    return res.json();
  }, [authHeaders, handleRes]);

  const predict = useCallback(async (session_id, inputs) => {
    const res = await fetch(`${API}/ml/predict`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ session_id, inputs }),
    });
    await handleRes(res);
    return res.json();
  }, [authHeaders, handleRes]);

  // Images (chart.png, distribution charts, correlation heatmap) can't carry
  // an Authorization header via a plain <img src="...">, so we fetch them as
  // authenticated blobs instead and hand back an object URL for <img> to use.
  const fetchImageBlobUrl = useCallback(async (url) => {
    const res = await fetch(url, { headers: authHeaders() });
    await handleRes(res);
    const blob = await res.blob();
    return URL.createObjectURL(blob);
  }, [authHeaders, handleRes]);

  const streamInsight = useCallback(async (question, context, onToken) => {
    const res = await fetch(`${API}/insight/stream`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ question, context }),
    });
    await handleRes(res);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      onToken(decoder.decode(value, { stream: true }));
    }
  }, [authHeaders, handleRes]);

  const streamQuery = useCallback(async (session_id, question, history, onRawToken) => {
    const res = await fetch(`${API}/query/stream`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ session_id, question, engine: "auto", history }),
    });
    await handleRes(res);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    const MARKER_LEN = 12;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      if (buffer.includes("__FINAL__") || buffer.includes("__ERROR__")) continue;

      if (buffer.length > MARKER_LEN) {
        const safe = buffer.slice(0, buffer.length - MARKER_LEN);
        if (safe) {
          onRawToken(safe);
          buffer = buffer.slice(safe.length);
        }
      }
    }

    const finalIdx = buffer.indexOf("__FINAL__");
    const errorIdx = buffer.indexOf("__ERROR__");
    if (finalIdx !== -1) {
      return { ok: true, data: JSON.parse(buffer.slice(finalIdx + "__FINAL__".length)) };
    }
    if (errorIdx !== -1) {
      return { ok: false, error: buffer.slice(errorIdx + "__ERROR__".length) };
    }
    if (buffer) onRawToken(buffer);
    return { ok: false, error: "Stream ended without a result" };
  }, [authHeaders, handleRes]);

  return {
    signup, login, upload, query, dashboard, categoryCounts, trainModels, predict,
    fetchImageBlobUrl, streamInsight, streamQuery,
  };
}
