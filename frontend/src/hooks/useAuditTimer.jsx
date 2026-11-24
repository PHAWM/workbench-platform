import { useEffect, useRef } from 'react';
import { adminAPI } from '../api/apiService';

const FLUSH_INTERVAL_MS = 60_000; // flush active time every 60 s

/**
 * Tracks active session time for an audit and flushes it to the backend.
 * Call once per audit page (AIApplicationOverview, AuditCriteria, etc.).
 * Active time accumulates only while the tab is visible.
 */
export const useAuditTimer = (auditId) => {
  const startRef = useRef(null);      // when the current visible segment started
  const pendingRef = useRef(0);       // seconds accumulated but not yet flushed
  const timerRef = useRef(null);

  const flush = (id) => {
    const seconds = Math.round(pendingRef.current);
    if (!id || seconds <= 0) return;
    pendingRef.current = 0;
    adminAPI.recordSessionChunk(id, seconds).catch(() => {});
  };

  const tick = () => {
    if (startRef.current !== null) {
      const elapsed = (Date.now() - startRef.current) / 1000;
      pendingRef.current += elapsed;
      startRef.current = Date.now();
    }
    flush(auditId);
  };

  const onVisibilityChange = () => {
    if (document.hidden) {
      // Tab hidden — accumulate elapsed and stop counting
      if (startRef.current !== null) {
        pendingRef.current += (Date.now() - startRef.current) / 1000;
        startRef.current = null;
      }
    } else {
      // Tab visible again — restart segment
      startRef.current = Date.now();
    }
  };

  const onBeforeUnload = () => {
    if (startRef.current !== null) {
      pendingRef.current += (Date.now() - startRef.current) / 1000;
      startRef.current = null;
    }
    flush(auditId);
  };

  useEffect(() => {
    if (!auditId) return;

    startRef.current = document.hidden ? null : Date.now();
    timerRef.current = setInterval(tick, FLUSH_INTERVAL_MS);

    document.addEventListener('visibilitychange', onVisibilityChange);
    window.addEventListener('beforeunload', onBeforeUnload);

    return () => {
      clearInterval(timerRef.current);
      document.removeEventListener('visibilitychange', onVisibilityChange);
      window.removeEventListener('beforeunload', onBeforeUnload);
      // Flush remaining time when navigating away within the SPA
      onBeforeUnload();
    };
  // auditId is stable per page mount; handlers close over it via ref-equivalent
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auditId]);
};
