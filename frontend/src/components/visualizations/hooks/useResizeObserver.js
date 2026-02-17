import { useState, useEffect, useRef } from 'react';

export const useResizeObserver = (defaultWidth = 600) => {
  const containerRef = useRef(null);
  const [width, setWidth] = useState(defaultWidth);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = entry.contentRect.width;
        if (w > 0) setWidth(w);
      }
    });

    resizeObserver.observe(container);
    return () => resizeObserver.disconnect();
  }, []);

  return { containerRef, width };
};

export default useResizeObserver;
