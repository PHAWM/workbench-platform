import { getMetricConfig } from '../configs/metricConfigs';

// Get appropriate axis tick formatter based on metric type
export const getAxisFormatter = (metricType) => {
  const config = getMetricConfig(metricType);

  switch (config.unit) {
    case '%':
      return (d) => `${d}%`;
    case 'ms':
      return (d) => `${d}ms`;
    default:
      // For values between -1 and 1, show 2 decimal places
      return (d) => {
        if (Math.abs(d) < 10 && d !== Math.floor(d)) {
          return d.toFixed(2);
        }
        return d.toLocaleString();
      };
  }
};

// Format a single metric value for display (tooltips, labels)
export const formatValue = (value, metricType) => {
  if (value === null || value === undefined) {
    return 'N/A';
  }

  const config = getMetricConfig(metricType);

  // Handle object values (like ROUGE scores with precision/recall/f1)
  if (typeof value === 'object') {
    return formatObjectValue(value);
  }

  // Handle numeric values
  if (typeof value === 'number') {
    if (config.unit === '%') {
      return `${value.toFixed(1)}%`;
    }
    // For small values (correlation coefficients, etc.), show more precision
    if (Math.abs(value) < 1 && value !== 0) {
      return value.toFixed(3);
    }
    // For larger values
    if (Math.abs(value) >= 1000) {
      return compactFormatter(value);
    }
    return value.toFixed(2);
  }

  return String(value);
};

// Format object values (like ROUGE, performance summaries)
export const formatObjectValue = (obj) => {
  if (!obj || typeof obj !== 'object') return 'N/A';

  const entries = Object.entries(obj)
    .filter(([_, v]) => typeof v === 'number')
    .map(([k, v]) => `${formatKeyLabel(k)}: ${v.toFixed(3)}`)
    .slice(0, 5); // Limit to 5 entries for display

  return entries.join(', ');
};

// Format key names for display (snake_case to Title Case)
export const formatKeyLabel = (key) => {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
};

// Compact number formatter for large values
export const compactFormatter = (d) => {
  if (d >= 1_000_000) return `${(d / 1_000_000).toFixed(1)}M`;
  if (d >= 1_000) return `${(d / 1_000).toFixed(1)}k`;
  if (d <= -1_000_000) return `${(d / 1_000_000).toFixed(1)}M`;
  if (d <= -1_000) return `${(d / 1_000).toFixed(1)}k`;
  return d.toString();
};

// Format percentage (handles both 0-1 and 0-100 ranges)
export const formatPercentage = (value, isDecimal = true) => {
  if (value === null || value === undefined) return 'N/A';
  const pct = isDecimal ? value * 100 : value;
  return `${pct.toFixed(1)}%`;
};

// Format confusion matrix counts
export const formatCount = (value) => {
  if (value === null || value === undefined) return '0';
  return value.toLocaleString();
};

// Format threshold value for display
export const formatThreshold = (threshold, metricType) => {
  if (threshold === null || threshold === undefined || threshold === '') {
    return 'Not set';
  }

  const config = getMetricConfig(metricType);

  if (typeof threshold === 'number') {
    return `${threshold}${config.unit}`;
  }

  // If threshold is a string, try to parse and format
  const parsed = parseFloat(threshold);
  if (!isNaN(parsed)) {
    return `${parsed}${config.unit}`;
  }

  return threshold;
};

// Get value color based on whether it meets threshold
export const getValueColor = (value, threshold, metricType) => {
  const config = getMetricConfig(metricType);

  if (value === null || value === undefined) return '#6b7280'; // gray

  const thresholdVal = threshold || config.thresholdDefault;

  let meetsThreshold = false;
  switch (config.better) {
    case 'higher':
      meetsThreshold = value >= thresholdVal;
      break;
    case 'lower':
      meetsThreshold = value <= thresholdVal;
      break;
    case 'closer_to_one':
      meetsThreshold = Math.abs(1 - value) <= thresholdVal;
      break;
    default:
      return '#6b7280';
  }

  return meetsThreshold ? '#22c55e' : '#ef4444'; // green or red
};

// Parse metric output and extract displayable values
export const parseMetricOutput = (output, metricType) => {
  if (!output) return null;

  // Handle error responses
  if (output.status === 'cannot be calculated' || output.error) {
    return {
      type: 'error',
      error: output.error || 'Unable to calculate metric',
      errorType: output.error_type,
      metricName: output.metric_name,
    };
  }

  // Handle single numeric values
  if (typeof output === 'number') {
    const config = getMetricConfig(metricType);
    return {
      type: 'single_value',
      value: output * (config.valueMultiplier || 1),
      formatted: formatValue(output * (config.valueMultiplier || 1), metricType),
    };
  }

  // Handle object outputs - detect type and extract values
  if (typeof output === 'object') {
    return parseObjectOutput(output);
  }

  return null;
};

// Parse object-type metric outputs
const parseObjectOutput = (output) => {
  // Confusion matrix analysis
  if (output.confusion_matrix !== undefined && output.true_positives !== undefined) {
    return {
      type: 'confusion_matrix_analysis',
      confusionMatrix: output.confusion_matrix,
      truePositives: output.true_positives,
      trueNegatives: output.true_negatives,
      falsePositives: output.false_positives,
      falseNegatives: output.false_negatives,
      accuracy: output.accuracy,
      precision: output.precision,
      recall: output.recall,
      specificity: output.specificity,
      falsePositiveRate: output.false_positive_rate,
      falseNegativeRate: output.false_negative_rate,
    };
  }

  // Classification report
  if (output['0'] && output['1'] && output.accuracy !== undefined) {
    return {
      type: 'classification_report',
      classes: Object.keys(output).filter(k => !['accuracy', 'macro avg', 'weighted avg'].includes(k)),
      accuracy: output.accuracy,
      macroAvg: output['macro avg'],
      weightedAvg: output['weighted avg'],
      classReports: output,
    };
  }

  // Performance/Classification summary
  if (output.accuracy !== undefined && output.f1 !== undefined) {
    return {
      type: 'performance_summary',
      metrics: {
        accuracy: output.accuracy,
        precision: output.precision,
        recall: output.recall,
        f1: output.f1,
        balancedAccuracy: output.balanced_accuracy,
        mcc: output.mcc,
        rocAuc: output.roc_auc,
        prAuc: output.pr_auc,
        logLoss: output.log_loss,
      },
    };
  }

  // Regression summary
  if (output.mse !== undefined && output.r2 !== undefined) {
    return {
      type: 'regression_summary',
      metrics: {
        mse: output.mse,
        rmse: output.rmse,
        mae: output.mae,
        r2: output.r2,
        explainedVariance: output.explained_variance,
        maxError: output.max_error,
        medianAbsoluteError: output.median_absolute_error,
      },
    };
  }

  // Demographic parity
  if (output.group_statistics) {
    return {
      type: 'demographic_parity',
      groupStatistics: output.group_statistics,
      parityDifference: output.parity_difference,
      parityRatio: output.parity_ratio,
      overallPositiveRate: output.overall_positive_rate,
      overallAccuracy: output.overall_accuracy,
    };
  }

  // Calibration
  if (output.bin_statistics || (typeof output === 'object' && Object.values(output)[0]?.bin_statistics)) {
    return {
      type: 'calibration',
      data: output,
    };
  }

  // ROUGE score
  if (output.precision !== undefined && output.recall !== undefined && output.f1 !== undefined) {
    return {
      type: 'rouge',
      precision: output.precision,
      recall: output.recall,
      f1: output.f1,
    };
  }

  // Keyword accuracy
  if (output.value !== undefined && output.matched_keywords !== undefined) {
    return {
      type: 'keyword_accuracy',
      value: output.value,
      accuracy: output.accuracy,
      precision: output.precision,
      f1Score: output.f1_score,
      matchedCount: output.matched_count,
      expectedCount: output.expected_count,
      predictedCount: output.predicted_count,
      matchedKeywords: output.matched_keywords,
    };
  }

  // Batch keyword accuracy
  if (output.overall_accuracy !== undefined && output.documents_evaluated !== undefined) {
    return {
      type: 'batch_keyword_accuracy',
      value: output.value,
      overallAccuracy: output.overall_accuracy,
      overallPrecision: output.overall_precision,
      overallF1Score: output.overall_f1_score,
      averageDocumentAccuracy: output.average_document_accuracy,
      totalMatchedKeywords: output.total_matched_keywords,
      totalExpectedKeywords: output.total_expected_keywords,
      totalPredictedKeywords: output.total_predicted_keywords,
      documentsEvaluated: output.documents_evaluated,
    };
  }

  // Underlying features (grouped comparison)
  if (output.underlying_features) {
    return {
      type: 'grouped_comparison',
      underlyingFeatures: output.underlying_features,
    };
  }

  // Default - return raw object
  return {
    type: 'raw',
    data: output,
  };
};
