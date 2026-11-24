import React, { useState, useEffect } from 'react';
import { ArrowLeft } from 'lucide-react';
import MetricAssignmentModal from '../popUp/metricAssignment';
import CreatableMultiSelect from '../ui/creatablemultiselect';
import RangeSlider from '../ui/RangeSlider';
import { useFormLogic } from '../../hooks/useFormLogic';
import { useFormValidation } from '../../hooks/useFormValidation';
import { buildEventApiPayload } from '../../utils/formUtils';
import { eventsAPI } from '../../api/apiService';

export const CreateEventForm = ({
  onCancel,
  onComplete,
  eventCategories = [],
  entities = [],
  availableMetrics = [],
  showBackToAssignment = false,
  auditId,
  parentContext = null,
  preservedMetricSelections = [],
  onMetricSelectionChange = null,
  availableUnderlyingFeatures = [],
  availableTargetFeatures = [],
  toast = null, // Optional toast for notifications
  updateVisibility
}) => {
  // Helper for notifications - uses toast if available, falls back to alert
  const notify = {
    success: (message) => toast ? toast.success(message) : alert(message),
    error: (message) => toast ? toast.error(message) : alert(message),
    warning: (message) => toast ? toast.warning(message) : alert(message),
    info: (message) => toast ? toast.info(message) : alert(message)
  };
  const [showMetricModal, setShowMetricModal] = useState(false);
  const [savedFormData, setSavedFormData] = useState(null);
  const [currentMetricSelections, setCurrentMetricSelections] = useState(preservedMetricSelections);

  // Entity state (no popup needed anymore)
  const [availableEntities, setAvailableEntities] = useState(entities);
  const [entityDetails, setEntityDetails] = useState({}); // Store num_individuals for each entity

  // Category state - manage locally to allow updates
  const [availableCategories, setAvailableCategories] = useState(eventCategories);

  // Sync categories when prop changes
  useEffect(() => {
    setAvailableCategories(eventCategories);
  }, [eventCategories]);

  // Sync entities when prop changes
  useEffect(() => {
    setAvailableEntities(entities);
  }, [entities]);

  const initialFormData = {
    name: '',
    description: '',
    categories: [],
    entities: [],
    entityDetails: {}, // Add entityDetails to form data
    cause: '',
    valence: '',
    likelihood: 50,
    magnitude: 50,
    reason: ''
  };

  const {
    formData,
    validateForm,
    handleInputChange,
    handleSliderChange
  } = useFormLogic(initialFormData);

  // Validation rules for inline validation
  const validationRules = {
    name: { required: true, message: 'Event name is required' },
    description: { required: true, message: 'Description is required' },
    categories: { required: true, message: 'At least one category is required' },
    entities: { required: true, message: 'At least one entity is required' },
    cause: { required: true, message: 'Cause is required' },
    valence: { required: true, message: 'Valence is required' },
    reason: { required: true, message: 'Reason is required' }
  };

  const {
    touchField,
    validateAndSetError,
    validateAllFields,
    getFieldError,
    hasFieldError
  } = useFormValidation(validationRules);

  const categoryOptions = availableCategories.map(category =>
    category.event_name || category.name || category
  );

  const entityOptions = availableEntities.map(entity =>
    entity.name || entity.entity_name || entity
  );

  // Handle entity creation - create via API and get the ID
  const handleEntityCreate = async (newEntityName) => {
    try {
      const response = await eventsAPI.createEntity(newEntityName, 0, parseInt(auditId));

      // console.log('Entity creation response:', response);

      const updatedEntityDetails = { ...entityDetails, [newEntityName]: 0 };
      setEntityDetails(updatedEntityDetails);

      // Add to available entities list with the ID from response
      // API can return id, entity_id, or entities_id
      const entityId = response.id || response.entity_id || response.entities_id;

      const newEntity = {
        id: entityId,
        entity_id: entityId,
        entities_id: entityId,
        name: newEntityName,
        entity_name: newEntityName,
        num_individuals: 0
      };

      setAvailableEntities(prev => [...prev, newEntity]);

      // Add to form data entities
      const updatedEntities = [...formData.entities, newEntityName];
      handleInputChange('entities', updatedEntities);
      // Clear validation error since we now have a valid value
      validateAndSetError('entities', updatedEntities);

      // Also update entityDetails in formData
      handleInputChange('entityDetails', updatedEntityDetails);

      // console.log('Entity created with ID:', entityId);
    } catch (error) {
      console.error('Error creating entity:', error);
      notify.error(`Failed to create entity: ${error.message || 'Unknown error'}`);
    }
  };

  const handleSubmit = async () => {
    // Validate all fields using inline validation
    const inlineValidation = validateAllFields(formData);

    if (!inlineValidation.isValid) {
      return;
    }

    const validation = validateForm(['name', 'description', 'categories', 'entities', 'cause', 'valence', 'reason']);

    if (!validation.isValid) {
      notify.error(`Please fill in all required fields: ${validation.missingFields.join(', ')}`);
      return;
    }

    const eventDataForAPI = {
      ...formData, // Include all form data (including entityDetails)
      eventName: formData.name,
      selectedMetricIds: formData.selectedMetricIds || []
    };

    if (parentContext === 'metric-assignment') {
      // Pass updated categories and entities with the event data
      await onComplete({
        ...eventDataForAPI,
        _updatedCategories: availableCategories,
        _updatedEntities: availableEntities
      });
      return;
    }

    setSavedFormData(eventDataForAPI);
    setShowMetricModal(true);
  };

  const handleMetricAssignmentComplete = (eventWithMetrics) => {
    setShowMetricModal(false);
    setSavedFormData(null);
    // Pass updated categories and entities with the event data
    onComplete({
      ...eventWithMetrics,
      _updatedCategories: availableCategories,
      _updatedEntities: availableEntities
    });
  };

  const handleMetricSelectionChange = (selectedMetricIds) => {
    setCurrentMetricSelections(selectedMetricIds);
    if (onMetricSelectionChange) {
      onMetricSelectionChange(selectedMetricIds);
    }
  };

  // If showing metric assignment modal, render it instead of the form
  if (showMetricModal && savedFormData && parentContext !== 'metric-assignment') {
    return (
      <MetricAssignmentModal
        eventData={savedFormData}
        metrics={availableMetrics.metrics}
        onClose={() => setShowMetricModal(false)}
        onBack={(currentSelections) => {
          setCurrentMetricSelections(currentSelections);
          setShowMetricModal(false);
        }}
        onComplete={handleMetricAssignmentComplete}
        auditId={auditId}
        initialSelectedMetrics={currentMetricSelections}
        onSelectionChange={handleMetricSelectionChange}
        availableUnderlyingFeatures={availableUnderlyingFeatures}
        availableTargetFeatures={availableTargetFeatures}
        updateVisibility={updateVisibility}
      />
    );
  }

  return (
    <div className="bg-E2DFFF rounded-3xl border-2 border-purple-200 p-6 shadow-lg w-full">
    {/* Purpose Box - Added as per wireframe */}
    <div className="mb-6 bg-b7efff rounded-2xl border-2 border-purple-300 p-6 shadow-md">
      <div className="flex items-start" >
        <div>
          <p className="text-gray-700">
           This is the Create Event page. On this page you can create your own event to audit the AI Application on. It allows you to define and customise an event by filling in all of the fields below. Once you have done this, you can choose to assign an instigator-created metric or create your own if no metric is yet assigned. You can save the event by clicking the Save Event button, or go back without saving by clicking the Return to Assign Event to Metric Without Saving or Return to Audit Criteria Overview Without Saving.        
          </p>
        </div>
      </div>
    </div>

    {/* Header */}
      <div className="flex items-center gap-3 mb-6 pb-4 border-b border-purple-200">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Create New Event</h1>
          <p className="text-base text-gray-600">
            {showBackToAssignment 
              ? 'Fill in the details below and return to metric assignment'
              : 'Fill in the details below to create a new event.'
            }
          </p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-8">
        {/* Left Column */}
        <div className="space-y-6">
          <div>
            <label className="block text-base font-medium text-gray-700 mb-1">Event Name *</label>
            <label className="block text-base text-gray-500 mb-2">Decide on a name that represents what can or does happen when using the AI Application</label>
            <input
              type="text"
              placeholder="Event Name"
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
            <label className="block text-base font-medium text-gray-700 mb-1">Event Description *</label>
            <label className="block text-base text-gray-500 mb-2">Describe what can or does happen when using the AI Application</label>
            <textarea
              placeholder="Event Description"
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
              className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors ${
                hasFieldError('description') ? 'border-red-500 focus:border-red-600' : 'border-purple-200 focus:border-purple-400'
              }`}
            />
            {hasFieldError('description') && (
              <p className="text-base text-red-600 mt-1">{getFieldError('description')}</p>
            )}
          </div>

          <CreatableMultiSelect
            label="Categories *"
            helpText="Choose or create which thematic group(s) you could sort this event into"
            value={formData.categories}
            onChange={(value) => {
              handleInputChange('categories', value);
              validateAndSetError('categories', value);
            }}
            onBlur={() => {
              touchField('categories');
              validateAndSetError('categories', formData.categories);
            }}
            onCreateNew={async (newCategoryName) => {
              try {
                // Create new category via API
                const response = await eventsAPI.createEventCategory({
                  event_name: newCategoryName,
                  description: `User-created category: ${newCategoryName}`,
                  audit_id: parseInt(auditId)
                });

                // console.log('Category creation response:', response);

                // Add to available categories list with the ID from response
                const newCategory = {
                  id: response.category_id,
                  category_id: response.category_id,
                  event_name: newCategoryName,
                  name: newCategoryName,
                  description: `User-created category: ${newCategoryName}`,
                  source: 'user_specific'
                };

                setAvailableCategories(prev => [...prev, newCategory]);

                // Add to form data categories
                const updatedCategories = [...formData.categories, newCategoryName];
                handleInputChange('categories', updatedCategories);
                // Clear validation error since we now have a valid value
                validateAndSetError('categories', updatedCategories);

                // console.log('Category created with ID:', response.category_id);
              } catch (error) {
                console.error('Error creating category:', error);
                notify.error(`Failed to create category: ${error.message || 'Unknown error'}`);
              }
            }}
            placeholder="Select or create categories..."
            options={categoryOptions}
            allowCreate={true}
            hasError={hasFieldError('categories')}
            errorMessage={getFieldError('categories')}
          />
        </div>

        {/* Middle Column */}
        <div className="space-y-6">
          <CreatableMultiSelect
            label="Entities *"
            helpText="Choose or create who is being impacted by the event"
            value={formData.entities}
            onChange={(value) => {
              handleInputChange('entities', value);
              validateAndSetError('entities', value);
            }}
            onBlur={() => {
              touchField('entities');
              validateAndSetError('entities', formData.entities);
            }}
            onCreateNew={handleEntityCreate}
            placeholder="Select entities..."
            options={entityOptions}
            allowCreate={true}
            hasError={hasFieldError('entities')}
            errorMessage={getFieldError('entities')}
          />

          <div>
            <label className="block text-base font-medium text-gray-700 mb-1">Cause *</label>
            <label className="block text-base text-gray-500 mb-2">Describe what could lead to this event happening</label>
            <textarea
              placeholder="Cause"
              value={formData.cause}
              onChange={(e) => {
                handleInputChange('cause', e.target.value);
                validateAndSetError('cause', e.target.value);
              }}
              onBlur={() => {
                touchField('cause');
                validateAndSetError('cause', formData.cause);
              }}
              rows={4}
              className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors ${
                hasFieldError('cause') ? 'border-red-500 focus:border-red-600' : 'border-purple-200 focus:border-purple-400'
              }`}
            />
            {hasFieldError('cause') && (
              <p className="text-base text-red-600 mt-1">{getFieldError('cause')}</p>
            )}
          </div>

          <div>
            <label className="block text-base font-medium text-gray-700 mb-1">Why are you adding this event? *</label>
            <label className="block text-base text-gray-500 mb-2">Describe your reasoning for adding this event</label>
            <textarea
              placeholder="Why this event is being added"
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
              className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors ${
                hasFieldError('reason') ? 'border-red-500 focus:border-red-600' : 'border-purple-200 focus:border-purple-400'
              }`}
            />
            {hasFieldError('reason') && (
              <p className="text-base text-red-600 mt-1">{getFieldError('reason')}</p>
            )}
          </div>
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          <div>
            <label className="block text-base font-medium text-gray-700 mb-1">Valence *</label>
            <label className="block text-base text-gray-500 mb-2">Decide if the event positive or negative</label>
            <div className={`space-y-3 p-3 rounded-2xl border-2 ${
              hasFieldError('valence') ? 'border-red-500' : 'border-transparent'
            }`}>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="radio"
                  name="valence"
                  value="positive"
                  checked={formData.valence === 'positive'}
                  onChange={(e) => {
                    handleInputChange('valence', e.target.value);
                    validateAndSetError('valence', e.target.value);
                  }}
                  className="w-4 h-4 text-purple-600 border-2 border-purple-200"
                />
                <span className="text-base">Positive</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="radio"
                  name="valence"
                  value="negative"
                  checked={formData.valence === 'negative'}
                  onChange={(e) => {
                    handleInputChange('valence', e.target.value);
                    validateAndSetError('valence', e.target.value);
                  }}
                  className="w-4 h-4 text-purple-600 border-2 border-purple-200"
                />
                <span className="text-base">Negative</span>
              </label>
            </div>
            {hasFieldError('valence') && (
              <p className="text-base text-red-600 mt-1">{getFieldError('valence')}</p>
            )}
          </div>

          <RangeSlider
            label="Likelihood *"
            value={formData.likelihood}
            helptext="Decide how likely you think it is that the event might happen (0-Not at all, 100=certainly)"
            onChange={(val) => handleSliderChange('likelihood', val)}
          />

          <RangeSlider
            label="Magnitude *"
            value={formData.magnitude}
            helptext="Decide how big you think the impact of the event would be if it happens (0=none, 100=very large)"
            onChange={(val) => handleSliderChange('magnitude', val)}
          />
        </div>
      </div>

      {/* Submit Button */}
      <div className="flex justify-between items-center mt-8 pt-6 border-t border-purple-200">
        <button
          onClick={onCancel}
          className="flex items-center gap-2 px-4 py-2 text-gray-600 border-2 border-purple-200 rounded-full hover:bg-purple-200 transition-colors"
        >
          Return to Audit Criteria without Saving
        </button>
        <button
          onClick={handleSubmit}
          className="bg-purple-100 hover:bg-purple-200 px-4 py-2 rounded-full text-base font-semibold transition-colors border-2 border-purple-200"
        >
          {parentContext === 'metric-assignment' 
            ? 'Return to Metric Assignment'
            : 'Save Event'
          }
        </button>
      </div>

    </div>
  );
};

export default CreateEventForm;