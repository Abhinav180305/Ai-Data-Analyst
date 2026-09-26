import { useCallback, useState } from "react";

// --- Toast notifications ---------------------------------------------------
let toastId = 0;

export function useToasts() {
  const [toasts, setToasts] = useState([]);
  const showToast = useCallback((message, kind = "error") => {
    const id = ++toastId;
    setToasts((t) => [...t, { id, message, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5000);
  }, []);
  const dismissToast = useCallback((id) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);
  return { toasts, showToast, dismissToast };
}
