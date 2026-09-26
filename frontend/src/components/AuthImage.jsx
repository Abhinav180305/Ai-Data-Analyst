import React, { useEffect, useState } from "react";

// Renders an <img> whose source requires an auth header — fetches as a blob
// under the hood and swaps in an object URL once it's ready.
export function AuthImage({ src, alt, className, fetchImageBlobUrl, onError }) {
  const [blobUrl, setBlobUrl] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let currentUrl = null;
    setFailed(false);
    setBlobUrl(null);

    fetchImageBlobUrl(src)
      .then((url) => {
        if (cancelled) { URL.revokeObjectURL(url); return; }
        currentUrl = url;
        setBlobUrl(url);
      })
      .catch((err) => {
        if (!cancelled) {
          setFailed(true);
          if (onError) onError(err);
        }
      });

    return () => {
      cancelled = true;
      if (currentUrl) URL.revokeObjectURL(currentUrl);
    };
  }, [src, fetchImageBlobUrl]);

  if (failed) return <div className="chart-placeholder">Could not load this chart.</div>;
  if (!blobUrl) return <div className="chart-placeholder">Loading…</div>;
  return <img src={blobUrl} alt={alt} className={className} />;
}
