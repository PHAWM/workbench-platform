import { useRef, useEffect } from 'react';
import * as d3 from 'd3';

export const useD3 = (renderFn, deps, options = {}) => {
  const svgRef = useRef(null);

  const {
    containerWidth = 600,
    height = 600,
    margin = { top: 10, right: 20, bottom: 50, left: 50 },
  } = options;

  const innerWidth = containerWidth - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;

  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    svg
      .attr('viewBox', `0 0 ${containerWidth} ${height}`)
      .attr('preserveAspectRatio', 'xMidYMid meet');

    const chartGroup = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    renderFn(chartGroup, {
      width: innerWidth,
      height: innerHeight,
      margin,
      containerWidth,
      containerHeight: height,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return svgRef;
};

export default useD3;
