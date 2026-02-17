import React, { useState } from 'react';
import { ChevronDown, ArrowLeft, X, Plus, User } from 'lucide-react';

const MetricTypeModal = ({ isOpen, onClose, onSelectType }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-purple border-2 border-purple-100 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-purple-200">
          <div>
            <h2 className="text-xl font-bold">Create New Metric</h2>
            <p className="text-gray-600 mt-1">Choose the type of metric you want to create</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-full transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          <button
            onClick={() => onSelectType('qualitative')}
            className="w-full p-4 border-2 border-purple-200 rounded-xl hover:border-purple-300 hover:bg-purple-50 transition-all text-left"
          >
            <h3 className="font-semibold text-purple-900">Qualitative Metric</h3>
            <p className="text-sm text-purple-700 mt-1">
              Metrics based on subjective assessment, categories, or descriptive data
            </p>
          </button>

          <button
            onClick={() => onSelectType('quantitative')}
            className="w-full p-4 border-2 border-purple-200 rounded-xl hover:border-purple-300 hover:bg-purple-50 transition-all text-left"
          >
            <h3 className="font-semibold text-purple-900">Quantitative Metric</h3>
            <p className="text-sm text-purple-700 mt-1">
              Metrics based on numerical data, measurements, or statistical analysis
            </p>
          </button>
        </div>
      </div>
    </div>
  );
};

export default MetricTypeModal;