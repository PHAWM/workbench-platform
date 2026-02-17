import React from 'react';
import { formatPercentage, formatCount } from '../utils/axisFormatters';

// Classification Report table visualization
const ClassificationReportTable = ({ data }) => {
  if (!data) {
    return (
      <div className="text-gray-500 italic text-center py-8">
        No classification report data available
      </div>
    );
  }

  // Extract class-level metrics and averages
  const classKeys = Object.keys(data).filter(
    k => !['accuracy', 'macro avg', 'weighted avg'].includes(k)
  );

  const macroAvg = data['macro avg'];
  const weightedAvg = data['weighted avg'];
  const accuracy = data.accuracy;

  return (
    <div className="space-y-4">
      {/* Overall Accuracy */}
      {accuracy !== undefined && (
        <div className="p-4 bg-purple-50 border-2 border-purple-200 rounded-xl text-center">
          <div className="text-sm text-gray-600 uppercase tracking-wide">Overall Accuracy</div>
          <div className="text-3xl font-bold text-purple-700">{formatPercentage(accuracy)}</div>
        </div>
      )}

      {/* Per-class Metrics Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-gray-100">
              <th className="border border-gray-300 p-3 text-left font-semibold">Class</th>
              <th className="border border-gray-300 p-3 text-center font-semibold">Precision</th>
              <th className="border border-gray-300 p-3 text-center font-semibold">Recall</th>
              <th className="border border-gray-300 p-3 text-center font-semibold">F1-Score</th>
              <th className="border border-gray-300 p-3 text-center font-semibold">Support</th>
            </tr>
          </thead>
          <tbody>
            {classKeys.map((classKey) => {
              const classData = data[classKey];
              return (
                <tr key={classKey} className="hover:bg-gray-50">
                  <td className="border border-gray-300 p-3 font-medium">{classKey}</td>
                  <td className="border border-gray-300 p-3 text-center">
                    {formatPercentage(classData.precision)}
                  </td>
                  <td className="border border-gray-300 p-3 text-center">
                    {formatPercentage(classData.recall)}
                  </td>
                  <td className="border border-gray-300 p-3 text-center">
                    {formatPercentage(classData['f1-score'])}
                  </td>
                  <td className="border border-gray-300 p-3 text-center">
                    {formatCount(classData.support)}
                  </td>
                </tr>
              );
            })}

            {/* Separator */}
            <tr>
              <td colSpan={5} className="border-t-2 border-gray-400"></td>
            </tr>

            {/* Macro Average */}
            {macroAvg && (
              <tr className="bg-blue-50">
                <td className="border border-gray-300 p-3 font-semibold">Macro Avg</td>
                <td className="border border-gray-300 p-3 text-center font-medium">
                  {formatPercentage(macroAvg.precision)}
                </td>
                <td className="border border-gray-300 p-3 text-center font-medium">
                  {formatPercentage(macroAvg.recall)}
                </td>
                <td className="border border-gray-300 p-3 text-center font-medium">
                  {formatPercentage(macroAvg['f1-score'])}
                </td>
                <td className="border border-gray-300 p-3 text-center font-medium">
                  {formatCount(macroAvg.support)}
                </td>
              </tr>
            )}

            {/* Weighted Average */}
            {weightedAvg && (
              <tr className="bg-green-50">
                <td className="border border-gray-300 p-3 font-semibold">Weighted Avg</td>
                <td className="border border-gray-300 p-3 text-center font-medium">
                  {formatPercentage(weightedAvg.precision)}
                </td>
                <td className="border border-gray-300 p-3 text-center font-medium">
                  {formatPercentage(weightedAvg.recall)}
                </td>
                <td className="border border-gray-300 p-3 text-center font-medium">
                  {formatPercentage(weightedAvg['f1-score'])}
                </td>
                <td className="border border-gray-300 p-3 text-center font-medium">
                  {formatCount(weightedAvg.support)}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default ClassificationReportTable;
