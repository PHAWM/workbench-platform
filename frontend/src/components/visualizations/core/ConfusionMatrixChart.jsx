import React from 'react';
import { formatCount, formatPercentage } from '../utils/axisFormatters';

// Confusion Matrix visualization component
const ConfusionMatrixChart = ({ data, showMetrics = true }) => {
  if (!data) {
    return (
      <div className="text-gray-500 italic text-center py-8">
        No confusion matrix data available
      </div>
    );
  }

  // Extract values - support both object format and array format
  let TP, TN, FP, FN;

  if (Array.isArray(data.confusion_matrix)) {
    // Array format: [[TN, FP], [FN, TP]]
    const matrix = data.confusion_matrix;
    TN = matrix[0]?.[0] || 0;
    FP = matrix[0]?.[1] || 0;
    FN = matrix[1]?.[0] || 0;
    TP = matrix[1]?.[1] || 0;
  } else if (data.confusion_matrix) {
    // Object format with TP, TN, FP, FN keys
    TP = data.confusion_matrix.TP || data.true_positives || 0;
    TN = data.confusion_matrix.TN || data.true_negatives || 0;
    FP = data.confusion_matrix.FP || data.false_positives || 0;
    FN = data.confusion_matrix.FN || data.false_negatives || 0;
  } else {
    // Direct object format
    TP = data.true_positives || data.TP || 0;
    TN = data.true_negatives || data.TN || 0;
    FP = data.false_positives || data.FP || 0;
    FN = data.false_negatives || data.FN || 0;
  }

  const total = TP + TN + FP + FN;

  // Calculate derived metrics if not provided
  const accuracy = data.accuracy ?? (total > 0 ? (TP + TN) / total : 0);
  const precision = data.precision ?? (TP + FP > 0 ? TP / (TP + FP) : 0);
  const recall = data.recall ?? (TP + FN > 0 ? TP / (TP + FN) : 0);
  const specificity = data.specificity ?? (TN + FP > 0 ? TN / (TN + FP) : 0);
  const fpr = data.false_positive_rate ?? (FP + TN > 0 ? FP / (FP + TN) : 0);
  const fnr = data.false_negative_rate ?? (FN + TP > 0 ? FN / (FN + TP) : 0);

  return (
    <div className="space-y-6">
      {/* Confusion Matrix Grid */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-green-50 border-2 border-green-200 rounded-lg p-4 text-center">
          <div className="text-xs font-medium text-gray-600 mb-2">True Positive (TP)</div>
          <div className="text-3xl font-bold text-green-700">{formatCount(TP)}</div>
          {total > 0 && (
            <div className="text-xs text-green-600 mt-1">{formatPercentage(TP / total, false)}</div>
          )}
        </div>
        <div className="bg-red-50 border-2 border-red-200 rounded-lg p-4 text-center">
          <div className="text-xs font-medium text-gray-600 mb-2">False Positive (FP)</div>
          <div className="text-3xl font-bold text-red-700">{formatCount(FP)}</div>
          {total > 0 && (
            <div className="text-xs text-red-600 mt-1">{formatPercentage(FP / total, false)}</div>
          )}
        </div>
        <div className="bg-orange-50 border-2 border-orange-200 rounded-lg p-4 text-center">
          <div className="text-xs font-medium text-gray-600 mb-2">False Negative (FN)</div>
          <div className="text-3xl font-bold text-orange-700">{formatCount(FN)}</div>
          {total > 0 && (
            <div className="text-xs text-orange-600 mt-1">{formatPercentage(FN / total, false)}</div>
          )}
        </div>
        <div className="bg-blue-50 border-2 border-blue-200 rounded-lg p-4 text-center">
          <div className="text-xs font-medium text-gray-600 mb-2">True Negative (TN)</div>
          <div className="text-3xl font-bold text-blue-700">{formatCount(TN)}</div>
          {total > 0 && (
            <div className="text-xs text-blue-600 mt-1">{formatPercentage(TN / total, false)}</div>
          )}
        </div>
      </div>

      {/* Matrix Table View */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="border border-gray-300 p-2"></th>
              <th className="border border-gray-300 p-2 bg-purple-100 font-medium">Predicted Positive</th>
              <th className="border border-gray-300 p-2 bg-purple-100 font-medium">Predicted Negative</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="border border-gray-300 p-2 bg-purple-100 font-medium">Actual Positive</td>
              <td className="border border-gray-300 p-3 text-center bg-green-50 font-semibold text-green-700">
                {formatCount(TP)}
              </td>
              <td className="border border-gray-300 p-3 text-center bg-orange-50 font-semibold text-orange-700">
                {formatCount(FN)}
              </td>
            </tr>
            <tr>
              <td className="border border-gray-300 p-2 bg-purple-100 font-medium">Actual Negative</td>
              <td className="border border-gray-300 p-3 text-center bg-red-50 font-semibold text-red-700">
                {formatCount(FP)}
              </td>
              <td className="border border-gray-300 p-3 text-center bg-blue-50 font-semibold text-blue-700">
                {formatCount(TN)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Derived Metrics */}
      {showMetrics && (
        <div className="grid grid-cols-3 gap-3">
          <div className="p-3 bg-white border border-gray-200 rounded-lg text-center">
            <div className="text-xs text-gray-500 uppercase">Accuracy</div>
            <div className="text-lg font-bold text-gray-800">{formatPercentage(accuracy)}</div>
          </div>
          <div className="p-3 bg-white border border-gray-200 rounded-lg text-center">
            <div className="text-xs text-gray-500 uppercase">Precision</div>
            <div className="text-lg font-bold text-gray-800">{formatPercentage(precision)}</div>
          </div>
          <div className="p-3 bg-white border border-gray-200 rounded-lg text-center">
            <div className="text-xs text-gray-500 uppercase">Recall</div>
            <div className="text-lg font-bold text-gray-800">{formatPercentage(recall)}</div>
          </div>
          <div className="p-3 bg-white border border-gray-200 rounded-lg text-center">
            <div className="text-xs text-gray-500 uppercase">Specificity</div>
            <div className="text-lg font-bold text-gray-800">{formatPercentage(specificity)}</div>
          </div>
          <div className="p-3 bg-white border border-gray-200 rounded-lg text-center">
            <div className="text-xs text-gray-500 uppercase">FP Rate</div>
            <div className="text-lg font-bold text-red-600">{formatPercentage(fpr)}</div>
          </div>
          <div className="p-3 bg-white border border-gray-200 rounded-lg text-center">
            <div className="text-xs text-gray-500 uppercase">FN Rate</div>
            <div className="text-lg font-bold text-orange-600">{formatPercentage(fnr)}</div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ConfusionMatrixChart;
