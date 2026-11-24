import React, { useState, useEffect } from 'react';
import { ArrowLeft, Plus, X, GripVertical } from 'lucide-react';
import CreatableMultiSelect from '../ui/creatablemultiselect';
import { useFormLogic } from '../../hooks/useFormLogic';
import { useFormValidation } from '../../hooks/useFormValidation';
import { buildQualitativeMetricValues } from '../../utils/formUtils';

const QualitativeMetricForm = ({
  onCancel,
  onComplete,
  showBackToAssignment = false,
  onBackToAssignment,
  preservedData = null,
  availableUnderlyingFeatures = [],
  availableTargetFeatures = [],
}) => {
  const [draggedIndex, setDraggedIndex] = useState(null);
  const [scaleLabels, setScaleLabels] = useState([]); // Store label inputs for each scale point

  const initialFormData = {
    name: '',
    description: '',
    definition: '',
    underlyingFeatures: [],
    targetFeatures: [],
    scalePoints: '0',
    scalePointsArray: [],
    threshold: '',
    reason: '',
    ...preservedData
  };

  const {
    formData,
    handleInputChange,
    handleUnderlyingFeaturesChange
  } = useFormLogic(initialFormData, preservedData);

  // Validation rules for inline validation
  const validationRules = {
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

  const {
    touchField,
    validateAndSetError,
    validateAllFields,
    getFieldError,
    hasFieldError,
    setFieldError,
    clearFieldError
  } = useFormValidation(validationRules);

  const underlyingFeatureOptions = availableUnderlyingFeatures.map(f => f.feature_name || f.name || `Feature ${f.id}`);

  // Initialize scale labels when points number changes
  useEffect(() => {
    const numPoints = parseInt(formData.points) || 0;
    if (numPoints > 0) {
      // Initialize empty labels or preserve existing ones
      const newLabels = Array(numPoints).fill('').map((_, index) => {
        // Keep existing label if it exists
        return scaleLabels[index] || formData.scalePointsArray?.[index]?.label || '';
      });
      setScaleLabels(newLabels);

      // Update scalePointsArray with sequential values
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
      handleInputChange('scalePointsArray', []);
      handleInputChange('scalePoints', '0');
    }
  }, [formData.points]);

  // Helper function to check if a label is a duplicate
  const isDuplicateLabel = (index, labels) => {
    const currentLabel = labels[index]?.trim().toLowerCase();
    if (!currentLabel) return false;
    return labels.some((label, i) =>
      i !== index && label.trim().toLowerCase() === currentLabel
    );
  };

  // Update scalePointsArray when labels change
  const handleLabelChange = (index, value) => {
    const newLabels = [...scaleLabels];
    newLabels[index] = value;
    setScaleLabels(newLabels);

    // Update scalePointsArray with sequential values
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

    // Reorder the labels
    const newLabels = [...scaleLabels];
    const draggedLabel = newLabels[draggedIndex];
    newLabels.splice(draggedIndex, 1);
    newLabels.splice(index, 0, draggedLabel);
    setScaleLabels(newLabels);

    // Update scalePointsArray with sequential values based on new order
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

  const handleSubmit = async () => {
    // Validate all fields using inline validation
    const validation = validateAllFields(formData);

    // Additional validation for scale labels
    let hasScaleLabelErrors = false;
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

    // Validate scale points match scale labels
    if (formData.scalePointsArray?.length > 0 &&
        parseInt(formData.scalePoints) !== formData.scalePointsArray.length) {
      setFieldError('points', `Scale points (${formData.scalePoints}) doesn't match labels (${formData.scalePointsArray.length})`);
      hasScaleLabelErrors = true;
    }

    if (!validation.isValid || hasScaleLabelErrors) {
      return;
    }

    const metricValues = buildQualitativeMetricValues(formData, availableUnderlyingFeatures, availableTargetFeatures);

    const completeFormData = {
      ...formData,
      definition: 'redudant remains placeholder',
      type: 'qualitative',
      preSelectedEventIds: preservedData?.preSelectedEventIds || [],
      metric_values: metricValues,
      event_mappings: preservedData?.preSelectedEventIds?.map(eventId => ({ event_id: eventId })) || []
    };

    await onComplete(completeFormData);
  };

  return (
      <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg w-full">
       {/* Purpose Box - Added as per wireframe */}
         <div className="mb-6 bg-b7efff rounded-2xl border-2 border-purple-300 p-6 shadow-md">
           <div className="flex items-start">
              <div>
                <p className="text-gray-700">
                  This is the Create Metric page for a Qualitative Metric. On this page you can create your own qualitative metric to audit the AI Application on. It allows you to define and customise a metric by filling in all of the fields below, thereafter you can see a visual preview of your created metric. Once you have done this, you can choose to assign an instigator-created event or create your own if no event is yet assigned. You can save the qualitative metric by clicking the Save Qualitative Metric button, or go back without saving by clicking the Return to Assign Metric to Event Without Saving or Return to Audit Criteria Overview Without Saving. 
                </p>
              </div>
            </div>
          </div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6 pb-4 border-b border-purple-200">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Create New Qualitative Metric</h1>
          <p className="text-base text-gray-600">
            {showBackToAssignment 
              ? 'Fill in the details below and return to assign events'
              : 'Fill in the details below to create a new qualitative metric'}
          </p>
          {preservedData && (
            <p className="text-base text-blue-600 mt-1">
              ✓ Form data restored {preservedData.preSelectedEventIds?.length > 0 && `(${preservedData.preSelectedEventIds.length} events selected)`}
            </p>
          )}
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
            className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors ${
              hasFieldError('name') ? 'border-red-500 focus:border-red-600' : 'border-purple-200 focus:border-purple-400'
            }`}
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
            className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors ${
              hasFieldError('points') ||
              (formData.scalePointsArray?.length > 0 &&
              parseInt(formData.points) !== formData.scalePointsArray.length)
                ? 'border-red-500 focus:border-red-600'
                : 'border-purple-200 focus:border-purple-400'
            }`}
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
            onChange={handleUnderlyingFeaturesChange}
            placeholder="Select features..."
            options={underlyingFeatureOptions}
            allowCreate={true}
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
            className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors resize-none ${
              hasFieldError('description') ? 'border-red-500 focus:border-red-600' : 'border-purple-200 focus:border-purple-400'
            }`}
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
            className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors resize-none ${
              hasFieldError('reason') ? 'border-red-500 focus:border-red-600' : 'border-purple-200 focus:border-purple-400'
            }`}
          />
          {hasFieldError('reason') && (
            <p className="text-base text-red-600 mt-1">{getFieldError('reason')}</p>
          )}
        </div>

        <div className="col-span-2">
          <label className="block text-base font-medium text-gray-700 mb-1">Scale Labels</label>
          <label className="block text-base text-gray-500 mb-2">
            Decide how to label each point on your scale and choose which value on the scale is still acceptable for this metric by checking the box next to it
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
                      draggable
                      onDragStart={() => handleDragStart(index)}
                      onDragOver={(e) => handleDragOver(e, index)}
                      onDragEnd={handleDragEnd}
                      className="flex flex-col gap-1 mb-2"
                    >
                      <div
                        className={`flex items-center gap-2 bg-purple-50 border-2 rounded-xl p-2 cursor-move transition-all ${
                          hasDuplicate ? 'border-red-400 bg-red-50' :
                          formData.threshold === label && label ? 'border-green-400 bg-green-50' : 'border-purple-200'
                        } ${
                          draggedIndex === index ? 'opacity-50 scale-95' : 'hover:border-purple-300'
                        }`}
                      >
                        <GripVertical className="w-4 h-4 text-gray-400 flex-shrink-0" />
                        <span className="text-base font-bold text-purple-600 bg-purple-200 rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0">
                          {index + 1}
                        </span>
                        <input
                          type="radio"
                          name="threshold"
                          checked={formData.threshold === label && label !== ''}
                          onChange={() => handleInputChange('threshold', label)}
                          disabled={!label.trim()}
                          className="w-5 h-4 text-green-600 border-gray-300 focus:ring-green-500 flex-shrink-0 mx-1"
                          title="Set as threshold"
                        />
                        <input
                          type="text"
                          placeholder={`Label ${index + 1}`}
                          value={label}
                          onChange={(e) => handleLabelChange(index, e.target.value)}
                          className={`flex-1 min-w-0 px-3 py-1.5 border-2 rounded-xl focus:outline-none transition-colors text-base ${
                            hasDuplicate ? 'border-red-400 focus:border-red-500' : 'border-purple-200 focus:border-purple-400'
                          }`}
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

      {/* Metric Preview - Full Width Below Columns */}
      <div className="mt-6">
        <label className="block text-base font-medium text-gray-700 mb-2">Metric Preview</label>
        <div className="bg-white border-2 border-purple-200 rounded-2xl p-6">
          <div className="text-center">
            <div className="font-medium text-gray-800 mb-6 text-lg">
              {formData.name || '<Metric Name>'}
            </div>

            {/* Scale visualization */}
            {formData.scalePointsArray?.length > 0 ? (
              <div className="w-full">
                <div className="text-base text-gray-500 mb-6">Scale Preview:</div>
                
                <div className="relative flex flex-col items-center">
                  {/* Gradient Connecting Line */}
                  <div 
                    className="absolute top-4 h-3 bg-gradient-to-r from-purple-200 to-purple-400 rounded-full"
                    style={{ 
                      // This ensures the line starts at the center of the first circle and ends at the last
                      width: `calc(100% - ${100 / formData.scalePointsArray.length}%)`,
                      left: `${50 / formData.scalePointsArray.length}%` 
                    }}
                  />

                  <div className="relative w-full flex items-start justify-between">
                    {formData.scalePointsArray.map((item, index) => {
                      const isThreshold = formData.threshold === item.label;
                      
                      return (
                        <div key={index} className="flex-1 flex flex-col items-center z-10">
                          {/* Circle Badge */}
                          <div className={`w-10 h-10 rounded-full text-white text-base font-bold flex items-center justify-center transition-all duration-300 ring-4 ring-white shadow-base border-3 border-purple-100 ${
                            isThreshold 
                                ? 'bg-purple-400 scale-110 text-purple-900' 
                                : 'bg-purple-500 scale-110'
                          }`}>
                            {index + 1}
                          </div>
                          
                          {/* Label Text */}
                          <div className="mt-3">
                            <div className={`text-base font-medium ${isThreshold ? 'text-purple-700 font-bold' : 'text-gray-600'}`}>
                              {!item.label ? `<Label ${index+1}>` : item.label}
                            </div>
                            {isThreshold && item.label=== null && (
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

      {/* Submit Button */}
      <div className="flex justify-between items-center mt-8 pt-6 border-t border-purple-200">
        <button
          onClick={showBackToAssignment ? onBackToAssignment : onCancel}
          className="flex items-center gap-2 px-4 py-2 text-gray-600 border-2 border-purple-200 rounded-full hover:bg-purple-200 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          {showBackToAssignment ? 'Return to Assign Metric without saving' : 'Return to Audit Criteria without saving'}
        </button>
        <button
          onClick={handleSubmit}
          className="bg-purple-100 hover:bg-purple-200 px-4 py-2 rounded-full text-base font-semibold transition-colors border-2 border-purple-200"
        >
          Save Qualitative Metric
        </button>
      </div>
    </div>
  );
};

export default QualitativeMetricForm;