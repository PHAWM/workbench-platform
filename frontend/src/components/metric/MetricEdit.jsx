import React, { useState, useEffect } from 'react';
import { ArrowLeft, GripVertical } from 'lucide-react';
import CreatableMultiSelect from '../ui/creatablemultiselect';
import { useFormLogic } from '../../hooks/useFormLogic';
import { useFormValidation } from '../../hooks/useFormValidation';
import {
  parseScalePoints,
  parseUnderlyingFeatures,
  parseFeatureRanges,
  parseTargetFeatures,
  buildQuantitativeMetricValues,
  buildQualitativeMetricValues
} from '../../utils/formUtils';

export const EditMetricForm = ({
  metric,
  onCancel,
  onSave,
  availableUnderlyingFeatures = [],
  availableTargetFeatures = [],
  isReadOnly = false,
  toast = null,
}) => {
  const notify = {
    success: (message) => toast ? toast.success(message) : alert(message),
    error: (message) => toast ? toast.error(message) : alert(message),
    warning: (message) => toast ? toast.warning(message) : alert(message),
    info: (message) => toast ? toast.info(message) : alert(message)
  };

  const [metricType] = useState(
    metric?.metricType?.toLowerCase() ||
    metric?.metric_type?.toLowerCase() ||
    (metric?.formula ? 'quantitative' : 'qualitative')
  );

  const [draggedIndex, setDraggedIndex] = useState(null);
  const [scaleLabels, setScaleLabels] = useState([]);

  // Initialize form data from existing metric
  const initialFormData = metric ? {
    name: metric.name || '',
    description: metric.description || '',
    definition: metric.definition || metric.formula || '',
    threshold: metric.threshold || '',
    reason: metric.reason || '',
    targetFeatures: parseTargetFeatures(metric.targetFeatures, availableTargetFeatures),
    underlyingFeatures: parseUnderlyingFeatures(metric.underlyingFeatures || metric.features, availableUnderlyingFeatures),
    featureRanges: parseFeatureRanges(metric, availableUnderlyingFeatures),
    ...parseScalePoints(metric.scale_points)
  } : {};

  // Derive featureGroups from the widest range loaded, falling back to 2
  if (metric) {
    const maxGroups = Math.max(
      2,
      ...Object.values(initialFormData.featureRanges || {}).map(r => Object.keys(r).length),
    );
    initialFormData.featureGroups = metric.featureGroups ?? String(maxGroups);
  }

  const {
    formData,
    hasChanges,
    getChanges,
    handleInputChange,
    handleUnderlyingFeaturesChange,
    handleFeatureRangeChange
  } = useFormLogic(initialFormData, metric);

  // Validation rules based on metric type
  const qualitativeValidationRules = {
    name: { required: true, message: 'Metric name is required' },
    description: { required: true, message: 'Description is required' },
    reason: { required: true, message: 'Reason is required' },
    points: {
      required: true,
      min: 1,
      max: 20,
      message: 'Scale points must be between 1 and 20'
    }
  };

  const quantitativeValidationRules = {
    name: { required: true, message: 'Metric name is required' },
    description: { required: true, message: 'Description is required' },
    targetFeatures: { required: true, message: 'At least one target is required' },
    underlyingFeatures: { required: true, message: 'At least one distinguishing factor is required' },
    threshold: { required: true, message: 'Threshold is required' },
    reason: { required: true, message: 'Reason is required' },
    featureGroups: { required: true, message: 'Number of Groups is required' }
  };

  const {
    touchField,
    validateAndSetError,
    validateAllFields,
    getFieldError,
    hasFieldError,
    setFieldError,
    clearFieldError
  } = useFormValidation(metricType === 'qualitative' ? qualitativeValidationRules : quantitativeValidationRules);

  const targetFeatureOptions = availableTargetFeatures.map(f => f.target_feature || f.name || `Feature ${f.id}`);
  const underlyingFeatureOptions = availableUnderlyingFeatures.map(f => f.feature_name || f.name || `Feature ${f.id}`);

  // Handler for qualitative features - updates 'underlyingFeatures' field directly
  const handleQualitativeFeaturesChange = (features) => {
    handleInputChange('underlyingFeatures', features);
  };

  // Initialize scale labels when points number changes (for qualitative metrics)
  useEffect(() => {
    if (metricType === 'qualitative') {
      const numPoints = parseInt(formData.points) || 0;
      if (numPoints > 0) {
        const newLabels = Array(numPoints).fill('').map((_, index) => {
          return formData.scalePointsArray?.[index]?.label || scaleLabels[index] || '';
        });
        setScaleLabels(newLabels);

        if (formData.scalePointsArray?.length !== numPoints) {
          const newScalePointsArray = newLabels.map((label, index) => ({
            value: index + 1,
            label: label
          }));
          handleInputChange('scalePointsArray', newScalePointsArray);
          handleInputChange('scalePoints', numPoints.toString());
        }
      } else {
        setScaleLabels([]);
        if (formData.scalePointsArray?.length > 0) {
          handleInputChange('scalePointsArray', []);
          handleInputChange('scalePoints', '0');
        }
      }
    }
  }, [formData.points, metricType]);

  // Helper function to check if a label is a duplicate
  const isDuplicateLabel = (index, labels) => {
    const currentLabel = labels[index]?.trim().toLowerCase();
    if (!currentLabel) return false;
    return labels.some((label, i) =>
      i !== index && label.trim().toLowerCase() === currentLabel
    );
  };

  const handleLabelChange = (index, value) => {
    const newLabels = [...scaleLabels];
    newLabels[index] = value;
    setScaleLabels(newLabels);

    const newScalePointsArray = newLabels.map((label, idx) => ({
      value: idx + 1,
      label: label
    }));
    handleInputChange('scalePointsArray', newScalePointsArray);

    // Inline validation for duplicates
    const trimmedLabels = newLabels.map(label => label.trim().toLowerCase()).filter(l => l);
    const uniqueLabels = new Set(trimmedLabels);
    if (uniqueLabels.size !== trimmedLabels.length) {
      setFieldError('scaleLabels', 'Scale point labels must be unique');
    } else {
      clearFieldError('scaleLabels');
    }
  };

  const handleDragStart = (index) => {
    setDraggedIndex(index);
  };

  const handleDragOver = (e, index) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === index) return;

    const newLabels = [...scaleLabels];
    const draggedLabel = newLabels[draggedIndex];
    newLabels.splice(draggedIndex, 1);
    newLabels.splice(index, 0, draggedLabel);
    setScaleLabels(newLabels);

    const newScalePointsArray = newLabels.map((label, idx) => ({
      value: idx + 1,
      label: label
    }));
    handleInputChange('scalePointsArray', newScalePointsArray);
    setDraggedIndex(index);
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
  };

  const handleSave = () => {
    if (!hasChanges()) {
      notify.info('No changes detected. Nothing to save.');
      return;
    }

    const changes = getChanges();
    const validation = validateAllFields(formData);

    // Additional validation for qualitative metrics
    let hasScaleLabelErrors = false;
    if (metricType === 'qualitative') {
      if (scaleLabels.length === 0) {
        setFieldError('points', 'At least one scale point is required');
        hasScaleLabelErrors = true;
      } else if (scaleLabels.some(label => !label.trim())) {
        setFieldError('scaleLabels', 'All scale point labels must be filled');
        hasScaleLabelErrors = true;
      } else {
        // Check for duplicate labels
        const trimmedLabels = scaleLabels.map(label => label.trim().toLowerCase());
        const uniqueLabels = new Set(trimmedLabels);
        if (uniqueLabels.size !== trimmedLabels.length) {
          setFieldError('scaleLabels', 'Scale point labels must be unique');
          hasScaleLabelErrors = true;
        } else {
          clearFieldError('scaleLabels');
        }
      }

      if (formData.scalePointsArray?.length > 0 &&
          parseInt(formData.points) !== formData.scalePointsArray.length) {
        setFieldError('points', `Scale points (${formData.points}) doesn't match labels (${formData.scalePointsArray.length})`);
        hasScaleLabelErrors = true;
      }
    }

    // Additional validation for quantitative metrics
    if (metricType === 'quantitative') {
      const incompleteRanges = formData.underlyingFeatures?.filter(feature => {
        const ranges = formData.featureRanges?.[feature];
        return !ranges || !ranges.group1 || !ranges.group2;
      }) || [];

      if (incompleteRanges.length > 0) {
        notify.error(`Incomplete ranges for: ${incompleteRanges.join(', ')}`);
        return;
      }
    }

    if (!validation.isValid || hasScaleLabelErrors) {
      notify.error('Validation failed. Please check all required fields.');
      return;
    }

    // Build API payload
    const apiPayload = {
      metric_id: metric.id,
      type: metricType,
      audit_id: sessionStorage.getItem('auditId')
    };

    Object.keys(changes).forEach(key => {
      switch (key) {
        case 'name':
        case 'description':
        case 'reason':
          apiPayload[key] = formData[key].trim();
          break;
        case 'definition':
          apiPayload[metricType === 'qualitative' ? 'definition' : 'formula'] = formData.definition.trim();
          break;
        case 'threshold':
          apiPayload.metric_values = [{
            event_id: metric.eventId,
            audit_id: parseInt(sessionStorage.getItem('auditId')),
            threshold: formData.threshold.toString()
          }];
          break;
        default:
          break;
      }
    });

    // Handle metric values based on type
    if (metricType === 'quantitative' && (changes.underlyingFeatures || changes.targetFeatures || changes.featureRanges)) {
      const metricValues = buildQuantitativeMetricValues(formData, availableUnderlyingFeatures, availableTargetFeatures);
      apiPayload.metric_values = metricValues.map(mv => ({
        ...mv,
        event_id: metric.eventId,
        audit_id: parseInt(sessionStorage.getItem('auditId'))
      }));
    } else if (metricType === 'qualitative' && (changes.underlyingFeatures || changes.scalePointsArray || changes.points)) {
      // For qualitative metrics, use underlyingFeatures directly
      const metricValues = buildQualitativeMetricValues(formData, availableUnderlyingFeatures, availableTargetFeatures);
      apiPayload.metric_values = metricValues.map(mv => ({
        ...mv,
        event_id: metric.eventId,
        audit_id: parseInt(sessionStorage.getItem('auditId'))
      }));
    }

    const updatedMetric = {
      ...metric,
      ...formData,
      metricType,
      _apiPayload: apiPayload,
      _changes: changes,
      _hasChanges: true
    };

    onSave(updatedMetric);
  };

  if (!metric) {
    return (
      <div className="bg-white rounded-3xl border-2 border-purple-200 p-6 shadow-lg">
        <p className="text-center text-gray-500">No metric selected for editing</p>
      </div>
    );
  }

  const changesExist = hasChanges();

  // Render Qualitative Edit Form
  if (metricType === 'qualitative') {
    return (
      <div className="bg-purple rounded-3xl p-6 shadow-lg w-full">
        {/* Purpose Box */}
        <div className="mb-6 bg-b7efff rounded-2xl border-2 border-purple-300 p-6 shadow-md">
          <div className="flex items-start">
            <div>
              <p className="text-gray-700">
                This is the Edit Metric page for a Qualitative Metric. You can modify the metric details below. Changes will be highlighted and saved when you click the Save button.
              </p>
            </div>
          </div>
        </div>

        {/* Header */}
        <div className="flex items-center gap-3 mb-6 pb-4 border-b border-purple-200">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Edit Qualitative Metric</h1>
            <p className="text-base text-gray-600">
              Update the details for: <span className="font-medium">{metric.name || metric.description}</span>
              {changesExist && <span className="ml-2 text-orange-600 text-base">(Changes detected)</span>}
            </p>
          </div>
        </div>

        {/* Row 1: Name | Scale Points | Features */}
        <div className="grid grid-cols-3 gap-8">
          <div>
            <label className="block text-base font-medium text-gray-700 mb-1">Metric Name *</label>
            <label className="block text-base text-gray-500 mb-2">Decide on a name that represents a way to measure the event if it is happening</label>
            <input
              type="text"
              placeholder="Metric Name"
              value={formData.name}
              onChange={(e) => {
                handleInputChange('name', e.target.value);
                validateAndSetError('name', e.target.value);
              }}
              onBlur={() => {
                touchField('name');
                validateAndSetError('name', formData.name);
              }}
              disabled={isReadOnly}
              className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors ${
                hasFieldError('name') ? 'border-red-500 focus:border-red-600' : 'border-purple-200 focus:border-purple-400'
              } ${isReadOnly ? 'cursor-not-allowed' : ''}`}
            />
            {hasFieldError('name') && (
              <p className="text-base text-red-600 mt-1">{getFieldError('name')}</p>
            )}
          </div>

          <div>
            <label className="block text-base font-medium text-gray-700 mb-1">Scale Points *</label>
            <label className="block text-base text-gray-500 mb-2">Decide how many measurement points you want for this metric (max 20)</label>
            <input
              type="number"
              min="0"
              max="20"
              placeholder="e.g., 5"
              value={formData.points}
              onChange={(e) => {
                const value = parseInt(e.target.value) || 0;
                if (value <= 20) {
                  handleInputChange('points', e.target.value);
                  validateAndSetError('points', e.target.value);
                }
              }}
              onBlur={() => {
                touchField('points');
                validateAndSetError('points', formData.points);
              }}
              disabled={isReadOnly}
              className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors ${
                hasFieldError('points') ||
                (formData.scalePointsArray?.length > 0 &&
                parseInt(formData.points) !== formData.scalePointsArray.length)
                  ? 'border-red-500 focus:border-red-600'
                  : 'border-purple-200 focus:border-purple-400'
              } ${isReadOnly ? 'cursor-not-allowed' : ''}`}
            />
            {hasFieldError('points') && (
              <p className="text-base text-red-600 mt-1">{getFieldError('points')}</p>
            )}
            {!hasFieldError('points') && formData.scalePointsArray?.length > 0 &&
              parseInt(formData.points) !== formData.scalePointsArray.length && (
              <p className="text-base text-red-600 mt-1">
                Scale points ({formData.points}) doesn't match number of labels added ({formData.scalePointsArray.length})
              </p>
            )}
          </div>

          <div>
            <CreatableMultiSelect
              label="Features (Optional)"
              helpText="Choose or create what aspect of the AI Application output you want to compare"
              value={formData.underlyingFeatures || []}
              onChange={handleQualitativeFeaturesChange}
              placeholder="Select features..."
              options={underlyingFeatureOptions}
              allowCreate={true}
              isDisabled={isReadOnly}
            />
          </div>
        </div>

        {/* Row 2: Metric Description | Scale Labels (spans 2 cols) */}
        <div className="grid grid-cols-3 gap-8 mt-6">
          <div>
            <label className="block text-base font-medium text-gray-700 mb-1">Metric Description *</label>
            <label className="block text-base text-gray-500 mb-2">Describe how to measure an event if it is happening</label>
            <textarea
              placeholder="Metric Description"
              value={formData.description}
              onChange={(e) => {
                handleInputChange('description', e.target.value);
                validateAndSetError('description', e.target.value);
              }}
              onBlur={() => {
                touchField('description');
                validateAndSetError('description', formData.description);
              }}
              rows={4}
              disabled={isReadOnly}
              className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors resize-none ${
                hasFieldError('description') ? 'border-red-500 focus:border-red-600' : 'border-purple-200 focus:border-purple-400'
              } ${isReadOnly ? 'cursor-not-allowed' : ''}`}
            />
            {hasFieldError('description') && (
              <p className="text-base text-red-600 mt-1">{getFieldError('description')}</p>
            )}
            <label className="block text-base font-medium text-gray-700 mb-1 mt-4">Why are you adding this metric? *</label>
            <label className="block text-base text-gray-500 mb-2">Describe your reasoning for adding this metric</label>
            <textarea
              placeholder="Why this metric is being added"
              value={formData.reason}
              onChange={(e) => {
                handleInputChange('reason', e.target.value);
                validateAndSetError('reason', e.target.value);
              }}
              onBlur={() => {
                touchField('reason');
                validateAndSetError('reason', formData.reason);
              }}
              rows={4}
              disabled={isReadOnly}
              className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors resize-none ${
                hasFieldError('reason') ? 'border-red-500 focus:border-red-600' : 'border-purple-200 focus:border-purple-400'
              } ${isReadOnly ? 'cursor-not-allowed' : ''}`}
            />
            {hasFieldError('reason') && (
              <p className="text-base text-red-600 mt-1">{getFieldError('reason')}</p>
            )}
          </div>

          <div className="col-span-2">
            <label className="block text-base font-medium text-gray-700 mb-1">Scale Labels</label>
            <label className="block text-base text-gray-500 mb-2">
              Decide how to label each point on your scale and select which value on the scale is still acceptable for this metric (threshold)
            </label>
            <div className="grid grid-cols-2 gap-4">
              {scaleLabels.length > 0 ? (
                (() => {
                  // Split items into two columns, filling downwards
                  const midpoint = Math.ceil(scaleLabels.length / 2);
                  const leftColumn = scaleLabels.slice(0, midpoint);
                  const rightColumn = scaleLabels.slice(midpoint);

                  const renderItem = (label, index) => {
                    const hasDuplicate = isDuplicateLabel(index, scaleLabels);
                    return (
                      <div
                        key={index}
                        draggable={!isReadOnly}
                        onDragStart={() => handleDragStart(index)}
                        onDragOver={(e) => handleDragOver(e, index)}
                        onDragEnd={handleDragEnd}
                        className="flex flex-col gap-1 mb-2"
                      >
                        <div
                          className={`flex items-center gap-2 bg-purple-50 border-2 rounded-xl p-2 transition-all ${
                            hasDuplicate ? 'border-red-400 bg-red-50' :
                            formData.threshold === label && label ? 'border-green-400 bg-green-50' : 'border-purple-200'
                          } ${
                            !isReadOnly ? 'cursor-move' : ''
                          } ${
                            draggedIndex === index ? 'opacity-50 scale-95' : !isReadOnly ? 'hover:border-purple-300' : ''
                          }`}
                        >
                          {!isReadOnly && <GripVertical className="w-4 h-4 text-gray-400 flex-shrink-0" />}
                          <span className="text-base font-bold text-purple-600 bg-purple-200 rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0">
                            {index + 1}
                          </span>
                          <input
                            type="radio"
                            name="threshold"
                            checked={formData.threshold === label && label !== ''}
                            onChange={() => !isReadOnly && handleInputChange('threshold', label)}
                            disabled={isReadOnly || !label.trim()}
                            className="w-5 h-4 text-green-600 border-gray-300 focus:ring-green-500 flex-shrink-0 mx-1"
                            title="Set as threshold"
                          />
                          <input
                            type="text"
                            placeholder={`Label ${index + 1}`}
                            value={label}
                            onChange={(e) => handleLabelChange(index, e.target.value)}
                            disabled={isReadOnly}
                            className={`flex-1 min-w-0 px-3 py-1.5 border-2 rounded-xl focus:outline-none transition-colors text-base ${
                              hasDuplicate ? 'border-red-400 focus:border-red-500' : 'border-purple-200 focus:border-purple-400'
                            } ${isReadOnly ? 'cursor-not-allowed bg-gray-50' : ''}`}
                          />
                        </div>
                        {hasDuplicate && (
                          <p className="text-sm text-red-600 ml-2">Duplicate label</p>
                        )}
                      </div>
                    );
                  };

                  return (
                    <>
                      <div className="space-y-2">
                        {leftColumn.map((label, idx) => renderItem(label, idx))}
                      </div>
                      <div className="space-y-2">
                        {rightColumn.map((label, idx) => renderItem(label, midpoint + idx))}
                      </div>
                    </>
                  );
                })()
              ) : (
                <div className="col-span-2 text-center py-8 text-gray-400 text-base italic border-2 border-dashed border-gray-200 rounded-xl">
                  No scale points defined yet - enter a number above
                </div>
              )}
            </div>
            {hasFieldError('scaleLabels') && (
              <p className="text-base text-red-600 mt-2">{getFieldError('scaleLabels')}</p>
            )}
            {formData.threshold && (
              <p className="text-base text-green-600 mt-2">
                Threshold set to: {formData.threshold}
              </p>
            )}
          </div>
        </div>

        {/* Metric Preview */}
        <div className="mt-6">
          <label className="block text-base font-medium text-gray-700 mb-2">Metric Preview</label>
          <div className="bg-white border-2 border-purple-200 rounded-2xl p-6">
            <div className="text-center">
              <div className="font-medium text-gray-800 mb-6 text-lg">
                {formData.name || '<Metric Name>'}
              </div>

              {formData.scalePointsArray?.length > 0 ? (
                <div className="w-full">
                  <div className="text-base text-gray-500 mb-6">Scale Preview:</div>

                  <div className="relative flex flex-col items-center">
                    <div
                      className="absolute top-4 h-3 bg-gradient-to-r from-purple-200 to-purple-400 rounded-full"
                      style={{
                        width: `calc(100% - ${100 / formData.scalePointsArray.length}%)`,
                        left: `${50 / formData.scalePointsArray.length}%`
                      }}
                    />

                    <div className="relative w-full flex items-start justify-between">
                      {formData.scalePointsArray.map((item, index) => {
                        const isThreshold = formData.threshold === item.label;

                        return (
                          <div key={index} className="flex-1 flex flex-col items-center z-10">
                            <div className={`w-10 h-10 rounded-full text-white text-sm font-bold flex items-center justify-center transition-all duration-300 ring-4 ring-white shadow-base border-3 border-purple-100 ${
                              isThreshold
                                  ? 'bg-purple-400 scale-110 text-purple-900'
                                  : 'bg-purple-500 scale-110'
                            }`}>
                              {index + 1}
                            </div>

                            <div className="mt-3">
                              <div className={`text-sm font-medium ${isThreshold ? 'text-purple-700 font-bold' : 'text-gray-600'}`}>
                                {!item.label ? `<Label ${index+1}>` : item.label}
                              </div>
                              {isThreshold && item.label && (
                                <span className="block text-base uppercase tracking-tighter text-purple-600 font-black mt-1">
                                  Threshold
                                </span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-base text-gray-400 italic py-8 border-2 border-dashed border-gray-100 rounded-xl">
                  Add scale labels to see preview
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Save Button */}
        <div className="flex justify-between items-center mt-8 pt-6 border-t border-purple-200">
          <button
            onClick={onCancel}
            className="flex items-center gap-2 px-4 py-2 text-gray-600 border-2 border-purple-200 rounded-full hover:bg-purple-200 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Return to Assign Metric without saving
          </button>
          <button
            onClick={handleSave}
            className={`px-4 py-2 rounded-full text-base font-semibold transition-colors border-2 ${
              changesExist && !isReadOnly
                ? 'bg-purple-100 hover:bg-purple-200 border-purple-200 text-purple-800'
                : 'bg-gray-100 border-gray-300 text-gray-500 cursor-not-allowed'
            }`}
            disabled={!changesExist || isReadOnly}
          >
            {isReadOnly ? 'Read-Only Mode' : changesExist ? 'Save Qualitative Metric' : 'No Changes to Save'}
          </button>
        </div>
      </div>
    );
  }

  // Render Quantitative Edit Form
  return (
    <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg w-full">
      {/* Purpose Box */}
      <div className="mb-6 bg-b7efff rounded-2xl border-2 border-purple-300 p-6 shadow-md">
        <div className="flex items-start">
          <div>
            <p className="text-gray-700">
              This is the Edit Metric page for a Quantitative Metric. You can modify the metric details below. Changes will be highlighted and saved when you click the Save button.
            </p>
          </div>
        </div>
      </div>

      {/* Header */}
      <div className="flex items-center gap-3 mb-6 pb-4 border-b border-purple-200">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Edit Quantitative Metric</h1>
          <p className="text-base text-gray-600">
            Update the details for: <span className="font-medium">{metric.name || metric.description}</span>
            {changesExist && <span className="ml-2 text-orange-600 text-base">(Changes detected)</span>}
          </p>
        </div>
      </div>

      {/* Row 1: Name | Target | Threshold */}
      <div className="grid grid-cols-3 gap-8">
        <div>
          <label className="block text-base font-medium text-gray-700 mb-1">Metric Name *</label>
          <label className="block text-base text-gray-500 mb-2">Decide on a name that represents a way to measure the event if it is happening</label>
          <input
            type="text"
            placeholder="Metric Name"
            value={formData.name}
            onChange={(e) => {
              handleInputChange('name', e.target.value);
              validateAndSetError('name', e.target.value);
            }}
            onBlur={() => {
              touchField('name');
              validateAndSetError('name', formData.name);
            }}
            disabled={isReadOnly}
            className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors ${
              hasFieldError('name') ? 'border-red-500 focus:border-red-600' : 'border-purple-200 focus:border-purple-400'
            } ${isReadOnly ? 'cursor-not-allowed' : ''}`}
          />
          {hasFieldError('name') && (
            <p className="text-base text-red-600 mt-1">{getFieldError('name')}</p>
          )}
        </div>
        <div>
          <CreatableMultiSelect
            label="Target *"
            helpText="Choose or create what aspect of the AI Application output you want to compare"
            value={formData.targetFeatures}
            onChange={(value) => {
              handleInputChange('targetFeatures', value);
              validateAndSetError('targetFeatures', value);
            }}
            placeholder="Select or create targets..."
            options={targetFeatureOptions}
            hasError={hasFieldError('targetFeatures')}
            isDisabled={isReadOnly}
          />
          {hasFieldError('targetFeatures') && (
            <p className="text-base text-red-600 mt-1">{getFieldError('targetFeatures')}</p>
          )}
        </div>
        <div>
          <label className="block text-base font-medium text-gray-700 mb-1">What is the threshold you wish to assign to this metric? *</label>
          <label className="block text-base text-gray-500 mb-2">Decide the value of the metric performance that is still acceptable to you.</label>
          <input
            type="text"
            placeholder="e.g. 5%"
            value={formData.threshold}
            onChange={(e) => {
              handleInputChange('threshold', e.target.value);
              validateAndSetError('threshold', e.target.value);
            }}
            onBlur={() => {
              touchField('threshold');
              validateAndSetError('threshold', formData.threshold);
            }}
            disabled={isReadOnly}
            className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors ${
              hasFieldError('threshold') ? 'border-red-500 focus:border-red-600' : 'border-purple-200 focus:border-purple-400'
            } ${isReadOnly ? 'cursor-not-allowed' : ''}`}
          />
          {hasFieldError('threshold') && (
            <p className="text-base text-red-600 mt-1">{getFieldError('threshold')}</p>
          )}
        </div>
      </div>

      {/* Row 2: Metric Description & Reason | Distinguish Factor | Number of Groups */}
      <div className="grid grid-cols-3 gap-8 mt-6">
        <div className="col-span-1">
          <div>
            <label className="block text-base font-medium text-gray-700 mb-1">Metric Description *</label>
            <label className="block text-base text-gray-500 mb-2">Describe how to measure an event if it is happening</label>
            <textarea
              placeholder="Metric Description"
              value={formData.description}
              onChange={(e) => {
                handleInputChange('description', e.target.value);
                validateAndSetError('description', e.target.value);
              }}
              onBlur={() => {
                touchField('description');
                validateAndSetError('description', formData.description);
              }}
              rows={4}
              disabled={isReadOnly}
              className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors resize-none ${
                hasFieldError('description') ? 'border-red-500 focus:border-red-600' : 'border-purple-200 focus:border-purple-400'
              } ${isReadOnly ? 'cursor-not-allowed' : ''}`}
            />
            {hasFieldError('description') && (
              <p className="text-base text-red-600 mt-1">{getFieldError('description')}</p>
            )}
          </div>
          <div className="mt-4">
            <label className="block text-base font-medium text-gray-700 mb-1">Why are you adding this metric? *</label>
            <label className="block text-base text-gray-500 mb-2">Describe your reasoning for adding this metric</label>
            <textarea
              placeholder="Why this metric is being added"
              value={formData.reason}
              onChange={(e) => {
                handleInputChange('reason', e.target.value);
                validateAndSetError('reason', e.target.value);
              }}
              onBlur={() => {
                touchField('reason');
                validateAndSetError('reason', formData.reason);
              }}
              rows={4}
              disabled={isReadOnly}
              className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors resize-none ${
                hasFieldError('reason') ? 'border-red-500 focus:border-red-600' : 'border-purple-200 focus:border-purple-400'
              } ${isReadOnly ? 'cursor-not-allowed' : ''}`}
            />
            {hasFieldError('reason') && (
              <p className="text-base text-red-600 mt-1">{getFieldError('reason')}</p>
            )}
          </div>
        </div>
        <div className="col-span-2">
          <div className="grid grid-cols-2 gap-8">
            <div>
              <CreatableMultiSelect
                label="Distinguishing Factor *"
                helpText="Choose or create the factor you want to compare this metric on"
                value={formData.underlyingFeatures}
                onChange={(value) => {
                  handleUnderlyingFeaturesChange(value);
                  validateAndSetError('underlyingFeatures', value);
                }}
                placeholder="Select or create distinguishing factors..."
                options={underlyingFeatureOptions}
                hasError={hasFieldError('underlyingFeatures')}
                isDisabled={isReadOnly}
              />
              {hasFieldError('underlyingFeatures') && (
                <p className="text-base text-red-600 mt-1">{getFieldError('underlyingFeatures')}</p>
              )}
            </div>
            <div>
              <label className="block text-base font-medium text-gray-700 mb-1">Number of Groups for Comparison</label>
              <label className="block text-base text-gray-500 mb-2">Decide how many groups you want to compare within the Distinguishing Factor</label>
              <input
                type="number"
                min="1"
                max="5"
                placeholder="e.g., 2"
                value={formData.featureGroups}
                onChange={(e) => {
                  const value = parseInt(e.target.value) || 0;
                  if (value >= 0 && value <= 5) {
                    handleInputChange('featureGroups', e.target.value);
                  }
                }}
                disabled={isReadOnly}
                className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors border-purple-200 focus:border-purple-400 ${isReadOnly ? 'cursor-not-allowed' : ''}`}
              />
            </div>
          </div>

          <div className="col-span-1 mt-6">
            <label className="block text-base font-medium text-gray-700 mb-1">Define Distinguishing Factor Groups *</label>
            <label className="block text-base text-gray-500 mb-2">Decide the values, or range, of each group you want to compare</label>
            {formData.underlyingFeatures?.length === 0 ? (
              <div className="text-base text-gray-400 italic p-4 border-2 border-dashed border-gray-200 rounded-2xl text-center">
                Select Distinguishing Factors to define their group ranges
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-4">
                {(formData.underlyingFeatures || []).map((feature) => {
                  const numGroups = formData.featureGroups === 'Minimum of 2'
                    ? 2
                    : parseInt(formData.featureGroups);

                  const featureObj = availableUnderlyingFeatures.find(
                    f => (f.feature_name || f.name) === feature
                  );
                  const rangeInfo = featureObj?.range;

                  return (
                    <div key={feature} className="p-4 border border-purple-200 rounded-xl bg-purple-50">
                      <h4 className="font-medium text-gray-700 mb-1">{feature.charAt(0).toUpperCase() + (feature).slice(1)}</h4>
                      {rangeInfo && (
                        <p className="text-base text-gray-500 mb-3">
                          Range: {Array.isArray(rangeInfo.range)
                            ? rangeInfo.range.join(', ')
                            : `${rangeInfo.type || 'Available values'}`}
                        </p>
                      )}
                      <div className="grid grid-cols-2 gap-3">
                        {Array.from({ length: numGroups }, (_, index) => {
                          const groupKey = `group${index + 1}`;
                          return (
                            <input
                              key={groupKey}
                              type="text"
                              placeholder={`${(feature).charAt(0).toUpperCase() + (feature).slice(1)} Group ${index + 1} Value Range`}
                              value={formData.featureRanges?.[feature]?.[groupKey] || ''}
                              onChange={(e) => handleFeatureRangeChange(feature, groupKey, e.target.value)}
                              disabled={isReadOnly}
                              className={`w-full bg-purple px-4 py-3 border-2 border-purple-200 rounded-2xl focus:border-purple-400 focus:outline-none transition-colors ${isReadOnly ? 'cursor-not-allowed' : ''}`}
                            />
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            {hasFieldError('featureRanges') && (
              <p className="text-base text-red-600 mt-2">{getFieldError('featureRanges')}</p>
            )}
          </div>
        </div>
      </div>

      {/* Metric Preview */}
      <div className="mt-6">
        <label className="block text-base font-medium text-gray-700 mb-1">Metric Preview</label>
        <div className="bg-white border-2 border-purple-200 rounded-2xl p-4">
          <div className="text-center">
            <div className="font-medium">{formData.name || '<Metric Name>'}</div>
            <div className="text-base text-gray-600 mt-1">
              Target: {formData.targetFeatures?.length > 0 ? formData.targetFeatures.join(', ') : '<Targets>'}
            </div>
            <div className="text-base text-gray-500 mt-1">
              Distinguishing Factors: {formData.underlyingFeatures?.length > 0 ? formData.underlyingFeatures.join(', ') : '<Distinguishing Factors>'}
            </div>
            <div className="w-full h-1 bg-gray-200 rounded mt-2 mb-2"></div>
            <div className="text-base">Threshold: {formData.threshold || '<Threshold>'}</div>
            {formData.underlyingFeatures?.length > 0 && (
              <div className="mt-2 space-y-1">
                {formData.underlyingFeatures.map((feature) => {
                  const numGroups = formData.featureGroups === 'Minimum of 2'
                    ? 2
                    : parseInt(formData.featureGroups);

                  return (
                    <div key={feature} className="space-y-1">
                      <div className="text-base text-gray-400 font-medium">{feature}</div>
                      <div className="flex justify-between gap-1 text-base text-gray-500">
                        {Array.from({ length: numGroups }, (_, index) => {
                          const groupKey = `group${index + 1}`;
                          return (
                            <span key={groupKey}>
                              {formData.featureRanges?.[feature]?.[groupKey] || `Group ${index + 1}`}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-between items-center mt-8 pt-6 border-t border-purple-200">
        <button
          onClick={onCancel}
          className="flex items-center gap-2 px-4 py-2 text-gray-600 border-2 border-purple-200 rounded-full hover:bg-purple-200 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Return to Assign Metric without saving
        </button>
        <button
          onClick={handleSave}
          className={`px-4 py-2 rounded-full text-base font-semibold transition-colors border-2 ${
            changesExist && !isReadOnly
              ? 'bg-purple-100 hover:bg-purple-200 border-purple-200 text-purple-800'
              : 'bg-gray-100 border-gray-300 text-gray-500 cursor-not-allowed'
          }`}
          disabled={!changesExist || isReadOnly}
        >
          {isReadOnly ? 'Read-Only Mode' : changesExist ? metricType === 'qualitative' ? 'Save Qualitative Metric' : 'Save Quantitative Metric' : 'No Changes to Save'}
        </button>
      </div>
    </div>
  );
};

export default EditMetricForm;
