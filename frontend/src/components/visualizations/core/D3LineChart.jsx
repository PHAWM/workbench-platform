import React from 'react';
import { useD3 } from '../hooks/useD3';
import { useResizeObserver } from '../hooks/useResizeObserver';
import { CHART_DEFAULTS } from '../configs/metricConfigs';

const D3LineChart = ({ data = [], metricType = 'accuracy' }) => {
  const { containerRef, width: containerWidth } = useResizeObserver();
  const { height, margin } = CHART_DEFAULTS;

  const svgRef = useD3(
    (chart, { width, height: innerHeight }) => {
      if (!data || data.length === 0) {
        chart.append('text')
          .attr('x', width / 2)
          .attr('y', innerHeight / 2)
          .attr('text-anchor', 'middle')
          .attr('class', 'text-gray-400 text-base')
          .text('Line chart coming soon');
        return;
      }
    },
    [data, containerWidth],
    { containerWidth, height, margin }
  );

  return (
    <div ref={containerRef} className="relative bg-white rounded-lg w-full">
      <svg ref={svgRef} className="w-full h-full" />
    </div>
  );
};

export default D3LineChart;
