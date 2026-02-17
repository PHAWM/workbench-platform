import React from 'react';
import * as d3 from 'd3';
import { useD3 } from '../hooks/useD3';
import { useResizeObserver } from '../hooks/useResizeObserver';
import { CHART_DEFAULTS } from '../configs/metricConfigs';
import { formatPercentage, formatCount } from '../utils/axisFormatters';
import { COLORS } from '../utils/colorScales';

// Fairness metrics visualization (Demographic Parity, Statistical Parity)
const FairnessChart = ({ data, metricType = 'demographic_parity' }) => {
  const { containerRef, width: containerWidth } = useResizeObserver();
  const { height, margin, barPadding, animationDuration } = CHART_DEFAULTS;

  // Extract group data
  const groupStats = data?.group_statistics || data?.groupStatistics || {};
  const groups = Object.entries(groupStats).map(([name, stats]) => ({
    name,
    positiveRate: stats.positive_rate || stats.positiveRate || 0,
    sampleSize: stats.sample_size || stats.sampleSize || 0,
    accuracy: stats.accuracy,
  }));

  const parityDiff = data?.parity_difference || data?.parityDifference;
  const parityRatio = data?.parity_ratio || data?.parityRatio;
  const overallRate = data?.overall_positive_rate || data?.overallPositiveRate;

  const svgRef = useD3(
    (chart, { width, height: innerHeight }) => {
      if (!groups || groups.length === 0) return;

      // Scales
      const x = d3.scaleBand()
        .range([0, width])
        .domain(groups.map(d => d.name))
        .padding(barPadding);

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

      // Overall rate reference line
      if (overallRate !== undefined) {
        chart.append('line')
          .attr('x1', 0)
          .attr('x2', width)
          .attr('y1', y(overallRate))
          .attr('y2', y(overallRate))
          .attr('stroke', '#9333ea')
          .attr('stroke-width', 2)
          .attr('stroke-dasharray', '5,5');

        chart.append('text')
          .attr('x', width - 10)
          .attr('y', y(overallRate) - 5)
          .attr('text-anchor', 'end')
          .attr('class', 'text-xs fill-purple-600')
          .text(`Overall: ${(overallRate * 100).toFixed(1)}%`);
      }

      // Bars
      chart.selectAll('.bar')
        .data(groups)
        .enter()
        .append('rect')
        .attr('x', d => x(d.name))
        .attr('width', x.bandwidth())
        .attr('fill', COLORS.bar)
        .attr('rx', 4)
        .attr('y', innerHeight)
        .attr('height', 0)
        .transition()
        .duration(animationDuration)
        .attr('y', d => y(d.positiveRate))
        .attr('height', d => innerHeight - y(d.positiveRate));

      // Value labels
      chart.selectAll('.label')
        .data(groups)
        .enter()
        .append('text')
        .attr('x', d => x(d.name) + x.bandwidth() / 2)
        .attr('y', d => y(d.positiveRate) - 5)
        .attr('text-anchor', 'middle')
        .attr('class', 'text-sm font-medium fill-gray-700')
        .text(d => `${(d.positiveRate * 100).toFixed(1)}%`);
    },
    [groups, containerWidth],
    { containerWidth, height: 300, margin }
  );

  if (!data || Object.keys(groupStats).length === 0) {
    return (
      <div className="text-gray-500 italic text-center py-8">
        No fairness data available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Chart */}
      <div ref={containerRef} className="relative bg-white rounded-lg w-full">
        <svg ref={svgRef} className="w-full h-full" />
      </div>

      {/* Summary Metrics */}
      <div className="grid grid-cols-3 gap-4">
        {parityDiff !== undefined && (
          <div className="p-4 bg-white border border-gray-200 rounded-lg text-center">
            <div className="text-xs text-gray-500 uppercase">Parity Difference</div>
            <div className={`text-xl font-bold ${Math.abs(parityDiff) > 0.1 ? 'text-red-600' : 'text-green-600'}`}>
              {(parityDiff * 100).toFixed(2)}%
            </div>
            <div className="text-xs text-gray-400 mt-1">
              {Math.abs(parityDiff) > 0.1 ? 'Potential disparity' : 'Within acceptable range'}
            </div>
          </div>
        )}

        {parityRatio !== undefined && (
          <div className="p-4 bg-white border border-gray-200 rounded-lg text-center">
            <div className="text-xs text-gray-500 uppercase">Parity Ratio</div>
            <div className={`text-xl font-bold ${parityRatio < 0.8 || parityRatio > 1.25 ? 'text-red-600' : 'text-green-600'}`}>
              {parityRatio.toFixed(3)}
            </div>
            <div className="text-xs text-gray-400 mt-1">
              {parityRatio < 0.8 || parityRatio > 1.25 ? 'Outside 4/5 rule' : 'Within 4/5 rule'}
            </div>
          </div>
        )}

        {overallRate !== undefined && (
          <div className="p-4 bg-white border border-gray-200 rounded-lg text-center">
            <div className="text-xs text-gray-500 uppercase">Overall Positive Rate</div>
            <div className="text-xl font-bold text-purple-600">
              {formatPercentage(overallRate)}
            </div>
          </div>
        )}
      </div>

      {/* Group Details Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-gray-100">
              <th className="border border-gray-300 p-2 text-left">Group</th>
              <th className="border border-gray-300 p-2 text-center">Positive Rate</th>
              <th className="border border-gray-300 p-2 text-center">Sample Size</th>
              {groups[0]?.accuracy !== undefined && (
                <th className="border border-gray-300 p-2 text-center">Accuracy</th>
              )}
            </tr>
          </thead>
          <tbody>
            {groups.map(group => (
              <tr key={group.name} className="hover:bg-gray-50">
                <td className="border border-gray-300 p-2 font-medium">{group.name}</td>
                <td className="border border-gray-300 p-2 text-center">
                  {formatPercentage(group.positiveRate)}
                </td>
                <td className="border border-gray-300 p-2 text-center">
                  {formatCount(group.sampleSize)}
                </td>
                {group.accuracy !== undefined && (
                  <td className="border border-gray-300 p-2 text-center">
                    {formatPercentage(group.accuracy)}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default FairnessChart;
