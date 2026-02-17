import React from 'react';
import D3BarChart from './core/D3BarChart';
import ConfusionMatrixChart from './core/ConfusionMatrixChart';
import ClassificationReportTable from './core/ClassificationReportTable';
import MetricSummaryCards from './core/MetricSummaryCards';
import FairnessChart from './core/FairnessChart';
import RougeScoreChart from './core/RougeScoreChart';
import { detectOutputType, getMetricConfig } from './configs/metricConfigs';
import { formatValue, formatKeyLabel } from './utils/axisFormatters';

// Unified metric visualization component
// Automatically detects output type and renders appropriate visualization
const MetricVisualization = ({
  output,
  metricType,
  threshold,
  targetFeature,
  chartData, // Pre-processed chart data (for backwards compatibility)
  showTitle = true,
  title = null,
}) => {
  // If no output, show placeholder
  if (!output && (!chartData || chartData.length === 0)) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-center">
        <div className="text-5xl mb-4">📊</div>
        <p className="text-lg font-medium text-gray-700 mb-2">No Data Available</p>
        <p className="text-sm text-gray-500">Metric output data is not available for visualization.</p>
      </div>
    );
  }

  // Detect output type
  const outputType = detectOutputType(output);
  // Use targetFeature to get the right config if available, otherwise fall back to metricType
  const effectiveMetricType = targetFeature?.toLowerCase().replace(/\s+/g, '_') || metricType;
  const config = getMetricConfig(effectiveMetricType);

  // Handle error responses
  if (outputType === 'error' || output?.status === 'cannot be calculated') {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-center">
        <div className="text-5xl mb-4">⚠️</div>
        <p className="text-lg font-medium text-gray-700 mb-2">Unable to Calculate Metric</p>
        <p className="text-sm text-gray-500">
          {output?.error || 'Sorry, we cannot calculate the metric right now.'}
        </p>
        {output?.error_type && (
          <p className="text-xs text-gray-400 mt-2">Error type: {output.error_type}</p>
        )}
      </div>
    );
  }

  // Render title if enabled
  const renderTitle = () => {
    if (!showTitle) return null;
    // Use targetFeature for title if available, as it indicates the specific metric being visualized
    const displayTitle = title || (targetFeature ? formatKeyLabel(targetFeature) : null) || config.label || formatKeyLabel(metricType || 'Metric');
    return (
      <h3 className="text-lg font-semibold text-gray-800 mb-4">{displayTitle}</h3>
    );
  };

  // Select visualization based on output type
  const renderVisualization = () => {
    switch (outputType) {
      case 'confusion_matrix_analysis':
      case 'confusion_matrix':
        return <ConfusionMatrixChart data={output} showMetrics={true} />;

      case 'classification_report':
        return <ClassificationReportTable data={output} />;

      case 'performance_summary':
      case 'classification_summary':
        return (
          <MetricSummaryCards
            data={{
              accuracy: output.accuracy,
              precision: output.precision,
              recall: output.recall,
              f1: output.f1,
              balanced_accuracy: output.balanced_accuracy,
              mcc: output.mcc,
              roc_auc: output.roc_auc,
              pr_auc: output.pr_auc,
              log_loss: output.log_loss,
            }}
            threshold={threshold}
            highlightKey={targetFeature?.toLowerCase().replace(/\s+/g, '_')}
          />
        );

      case 'regression_summary':
        return (
          <MetricSummaryCards
            data={{
              mse: output.mse,
              rmse: output.rmse,
              mae: output.mae,
              r2: output.r2,
              explained_variance: output.explained_variance,
              max_error: output.max_error,
              median_absolute_error: output.median_absolute_error,
            }}
            threshold={threshold}
          />
        );

      case 'demographic_parity':
      case 'statistical_parity':
        return <FairnessChart data={output} metricType={metricType} />;

      case 'calibration':
        // TODO: Add dedicated calibration curve component
        return (
          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-600 mb-2">Calibration Data:</p>
            <pre className="text-xs overflow-auto max-h-64">
              {JSON.stringify(output, null, 2)}
            </pre>
          </div>
        );

      case 'rouge':
        return <RougeScoreChart data={output} threshold={threshold} />;

      case 'single_value':
      case 'keyword_accuracy':
      case 'batch_keyword_accuracy':
        // Single numeric value - show as a card
        const value = typeof output === 'number' ? output : output.value;
        return (
          <div className="p-6 bg-purple-50 border-2 border-purple-200 rounded-xl text-center">
            <div className="text-sm text-gray-600 uppercase tracking-wide">
              {config.label || 'Value'}
            </div>
            <div className="text-4xl font-bold text-purple-700">
              {formatValue(value * (config.valueMultiplier || 1), metricType)}
            </div>
            {threshold && (
              <div className="text-sm text-gray-500 mt-2">
                Threshold: {threshold}{config.unit}
              </div>
            )}
          </div>
        );

      case 'grouped_comparison':
        // Check if this is grouped confusion matrices (target_feature = "Confusion Matrix")
        if (targetFeature?.toLowerCase().includes('confusion')) {
          const groupedMatrices = extractGroupedConfusionMatrices(output.underlying_features);
          if (groupedMatrices.length > 0) {
            return (
              <div className="space-y-6">
                {groupedMatrices.map((group, idx) => (
                  <div key={idx} className="border border-gray-200 rounded-lg p-4">
                    <h4 className="text-md font-semibold text-gray-700 mb-3">{group.name}</h4>
                    <ConfusionMatrixChart data={group.matrix} showMetrics={true} />
                  </div>
                ))}
              </div>
            );
          }
        }
        // Use bar chart for grouped data (backwards compatible with existing implementation)
        if (chartData && chartData.length > 0) {
          return <D3BarChart data={chartData} threshold={threshold} metricType={effectiveMetricType} />;
        }
        // Process underlying_features into chart data
        const processedData = processGroupedData(output.underlying_features, targetFeature, config);
        if (processedData.length > 0) {
          return <D3BarChart data={processedData} threshold={threshold} metricType={effectiveMetricType} />;
        }
        return renderRawOutput();

      default:
        // For pre-processed chart data (backwards compatibility)
        if (chartData && chartData.length > 0) {
          return <D3BarChart data={chartData} threshold={threshold} metricType={effectiveMetricType} />;
        }
        // Render raw output as fallback
        return renderRawOutput();
    }
  };

  // Render raw output as JSON (fallback)
  const renderRawOutput = () => (
    <div className="p-4 bg-gray-50 rounded-lg">
      <p className="text-sm text-gray-600 mb-2">Raw Output Data:</p>
      <pre className="text-xs overflow-auto max-h-64 bg-white p-2 rounded border">
        {JSON.stringify(output, null, 2)}
      </pre>
    </div>
  );

  return (
    <div className="bg-white border border-purple-200 rounded-2xl p-4 shadow-sm">
      {renderTitle()}
      {renderVisualization()}
    </div>
  );
};

// Helper function to extract grouped confusion matrices from underlying_features
const extractGroupedConfusionMatrices = (underlyingFeatures) => {
  if (!underlyingFeatures) return [];

  const matrices = [];
  const featureKeys = Object.keys(underlyingFeatures);

  featureKeys.forEach(featureKey => {
    const featureData = underlyingFeatures[featureKey];
    const groupsData = featureData.overall || featureData;

    if (groupsData && typeof groupsData === 'object') {
      Object.keys(groupsData).forEach(groupName => {
        const groupData = groupsData[groupName];

        // Check if groupData is a confusion matrix (2D array [[TN, FP], [FN, TP]])
        if (Array.isArray(groupData) && groupData.length === 2 &&
            Array.isArray(groupData[0]) && Array.isArray(groupData[1])) {
          const [[TN, FP], [FN, TP]] = groupData;

          const displayName = featureKeys.length > 1
            ? `${featureKey} - ${groupName}`
            : groupName;

          matrices.push({
            name: displayName,
            matrix: {
              confusion_matrix: groupData,
              true_positives: TP,
              true_negatives: TN,
              false_positives: FP,
              false_negatives: FN,
            },
          });
        }
      });
    }
  });

  return matrices;
};

// Helper function to process grouped/underlying_features data into chart format
const processGroupedData = (underlyingFeatures, targetFeature, config) => {
  if (!underlyingFeatures) return [];

  const chartData = [];
  const featureKeys = Object.keys(underlyingFeatures);

  featureKeys.forEach(featureKey => {
    const featureData = underlyingFeatures[featureKey];
    const groupsData = featureData.overall || featureData;

    if (groupsData && typeof groupsData === 'object') {
      Object.keys(groupsData).forEach(groupName => {
        const groupData = groupsData[groupName];
        let value = 0;

        if (typeof groupData === 'number') {
          value = groupData * (config.valueMultiplier || 100);
        } else if (typeof groupData === 'object' && groupData !== null) {
          // Try to find target feature value
          const targetKey = targetFeature?.toLowerCase().replace(/\s+/g, '_');
          if (targetKey && groupData[targetKey] !== undefined) {
            value = groupData[targetKey] * (config.valueMultiplier || 100);
          } else if (groupData.accuracy !== undefined) {
            value = groupData.accuracy * (config.valueMultiplier || 100);
          } else {
            // Use first numeric value
            const firstNumeric = Object.values(groupData).find(v => typeof v === 'number');
            if (firstNumeric !== undefined) {
              value = firstNumeric * (config.valueMultiplier || 100);
            }
          }
        }

        const displayName = featureKeys.length > 1
          ? `${featureKey} ${groupName.charAt(0).toUpperCase() + groupName.slice(1)}`
          : groupName.charAt(0).toUpperCase() + groupName.slice(1);

        chartData.push({
          name: displayName,
          value: parseFloat(value.toFixed(2)),
        });
      });
    }
  });

  return chartData;
};

export default MetricVisualization;
