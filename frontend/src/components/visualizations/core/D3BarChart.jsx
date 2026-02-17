import React, { useRef } from 'react';
import * as d3 from 'd3';
import { useD3 } from '../hooks/useD3';
import { useResizeObserver } from '../hooks/useResizeObserver';
import { getMetricConfig, CHART_DEFAULTS } from '../configs/metricConfigs';
import { getAxisFormatter, formatValue } from '../utils/axisFormatters';
import { COLORS, THRESHOLD_COLORS } from '../utils/colorScales';

function renderThreshold(chart, { data, isSingleBar, thresholdVal, y, x, width, metricType }) {
  const config = getMetricConfig(metricType);
  const unit = config.unit;

  if (isSingleBar) {
    const yPos = y(thresholdVal);
    const group = chart.append('g');

    group.append('line')
      .attr('x1', 0)
      .attr('x2', width)
      .attr('y1', yPos)
      .attr('y2', yPos)
      .attr('stroke', THRESHOLD_COLORS.line)
      .attr('stroke-width', THRESHOLD_COLORS.lineWidth)
      .attr('stroke-dasharray', THRESHOLD_COLORS.dashArray);

    group.append('text')
      .attr('x', width - 150)
      .attr('y', yPos - 4)
      .attr('fill', THRESHOLD_COLORS.line)
      .attr('class', THRESHOLD_COLORS.labelClass)
      .text(`Threshold: ${thresholdVal.toFixed(1)}${unit}`);
  } else {
    for (let i = 0; i < data.length - 1; i++) {
      const barRight = x(data[i].name) + x.bandwidth();
      const barLeftNext = x(data[i + 1].name);
      const midX = (barRight + barLeftNext) / 2;

      const lowerBarValue = Math.min(data[i].value, data[i + 1].value);
      const thresholdPosition = Math.min(lowerBarValue + thresholdVal, 100);
      const yPos = y(thresholdPosition);
      const lowerBoundYPos = y(lowerBarValue);

      const group = chart.append('g');

      // Shaded region between the two threshold lines
      group.append('rect')
        .attr('x', 0)
        .attr('y', yPos)
        .attr('width', width)
        .attr('height', lowerBoundYPos - yPos)
        .attr('fill', THRESHOLD_COLORS.shadeFill)
        .attr('opacity', THRESHOLD_COLORS.shadeOpacity)
        .attr('rx', 4);

      // Upper threshold line (lower bar + threshold)
      group.append('line')
        .attr('x1', 0)
        .attr('x2', width)
        .attr('y1', yPos)
        .attr('y2', yPos)
        .attr('stroke', THRESHOLD_COLORS.line)
        .attr('stroke-width', THRESHOLD_COLORS.lineWidth)
        .attr('stroke-dasharray', THRESHOLD_COLORS.dashArray);

      // Lower bound line at the lower bar value
      group.append('line')
        .attr('x1', 0)
        .attr('x2', width)
        .attr('y1', lowerBoundYPos)
        .attr('y2', lowerBoundYPos)
        .attr('stroke', THRESHOLD_COLORS.line)
        .attr('stroke-width', THRESHOLD_COLORS.lineWidth)
        .attr('stroke-dasharray', THRESHOLD_COLORS.dashArray);

      // Label only once (on the first gap)
      if (i === 0) {
        group.append('text')
          .attr('x', midX)
          .attr('y', yPos - 16)
          .attr('fill', THRESHOLD_COLORS.line)
          .attr('text-anchor', 'middle')
          .attr('class', THRESHOLD_COLORS.labelClass)
          .text(`Threshold: ${thresholdVal.toFixed(1)}${unit}`);
      }
    }
  }
}

const D3BarChart = ({ data, threshold, metricType = 'accuracy' }) => {
  const tooltipRef = useRef();
  const { containerRef, width: containerWidth } = useResizeObserver();

  const config = getMetricConfig(metricType);
  const { height, margin, barPadding, barCornerRadius, animationDuration } = CHART_DEFAULTS;
  const tickFormatter = getAxisFormatter(metricType);

  const yDomain = config.domain === 'auto'
    ? [0, d3.max(data || [], d => d.value) * 1.1]
    : config.domain;

  const svgRef = useD3(
    (chart, { width, height: innerHeight }) => {
      if (!data || data.length === 0) return;

      const thresholdVal = parseFloat(threshold) || config.thresholdDefault;
      const isSingleBar = data.length === 1;

      // --- Scales ---
      const x = d3.scaleBand()
        .range([0, width])
        .domain(data.map(d => d.name))
        .padding(barPadding);

      const y = d3.scaleLinear()
        .range([innerHeight, 0])
        .domain(yDomain);

      // --- Tooltip ---
      const tooltip = d3.select(tooltipRef.current);

      // --- Axes ---
      chart.append('g')
        .attr('transform', `translate(0,${innerHeight})`)
        .call(d3.axisBottom(x).tickSizeOuter(0))
        .attr('class', 'text-gray-500 text-base font-sans')
        .selectAll('text');

      chart.append('g')
        .call(d3.axisLeft(y).ticks(5).tickFormat(tickFormatter))
        .attr('class', 'text-gray-500 text-base font-sans')
        .selectAll('text');

      // --- Bars ---
      chart.selectAll('.bar')
        .data(data)
        .enter()
        .append('rect')
        .attr('x', d => x(d.name))
        .attr('width', x.bandwidth())
        .attr('fill', COLORS.bar)
        .attr('rx', barCornerRadius)
        .attr('y', innerHeight)
        .attr('height', 0)
        .on('mouseover', (event, d) => {
          tooltip.style('opacity', 1).html(`
            <div class="font-bold">${d.name}</div>
            <div class="text-base">${formatValue(d.value, metricType)}</div>
          `);
        })
        .on('mousemove', (event) => {
          tooltip
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY - 20) + 'px');
        })
        .on('mouseout', () => tooltip.style('opacity', 0))
        .transition()
        .duration(animationDuration)
        .attr('y', d => y(d.value))
        .attr('height', d => innerHeight - y(d.value));

      // --- Threshold ---
      renderThreshold(chart, {
        data, isSingleBar, thresholdVal, y, x, width, metricType,
      });
    },
    [data, threshold, containerWidth],
    { containerWidth, height, margin }
  );

  return (
    <div ref={containerRef} className="relative bg-white rounded-lg w-full">
      <svg ref={svgRef} className="w-full h-full" />
      <div
        ref={tooltipRef}
        className="fixed pointer-events-none opacity-0 bg-gray-900 text-white p-3 rounded text-sm z-50 transition-opacity"
      />
    </div>
  );
};

export default D3BarChart;
