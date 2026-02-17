// Main visualization component (auto-selects visualization type)
export { default as MetricVisualization } from './MetricVisualization';

// Core chart components
export { default as D3BarChart } from './core/D3BarChart';
export { default as D3LineChart } from './core/D3LineChart';
export { default as ConfusionMatrixChart } from './core/ConfusionMatrixChart';
export { default as ClassificationReportTable } from './core/ClassificationReportTable';
export { default as MetricSummaryCards } from './core/MetricSummaryCards';
export { default as FairnessChart } from './core/FairnessChart';
export { default as RougeScoreChart } from './core/RougeScoreChart';

// Hooks
export { useD3 } from './hooks/useD3';
export { useResizeObserver } from './hooks/useResizeObserver';

// Utilities
export {
  getAxisFormatter,
  formatValue,
  formatObjectValue,
  formatKeyLabel,
  compactFormatter,
  formatPercentage,
  formatCount,
  formatThreshold,
  getValueColor,
  parseMetricOutput,
} from './utils/axisFormatters';

export { COLORS, THRESHOLD_COLORS } from './utils/colorScales';

// Configs
export {
  METRIC_CONFIGS,
  getMetricConfig,
  getChartType,
  isBetterValue,
  meetsThreshold,
  detectOutputType,
  DEFAULT_METRIC_TYPE,
  CHART_DEFAULTS,
} from './configs/metricConfigs';
