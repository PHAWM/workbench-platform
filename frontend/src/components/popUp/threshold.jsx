import React, { useState, useEffect } from 'react';
import { X, Save, AlertCircle, Info } from 'lucide-react';

const ThresholdModal = ({ 
  isOpen, 
  onClose, 
  metric, 
  onSave 
}) => {
  const [thresholdValue, setThresholdValue] = useState('');
  const [errors, setErrors] = useState({});

  // A qualitative metric's threshold is one of its scale labels, not a free number.
  const isQualitative =
    (metric?.metricType || metric?.metric_type)?.toLowerCase() === 'qualitative';

  // Resolve the ordered list of scale labels regardless of which shape the
  // metric carries: a {label: value} map (optionally nested under scale_points),
  // or the scalePointsArray of {value, label} used by the create form.
  const getScaleLabels = (m) => {
    if (!m) return [];
    if (Array.isArray(m.scalePointsArray) && m.scalePointsArray.length) {
      return m.scalePointsArray.map((p) => p.label).filter(Boolean);
    }
    const raw = m.scale_points?.scale_points || m.scale_points;
    if (raw && typeof raw === 'object') {
      // Order by the numeric scale value so labels read low -> high.
      return Object.entries(raw)
        .sort((a, b) => Number(a[1]) - Number(b[1]))
        .map(([label]) => label);
    }
    return [];
  };

  const scaleLabels = getScaleLabels(metric);

  // Reset form when modal opens with new metric
  useEffect(() => {
    if (isOpen && metric) {
      setThresholdValue(metric.threshold ?? '');
      setErrors({});
    }
  }, [isOpen, metric]);

  // Close modal when clicking outside
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  // Validate form
  const validateForm = () => {
    const newErrors = {};

    if (isQualitative) {
      if (!String(thresholdValue).trim()) {
        newErrors.thresholdValue = 'Please select a scale label as the threshold';
      }
    } else if (!String(thresholdValue).trim()) {
      newErrors.thresholdValue = 'Threshold value is required';
    } else if (isNaN(parseFloat(thresholdValue))) {
      newErrors.thresholdValue = 'Threshold value must be a valid number';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handle save
  const handleSave = () => {
    if (validateForm()) {
      const thresholdData = {
        // Qualitative thresholds are label strings; quantitative are numbers.
        value: isQualitative ? thresholdValue : parseFloat(thresholdValue),
        metricId: metric.id,
        metricName: metric.name,
        timestamp: new Date().toISOString()
      };

      onSave(thresholdData);
      onClose();
    }
  };

  // Handle key press for accessibility
  const handleKeyPress = (e) => {
    if (e.key === 'Escape') {
      onClose();
    } else if (e.key === 'Enter' && e.ctrlKey) {
      handleSave();
    }
  };

  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
      onClick={handleBackdropClick}
      onKeyDown={handleKeyPress}
      tabIndex={-1}
    >
      <div className="bg-purple border-2 border-purple-100 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-purple-200">
          <div>
            <h2 className="text-xl font-bold text-gray-900">Set Threshold</h2>
            <p className="text-sm text-gray-600 mt-1">
              Configure threshold for: <span className="font-medium">{metric?.name}</span>
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-full transition-colors"
            aria-label="Close modal"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Threshold Value */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {isQualitative
                ? 'Choose the scale label that is still acceptable to you for this metric.'
                : 'Decide the value of the metric performance that is still acceptable to you.'}
            </label>

            {isQualitative ? (
              scaleLabels.length > 0 ? (
                <div className="space-y-2">
                  {scaleLabels.map((label, index) => {
                    const isSelected = thresholdValue === label;
                    return (
                      <label
                        key={`${label}-${index}`}
                        className={`flex items-center gap-3 px-4 py-3 border-2 rounded-xl cursor-pointer transition-all ${
                          isSelected
                            ? 'border-green-400 bg-green-50'
                            : 'border-gray-300 hover:border-purple-300'
                        }`}
                      >
                        <input
                          type="radio"
                          name="threshold"
                          value={label}
                          checked={isSelected}
                          onChange={() => setThresholdValue(label)}
                          className="w-5 h-5 text-green-600 border-gray-300 focus:ring-green-500 flex-shrink-0"
                        />
                        <span className="text-sm font-bold text-purple-600 bg-purple-200 rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0">
                          {index + 1}
                        </span>
                        <span className="text-base font-medium text-gray-800">{label}</span>
                      </label>
                    );
                  })}
                </div>
              ) : (
                <p className="text-sm text-gray-500 italic border-2 border-dashed border-gray-200 rounded-xl py-6 text-center">
                  This metric has no scale labels to choose from.
                </p>
              )
            ) : (
              <input
                type="text"
                value={thresholdValue}
                onChange={(e) => setThresholdValue(e.target.value)}
                placeholder="Enter threshold value (e.g., 0.95, 100, 5.5)"
                className={`w-full px-4 py-3 border rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all ${
                  errors.thresholdValue ? 'border-red-300 bg-red-50' : 'border-gray-300'
                }`}
              />
            )}

            {errors.thresholdValue && (
              <p className="text-red-600 text-sm mt-1 flex items-center gap-1">
                {errors.thresholdValue}
              </p>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-3 py-3 px-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-xl hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
             className="bg-purple-100 hover:bg-purple-200 px-4 py-2 rounded-full text-sm font-semibold transition-colors border-2 border-purple-200"
          >
            Save Threshold
          </button>
        </div>

        {/* Keyboard shortcuts hint */}
        <div className="px-6 pb-4">
          <p className="text-xs text-gray-500">
            Press <kbd className="px-1 py-0.5 bg-gray-200 rounded text-xs">Esc</kbd> to close, 
            <kbd className="px-1 py-0.5 bg-gray-200 rounded text-xs mx-1">Ctrl+Enter</kbd> to save
          </p>
        </div>
      </div>
    </div>
  );
};

export default ThresholdModal;