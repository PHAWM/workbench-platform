import React from 'react';
import * as d3 from 'd3';
import { useD3 } from '../hooks/useD3';
import { useResizeObserver } from '../hooks/useResizeObserver';
import { CHART_DEFAULTS } from '../configs/metricConfigs';
import { formatPercentage } from '../utils/axisFormatters';

// ROUGE Score visualization (precision, recall, f1)
const RougeScoreChart = ({ data, threshold }) => {
  const { containerRef, width: containerWidth } = useResizeObserver();
  const { height, margin, animationDuration } = CHART_DEFAULTS;

  const chartData = [
    { name: 'Precision', value: data?.precision || 0, color: '#3b82f6' },
    { name: 'Recall', value: data?.recall || 0, color: '#10b981' },
    { name: 'F1 Score', value: data?.f1 || 0, color: '#8b5cf6' },
  ];

  const svgRef = useD3(
    (chart, { width, height: innerHeight }) => {
      if (!data) return;

      const x = d3.scaleBand()
        .range([0, width])
        .domain(chartData.map(d => d.name))
        .padding(0.3);

      const y = d3.scaleLinear()
        .range([innerHeight, 0])
        .domain([0, 1]);

      // X Axis
      chart.append('g')
        .attr('transform', `translate(0,${innerHeight})`)
        .call(d3.axisBottom(x).tickSizeOuter(0))
        .attr('class', 'text-gray-500 text-sm');

      // Y Axis
      chart.append('g')
        .call(d3.axisLeft(y).ticks(5).tickFormat(d => `${(d * 100).toFixed(0)}%`))
        .attr('class', 'text-gray-500 text-sm');

      // Threshold line
      if (threshold) {
        const thresholdVal = parseFloat(threshold);
        if (!isNaN(thresholdVal)) {
          chart.append('line')
            .attr('x1', 0)
            .attr('x2', width)
            .attr('y1', y(thresholdVal))
            .attr('y2', y(thresholdVal))
            .attr('stroke', '#ef4444')
            .attr('stroke-width', 2)
            .attr('stroke-dasharray', '5,5');

          chart.append('text')
            .attr('x', width - 10)
            .attr('y', y(thresholdVal) - 5)
            .attr('text-anchor', 'end')
            .attr('class', 'text-xs fill-red-500')
            .text(`Threshold: ${(thresholdVal * 100).toFixed(0)}%`);
        }
      }

      // Bars
      chart.selectAll('.bar')
        .data(chartData)
        .enter()
        .append('rect')
        .attr('x', d => x(d.name))
        .attr('width', x.bandwidth())
        .attr('fill', d => d.color)
        .attr('rx', 4)
        .attr('y', innerHeight)
        .attr('height', 0)
        .transition()
        .duration(animationDuration)
        .attr('y', d => y(d.value))
        .attr('height', d => innerHeight - y(d.value));

      // Value labels
      chart.selectAll('.label')
        .data(chartData)
        .enter()
        .append('text')
        .attr('x', d => x(d.name) + x.bandwidth() / 2)
        .attr('y', d => y(d.value) - 5)
        .attr('text-anchor', 'middle')
        .attr('class', 'text-sm font-medium fill-gray-700')
        .text(d => `${(d.value * 100).toFixed(1)}%`);
    },
    [data, threshold, containerWidth],
    { containerWidth, height: 300, margin }
  );

  if (!data) {
    return (
      <div className="text-gray-500 italic text-center py-8">
        No ROUGE score data available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Chart */}
      <div ref={containerRef} className="relative bg-white rounded-lg w-full">
        <svg ref={svgRef} className="w-full h-full" />
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg text-center">
          <div className="text-xs text-gray-500 uppercase">Precision</div>
          <div className="text-xl font-bold text-blue-600">
            {formatPercentage(data.precision)}
          </div>
        </div>
        <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-center">
          <div className="text-xs text-gray-500 uppercase">Recall</div>
          <div className="text-xl font-bold text-green-600">
            {formatPercentage(data.recall)}
          </div>
        </div>
        <div className="p-4 bg-purple-50 border border-purple-200 rounded-lg text-center">
          <div className="text-xs text-gray-500 uppercase">F1 Score</div>
          <div className="text-xl font-bold text-purple-600">
            {formatPercentage(data.f1)}
          </div>
        </div>
      </div>
    </div>
  );
};

export default RougeScoreChart;
