import React from 'react';
import { formatValue, formatKeyLabel } from '../utils/axisFormatters';
import { getMetricConfig, meetsThreshold } from '../configs/metricConfigs';

// Display a summary of multiple metrics as cards
const MetricSummaryCards = ({ data, threshold, highlightKey = null }) => {
  if (!data || typeof data !== 'object') {
    return (
      <div className="text-gray-500 italic text-center py-8">
        No summary data available
      </div>
    );
  }

  // Filter out null/undefined values and get displayable metrics
  const metrics = Object.entries(data)
    .filter(([_, value]) => value !== null && value !== undefined && typeof value === 'number')
    .map(([key, value]) => {
      const config = getMetricConfig(key);
      const passes = threshold ? meetsThreshold(value, threshold, key) : null;

      return {
        key,
        label: formatKeyLabel(key),
        value,
        formatted: formatValue(value, key),
        unit: config.unit,
        passes,
        isHighlighted: key === highlightKey,
      };
    });

  if (metrics.length === 0) {
    return (
      <div className="text-gray-500 italic text-center py-8">
        No metrics to display
      </div>
    );
  }

  // Determine grid columns based on number of metrics
  const gridCols = metrics.length <= 3 ? 'grid-cols-3' :
                   metrics.length <= 4 ? 'grid-cols-4' :
                   'grid-cols-4';

  return (
    <div className={`grid ${gridCols} gap-4`}>
      {metrics.map(({ key, label, value, formatted, passes, isHighlighted }) => (
        <div
          key={key}
          className={`p-4 rounded-xl border-2 transition-all ${
            isHighlighted
              ? 'border-purple-400 bg-purple-50 shadow-md'
              : passes === true
                ? 'border-green-200 bg-green-50'
                : passes === false
                  ? 'border-red-200 bg-red-50'
                  : 'border-gray-200 bg-white'
          }`}
        >
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
            {label}
          </div>
          <div className={`text-2xl font-bold ${
            passes === true ? 'text-green-700' :
            passes === false ? 'text-red-700' :
            'text-gray-800'
          }`}>
            {formatted}
          </div>
          {passes !== null && (
            <div className={`text-xs mt-1 ${passes ? 'text-green-600' : 'text-red-600'}`}>
              {passes ? '✓ Meets threshold' : '✗ Below threshold'}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

export default MetricSummaryCards;
