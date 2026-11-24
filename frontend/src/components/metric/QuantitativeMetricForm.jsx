import React from 'react';
import { ArrowLeft, ChevronDown } from 'lucide-react';
import CreatableMultiSelect from '../ui/creatablemultiselect';
import { useFormLogic } from '../../hooks/useFormLogic';
import { useFormValidation } from '../../hooks/useFormValidation';
import { buildQuantitativeMetricValues } from '../../utils/formUtils';
import { useToast } from '../../hooks/useToast';

const QuantitativeMetricForm = ({
  onCancel,
  onComplete,
  showBackToAssignment = false,
  onBackToAssignment,
  preservedData = null,
  availableUnderlyingFeatures = [],
  availableTargetFeatures = [],
}) => {

  const initialFormData = {
    name: '',
    description: '',
    definition: '',
    targetFeatures: [],
    underlyingFeatures: [],
    featureGroups: 'Minimum of 2',
    featureRanges: {},
    threshold: '',
    reason: '',
    ...preservedData
  };

  const toast = useToast();

  const {
    formData,
    validateForm,
    handleInputChange,
    handleUnderlyingFeaturesChange,
    handleFeatureRangeChange
  } = useFormLogic(initialFormData, preservedData);

  // Validation rules for inline validation
  const validationRules = {
    name: { required: true, message: 'Metric name is required' },
    description: { required: true, message: 'Description is required' },
    // definition: { required: true, message: 'Definition is required' },
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
    setFieldError
  } = useFormValidation(validationRules);

  const targetFeatureOptions = availableTargetFeatures.map(f => f.target_feature || f.name || `Feature ${f.id}`);
  const underlyingFeatureOptions = availableUnderlyingFeatures.map(f => f.feature_name || f.name || `Feature ${f.id}`);

  const handleSubmit = async () => {
    // Validate all fields using inline validation
    const validation = validateAllFields(formData);

    if (!validation.isValid) {
       toast.error("Validation failed. Make sure you filed all the fields");
      return;
    }

    const metricValues = buildQuantitativeMetricValues(formData, availableUnderlyingFeatures, availableTargetFeatures);

    const completeFormData = {
      ...formData,
      type: 'quantitative',
      definition: 'redudant remians placeholder',
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
                This is the Create Metric page for a Quantitative Metric. On this page you can create your own quantitative metric to audit the AI Application on. It allows you to define and customise a metric by filling in all of the fields below, thereafter you can see a visual preview of your created metric. Once you have done this, you can choose to assign an instigator-created event or create your own if no event is yet assigned. You can save the quantitiave metric by clicking the Save Quantitative Metric button, or go back without saving by clicking the Return to Assign Quantitative Metric to Event Without Saving or Return to Audit Criteria Overview Without Saving 
              </p>
          </div>
        </div>
      </div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6 pb-4 border-b border-purple-200">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Create Quantitative Metric</h1>
          <p className="text-base text-gray-600">
            {showBackToAssignment 
              ? 'Fill in the details below and return to assign events'
              : 'Fill in the details below to create a new quantitative metric'}
          </p>
          {preservedData && (
            <p className="text-base text-blue-600 mt-1">
              ✓ Form data restored {preservedData.preSelectedEventIds?.length > 0 && `(${preservedData.preSelectedEventIds.length} events selected)`}
            </p>
          )}
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
            className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors ${
              hasFieldError('name') ? 'border-red-500 focus:border-red-600' : 'border-purple-200 focus:border-purple-400'
            }`}
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
            className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors ${
              hasFieldError('threshold') ? 'border-red-500 focus:border-red-600' : 'border-purple-200 focus:border-purple-400'
            }`}
          />
          {hasFieldError('threshold') && (
            <p className="text-base text-red-600 mt-1">{getFieldError('threshold')}</p>
          )}
        </div>
      </div>
      {/* Row 2 Metric Description & Reason | Distinguish Factor | Number of Groups*/}
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
              className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors resize-none ${
                hasFieldError('description') ? 'border-red-500 focus:border-red-600' : 'border-purple-200 focus:border-purple-400'
              }`}
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
              className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors resize-none ${
                hasFieldError('reason') ? 'border-red-500 focus:border-red-600' : 'border-purple-200 focus:border-purple-400'
              }`}
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
                className="w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors border-purple-200 focus:border-purple-400"
              />
            </div>
          </div>
        
          <div className="col-span-1 mt-6">
            <label className="block text-base font-medium text-gray-700 mb-1">Define Distinguishing Factor Groups *</label>
            <label className="block text-base text-gray-500 mb-2">Decide the values, or range, of each group you want to compare</label>
            {formData.underlyingFeatures.length === 0 ? (
              <div className="text-base text-gray-400 italic p-4 border-2 border-dashed border-gray-200 rounded-2xl text-center">
                Select Distinguishing Factors to define their group ranges
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-4">
                {formData.underlyingFeatures.map((feature) => {
                  // Determine the number of groups to render
                  const numGroups = formData.featureGroups === 'Minimum of 2'
                    ? 2
                    : parseInt(formData.featureGroups);

                  // Find the feature object to get range information
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
                              value={formData.featureRanges[feature]?.[groupKey] || ''}
                              onChange={(e) => handleFeatureRangeChange(feature, groupKey, e.target.value)}
                              className="w-full bg-purple px-4 py-3 border-2 border-purple-200 rounded-2xl focus:border-purple-400 focus:outline-none transition-colors"
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
              Target: {formData.targetFeatures.length > 0 ? formData.targetFeatures.join(', ') : '<Targets>'}
            </div>
            <div className="text-base text-gray-500 mt-1">
              Distinguishing Factors: {formData.underlyingFeatures.length > 0 ? formData.underlyingFeatures.join(', ') : '<Distinguishing Factors>'}
            </div>
            <div className="w-full h-1 bg-gray-200 rounded mt-2 mb-2"></div>
            <div className="text-base">Threshold: {formData.threshold || '<Threshold>'}</div>
            {formData.underlyingFeatures.length > 0 && (
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
                              {formData.featureRanges[feature]?.[groupKey] || `Group ${index + 1}`}
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
          Save Quantitative Metric
        </button>
      </div>
    </div>
  );
};

export default QuantitativeMetricForm;