import React, { useState } from "react";

// --- Auth screen (login / signup) ------------------------------------------
export function AuthScreen({ onAuthed, apiForAuth, showToast }) {
  const [mode, setMode] = useState("login"); // "login" | "signup"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!email || !password) return;
    setBusy(true);
    try {
      const res = mode === "login"
        ? await apiForAuth.login(email, password)
        : await apiForAuth.signup(email, password);
      onAuthed(res.access_token, res.email);
    } catch (err) {
      showToast(err.message);
    }
    setBusy(false);
  };

  return (
    <div className="upload-screen">
      <h1>{mode === "login" ? "Log in" : "Create an account"}</h1>
      <p>AI Data Analyst — your data stays tied to your account only.</p>
      <form className="auth-form" onSubmit={submit}>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          required
        />
        <input
          type="password"
          placeholder={mode === "signup" ? "Password (min. 8 characters)" : "Password"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          required
        />
        <button type="submit" disabled={busy}>
          {busy ? "Please wait…" : mode === "login" ? "Log in" : "Sign up"}
        </button>
      </form>
      <button className="auth-switch" onClick={() => setMode(mode === "login" ? "signup" : "login")}>
        {mode === "login" ? "Need an account? Sign up" : "Already have an account? Log in"}
      </button>
    </div>
  );
}
