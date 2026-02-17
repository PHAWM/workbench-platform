// Metric configuration for visualization
// Supports all workbench metric output formats

export const METRIC_CONFIGS = {
  // =====================================
  // 1. Classification Metrics
  // =====================================
  accuracy: {
    label: "Accuracy",
    unit: "%",
    domain: [0, 100],
    better: "higher",
    thresholdDefault: 5,
    valueMultiplier: 100, // Convert 0-1 to percentage
    chartType: "bar",
  },
  precision: {
    label: "Precision",
    unit: "%",
    domain: [0, 100],
    better: "higher",
    thresholdDefault: 5,
    valueMultiplier: 100,
    chartType: "bar",
  },
  recall: {
    label: "Recall",
    unit: "%",
    domain: [0, 100],
    better: "higher",
    thresholdDefault: 5,
    valueMultiplier: 100,
    chartType: "bar",
  },
  f1: {
    label: "F1 Score",
    unit: "%",
    domain: [0, 100],
    better: "higher",
    thresholdDefault: 5,
    valueMultiplier: 100,
    chartType: "bar",
  },
  fbeta: {
    label: "F-Beta Score",
    unit: "%",
    domain: [0, 100],
    better: "higher",
    thresholdDefault: 5,
    valueMultiplier: 100,
    chartType: "bar",
  },
  balanced_accuracy: {
    label: "Balanced Accuracy",
    unit: "%",
    domain: [0, 100],
    better: "higher",
    thresholdDefault: 5,
    valueMultiplier: 100,
    chartType: "bar",
  },
  mcc: {
    label: "Matthews Correlation Coefficient",
    unit: "",
    domain: [-1, 1],
    better: "higher",
    thresholdDefault: 0.1,
    valueMultiplier: 1,
    chartType: "bar",
  },
  cohen_kappa: {
    label: "Cohen's Kappa",
    unit: "",
    domain: [-1, 1],
    better: "higher",
    thresholdDefault: 0.1,
    valueMultiplier: 1,
    chartType: "bar",
  },
  hamming_loss: {
    label: "Hamming Loss",
    unit: "",
    domain: [0, 1],
    better: "lower",
    thresholdDefault: 0.1,
    valueMultiplier: 1,
    chartType: "bar",
  },
  jaccard: {
    label: "Jaccard Score",
    unit: "%",
    domain: [0, 100],
    better: "higher",
    thresholdDefault: 5,
    valueMultiplier: 100,
    chartType: "bar",
  },
  specificity: {
    label: "Specificity",
    unit: "%",
    domain: [0, 100],
    better: "higher",
    thresholdDefault: 5,
    valueMultiplier: 100,
    chartType: "bar",
  },

  // =====================================
  // 2. Fairness Metrics
  // =====================================
  demographic_parity: {
    label: "Demographic Parity",
    unit: "",
    domain: "auto",
    better: "closer_to_one",
    thresholdDefault: 0.1,
    valueMultiplier: 1,
    chartType: "grouped_bar",
  },
  statistical_parity: {
    label: "Statistical Parity",
    unit: "",
    domain: "auto",
    better: "closer_to_one",
    thresholdDefault: 0.1,
    valueMultiplier: 1,
    chartType: "grouped_bar",
  },
  equalized_odds: {
    label: "Equalized Odds",
    unit: "",
    domain: [0, 1],
    better: "lower",
    thresholdDefault: 0.1,
    valueMultiplier: 1,
    chartType: "bar",
  },
  equal_opportunity: {
    label: "Equal Opportunity",
    unit: "",
    domain: [0, 1],
    better: "lower",
    thresholdDefault: 0.1,
    valueMultiplier: 1,
    chartType: "bar",
  },
  disparate_impact: {
    label: "Disparate Impact",
    unit: "",
    domain: [0, 2],
    better: "closer_to_one",
    thresholdDefault: 0.8,
    valueMultiplier: 1,
    chartType: "bar",
    referenceLines: [
      { value: 0.8, label: "Lower bound", color: "#ef4444" },
      { value: 1.0, label: "Ideal", color: "#22c55e" },
      { value: 1.25, label: "Upper bound", color: "#ef4444" },
    ],
  },
  calibration: {
    label: "Calibration",
    unit: "",
    domain: [0, 1],
    better: "lower",
    thresholdDefault: 0.05,
    valueMultiplier: 1,
    chartType: "calibration_curve",
  },

  // =====================================
  // 3. Regression Metrics
  // =====================================
  mse: {
    label: "Mean Squared Error",
    unit: "",
    domain: "auto",
    better: "lower",
    thresholdDefault: 0.1,
    valueMultiplier: 1,
    chartType: "bar",
  },
  rmse: {
    label: "Root Mean Squared Error",
    unit: "",
    domain: "auto",
    better: "lower",
    thresholdDefault: 0.1,
    valueMultiplier: 1,
    chartType: "bar",
  },
  mae: {
    label: "Mean Absolute Error",
    unit: "",
    domain: "auto",
    better: "lower",
    thresholdDefault: 0.1,
    valueMultiplier: 1,
    chartType: "bar",
  },
  mape: {
    label: "Mean Absolute Percentage Error",
    unit: "%",
    domain: "auto",
    better: "lower",
    thresholdDefault: 10,
    valueMultiplier: 1,
    chartType: "bar",
  },
  r2: {
    label: "R² Score",
    unit: "",
    domain: [0, 1],
    better: "higher",
    thresholdDefault: 0.1,
    valueMultiplier: 1,
    chartType: "bar",
  },
  explained_variance: {
    label: "Explained Variance",
    unit: "",
    domain: [0, 1],
    better: "higher",
    thresholdDefault: 0.1,
    valueMultiplier: 1,
    chartType: "bar",
  },
  max_error: {
    label: "Max Error",
    unit: "",
    domain: "auto",
    better: "lower",
    thresholdDefault: 0.1,
    valueMultiplier: 1,
    chartType: "bar",
  },
  median_absolute_error: {
    label: "Median Absolute Error",
    unit: "",
    domain: "auto",
    better: "lower",
    thresholdDefault: 0.1,
    valueMultiplier: 1,
    chartType: "bar",
  },

  // =====================================
  // 4. Probability/Calibration Metrics
  // =====================================
  roc_auc: {
    label: "ROC AUC",
    unit: "",
    domain: [0, 1],
    better: "higher",
    thresholdDefault: 0.05,
    valueMultiplier: 1,
    chartType: "bar",
  },
  pr_auc: {
    label: "PR AUC",
    unit: "",
    domain: [0, 1],
    better: "higher",
    thresholdDefault: 0.05,
    valueMultiplier: 1,
    chartType: "bar",
  },
  average_precision: {
    label: "Average Precision",
    unit: "",
    domain: [0, 1],
    better: "higher",
    thresholdDefault: 0.05,
    valueMultiplier: 1,
    chartType: "bar",
  },
  log_loss: {
    label: "Log Loss",
    unit: "",
    domain: "auto",
    better: "lower",
    thresholdDefault: 0.1,
    valueMultiplier: 1,
    chartType: "bar",
  },
  cross_entropy: {
    label: "Cross Entropy",
    unit: "",
    domain: "auto",
    better: "lower",
    thresholdDefault: 0.1,
    valueMultiplier: 1,
    chartType: "bar",
  },
  brier_score: {
    label: "Brier Score",
    unit: "",
    domain: [0, 1],
    better: "lower",
    thresholdDefault: 0.1,
    valueMultiplier: 1,
    chartType: "bar",
  },
  ece: {
    label: "Expected Calibration Error",
    unit: "",
    domain: [0, 1],
    better: "lower",
    thresholdDefault: 0.05,
    valueMultiplier: 1,
    chartType: "bar",
  },
  expected_calibration_error: {
    label: "Expected Calibration Error",
    unit: "",
    domain: [0, 1],
    better: "lower",
    thresholdDefault: 0.05,
    valueMultiplier: 1,
    chartType: "bar",
  },

  // =====================================
  // 5. Ranking Metrics
  // =====================================
  ndcg: {
    label: "NDCG",
    unit: "",
    domain: [0, 1],
    better: "higher",
    thresholdDefault: 0.05,
    valueMultiplier: 1,
    chartType: "bar",
  },
  normalized_dcg: {
    label: "Normalized DCG",
    unit: "",
    domain: [0, 1],
    better: "higher",
    thresholdDefault: 0.05,
    valueMultiplier: 1,
    chartType: "bar",
  },
  top_k_accuracy: {
    label: "Top-K Accuracy",
    unit: "%",
    domain: [0, 100],
    better: "higher",
    thresholdDefault: 5,
    valueMultiplier: 100,
    chartType: "bar",
  },

  // =====================================
  // 6. Generative AI Metrics
  // =====================================
  bleu: {
    label: "BLEU Score",
    unit: "",
    domain: [0, 1],
    better: "higher",
    thresholdDefault: 0.05,
    valueMultiplier: 1,
    chartType: "bar",
  },
  rouge: {
    label: "ROUGE Score",
    unit: "",
    domain: [0, 1],
    better: "higher",
    thresholdDefault: 0.05,
    valueMultiplier: 1,
    chartType: "grouped_bar", // Has precision, recall, f1
  },
  perplexity: {
    label: "Perplexity",
    unit: "",
    domain: "auto",
    better: "lower",
    thresholdDefault: 10,
    valueMultiplier: 1,
    chartType: "bar",
  },

  // =====================================
  // 7. Keyword/Text Metrics (ANNIF) - treated as accuracy
  // =====================================
  keyword_accuracy: {
    label: "Keyword Accuracy",
    unit: "%",
    domain: [0, 100],
    better: "higher",
    thresholdDefault: 5,
    valueMultiplier: 100,
    chartType: "bar",
  },
  batch_keyword_accuracy: {
    label: "Batch Keyword Accuracy",
    unit: "%",
    domain: [0, 100],
    better: "higher",
    thresholdDefault: 5,
    valueMultiplier: 100,
    chartType: "bar",
  },

  // =====================================
  // 8. Complex/Summary Metrics
  // =====================================
  confusion_matrix_analysis: {
    label: "Confusion Matrix Analysis",
    unit: "",
    domain: "auto",
    better: null,
    thresholdDefault: null,
    valueMultiplier: 1,
    chartType: "confusion_matrix",
  },
  classification_report: {
    label: "Classification Report",
    unit: "",
    domain: "auto",
    better: null,
    thresholdDefault: null,
    valueMultiplier: 1,
    chartType: "table",
  },
  performance_summary: {
    label: "Performance Summary",
    unit: "",
    domain: "auto",
    better: null,
    thresholdDefault: null,
    valueMultiplier: 1,
    chartType: "summary_cards",
  },
  classification_summary: {
    label: "Classification Summary",
    unit: "",
    domain: "auto",
    better: null,
    thresholdDefault: null,
    valueMultiplier: 1,
    chartType: "summary_cards",
  },
  regression_summary: {
    label: "Regression Summary",
    unit: "",
    domain: "auto",
    better: null,
    thresholdDefault: null,
    valueMultiplier: 1,
    chartType: "summary_cards",
  },
};

// Get config for a metric type (with fallback to accuracy)
export const getMetricConfig = (metricType) => {
  if (!metricType) return METRIC_CONFIGS.accuracy;

  const normalizedType = metricType.toLowerCase().replace(/[\s-]/g, '_');
  return METRIC_CONFIGS[normalizedType] || METRIC_CONFIGS.accuracy;
};

// Get chart type for a metric
export const getChartType = (metricType) => {
  const config = getMetricConfig(metricType);
  return config.chartType || 'bar';
};

// Check if a metric value indicates "better" performance
export const isBetterValue = (value, compareValue, metricType) => {
  const config = getMetricConfig(metricType);
  switch (config.better) {
    case 'higher':
      return value >= compareValue;
    case 'lower':
      return value <= compareValue;
    case 'closer_to_one':
      return Math.abs(1 - value) <= Math.abs(1 - compareValue);
    default:
      return true;
  }
};

// Check if value meets threshold
export const meetsThreshold = (value, threshold, metricType) => {
  const config = getMetricConfig(metricType);
  const thresholdVal = threshold || config.thresholdDefault;

  switch (config.better) {
    case 'higher':
      return value >= thresholdVal;
    case 'lower':
      return value <= thresholdVal;
    case 'closer_to_one':
      return Math.abs(1 - value) <= thresholdVal;
    default:
      return true;
  }
};

// Determine output type from API response structure
export const detectOutputType = (output) => {
  if (!output || typeof output !== 'object') {
    return 'unknown';
  }

  // Check for error response
  if (output.status === 'cannot be calculated' || output.error) {
    return 'error';
  }

  // Confusion matrix analysis
  if (output.confusion_matrix && output.true_positives !== undefined) {
    return 'confusion_matrix_analysis';
  }

  // Simple confusion matrix (nested array)
  if (output.confusion_matrix && Array.isArray(output.confusion_matrix)) {
    return 'confusion_matrix';
  }

  // Classification report
  if (output['0'] && output['1'] && output.accuracy !== undefined) {
    return 'classification_report';
  }

  // Performance/Classification summary
  if (output.accuracy !== undefined && output.precision !== undefined &&
      output.recall !== undefined && output.f1 !== undefined) {
    return 'performance_summary';
  }

  // Regression summary
  if (output.mse !== undefined && output.rmse !== undefined &&
      output.mae !== undefined && output.r2 !== undefined) {
    return 'regression_summary';
  }

  // Demographic parity / statistical parity
  if (output.group_statistics && output.parity_difference !== undefined) {
    return 'demographic_parity';
  }

  // Calibration
  if (output.bin_statistics || output.average_calibration_error !== undefined) {
    return 'calibration';
  }

  // ROUGE score
  if (output.precision !== undefined && output.recall !== undefined &&
      output.f1 !== undefined && Object.keys(output).length === 3) {
    return 'rouge';
  }

  // Keyword accuracy
  if (output.value !== undefined && output.matched_keywords !== undefined) {
    return 'keyword_accuracy';
  }

  // Batch keyword accuracy
  if (output.overall_accuracy !== undefined && output.documents_evaluated !== undefined) {
    return 'batch_keyword_accuracy';
  }

  // Grouped data (underlying_features structure)
  if (output.underlying_features) {
    return 'grouped_comparison';
  }

  // Simple numeric value
  if (typeof output === 'number') {
    return 'single_value';
  }

  return 'unknown';
};

export const DEFAULT_METRIC_TYPE = 'accuracy';

export const CHART_DEFAULTS = {
  height: 500,
  margin: { top: 10, right: 20, bottom: 50, left: 50 },
  barPadding: 0.4,
  barCornerRadius: 4,
  animationDuration: 800,
};
