import React, { useState, useEffect } from 'react';
import { ArrowLeft } from 'lucide-react';
import CreatableMultiSelect from '../ui/creatablemultiselect';
import RangeSlider from '../ui/RangeSlider';
import { useFormLogic } from '../../hooks/useFormLogic';
import { useFormValidation } from '../../hooks/useFormValidation';
import { buildEventApiPayload, stringToArray } from '../../utils/formUtils';
import { eventsAPI } from '../../api/apiService';

export const EditEventForm = ({
  event,
  onCancel,
  onSave,
  eventCategories = [],
  entities = [],
  editValues = false,
  isReadOnly = false,
  toast = null // Optional toast for notifications
}) => {
  // Helper for notifications - uses toast if available, falls back to alert
  const notify = {
    success: (message) => toast ? toast.success(message) : alert(message),
    error: (message) => toast ? toast.error(message) : alert(message),
    warning: (message) => toast ? toast.warning(message) : alert(message),
    info: (message) => toast ? toast.info(message) : alert(message)
  };
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

  // Get audit ID from event
  const auditId = event?.audit_id || event?.auditId ||
                 sessionStorage.getItem('auditId') ||
                 (typeof window !== 'undefined' && window.location.pathname.match(/\/\d+/)?.[0]?.slice(1)) ||
                 1;
  // Initialize form data from event
  const initialFormData = event ? {
    eventName: event.name || '',
    eventDescription: event.description || '',
    categories: stringToArray(event.category),
    entities: stringToArray(event.entities),
    cause: event.cause || '',
    valence: event.valence?.toLowerCase() || '',
    likelihood: typeof event.likelihood === 'string' ?
      parseInt(event.likelihood.replace(/\D/g, '')) || null :
      (event.likelihood !== null && event.likelihood !== undefined ? event.likelihood : null),
    magnitude: typeof event.magnitude === 'string' ?
      parseInt(event.magnitude.replace(/\D/g, '')) || null :
      (event.magnitude !== null && event.magnitude !== undefined ? event.magnitude : null),
    reason: event.reason || ''
  } : {};

  const {
    formData,
    hasChanges,
    getChanges,
    validateForm,
    handleInputChange,
    handleSliderChange
  } = useFormLogic(initialFormData, event);

  // Validation rules for inline validation
  const validationRules = {
    eventName: { required: true, message: 'Event name is required' },
    eventDescription: { required: true, message: 'Description is required' },
    categories: { required: true, message: 'At least one category is required' },
    entities: { required: true, message: 'At least one entity is required' },
    cause: { required: true, message: 'Cause is required' },
    valence: { required: true, message: 'Valence is required' }
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

      setEntityDetails({ ...entityDetails, [newEntityName]: 0 });

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

      // console.log('Entity created with ID:', entityId);
    } catch (error) {
      console.error('Error creating entity:', error);
      notify.error(`Failed to create entity: ${error.message || 'Unknown error'}`);
    }
  };

  const validateApiPayload = (payload, changes) => {
    const errors = [];
    
    if (!payload.audit_id || isNaN(payload.audit_id)) {
      errors.push('Invalid audit_id');
    }
    
    if (changes.eventName && (!payload.name || payload.name.trim().length === 0)) {
      errors.push('Name is required');
    }
    
    if (changes.eventDescription && (!payload.description || payload.description.trim().length === 0)) {
      errors.push('Description is required');
    }
    
    if (changes.likelihood && (payload.likelihood < 0 || payload.likelihood > 1)) {
      errors.push('Likelihood must be between 0 and 1');
    }
    
    if (changes.magnitude && (payload.magnitude < 0 || payload.magnitude > 1)) {
      errors.push('Magnitude must be between 0 and 1');
    }
    
    if (changes.valence && (payload.valence !== 1.0 && payload.valence !== -1.0)) {
      errors.push('Valence must be 1.0 or -1.0');
    }
    
    return {
      isValid: errors.length === 0,
      errors
    };
  };

  const handleSave = () => {
    if (!hasChanges()) {
      notify.info('No changes detected. Nothing to save.');
      return;
    }

    // In "Edit Event Values" mode only valence/likelihood/magnitude are editable,
    // so only require those. The full edit form requires every field.
    const requiredFields = editValues
      ? ['eventName', 'eventDescription', 'categories', 'entities', 'cause', 'valence']
      : ['valence'];

    // Validate the relevant fields using inline validation
    const inlineValidation = validateAllFields(formData, requiredFields);

    if (!inlineValidation.isValid) {
      return;
    }

    const changes = getChanges();
    const validation = validateForm(requiredFields);

    if (!validation.isValid) {
      notify.error(`Please fill in all required fields: ${validation.missingFields.join(', ')}`);
      return;
    }

    // Get audit ID from various sources
    const auditId = event.audit_id || event.auditId || 
                   sessionStorage.getItem('auditId') ||
                   (typeof window !== 'undefined' && window.location.pathname.match(/\/\d+/)?.[0]?.slice(1)) ||
                   1;

    // Build API payload with only changed fields
    // Use updated categories/entities from local state (includes newly created ones with IDs)
    const apiPayload = buildEventApiPayload(formData, auditId, changes, availableCategories, availableEntities);

    // Add metadata for user-created events
    if (event.isUserCreated) {
      apiPayload.is_user_defined = true;
      apiPayload.is_template = false;
    } else {
      apiPayload.is_user_defined = false;
    }

    const payloadValidation = validateApiPayload(apiPayload, changes);
    if (!payloadValidation.isValid) {
      notify.error(`Validation failed: ${payloadValidation.errors.join(', ')}`);
      return;
    }

    // Create response for parent component
    const updatedEvent = {
      ...event,
      name: formData.eventName,
      description: formData.eventDescription,
      category: Array.isArray(formData.categories) ? formData.categories.join(', ') : formData.categories,
      entities: Array.isArray(formData.entities) ? formData.entities.join(', ') : formData.entities,
      cause: formData.cause,
      valence: formData.valence,
      likelihood: formData.likelihood,
      magnitude: formData.magnitude,
      reason: formData.reason,
      _apiPayload: apiPayload,
      _changes: changes,
      _hasChanges: true
    };

    onSave(updatedEvent);
  };

  if (!event) {
    return (
      <div className="bg-white rounded-3xl border-2 border-purple-200 p-6 shadow-lg">
        <p className="text-center text-gray-500">No event selected for editing</p>
      </div>
    );
  }

  const changesExist = hasChanges();

  // PARTIAL EDIT MODE - For non-user-created events (only magnitude, likelihood, valence editable)
  if (!editValues) {
    return (
      <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg w-full">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6 pb-4 border-b border-purple-200">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Edit Event Values</h1>
            <p className="text-base text-gray-600">
              Update your assessment of the impact you believe this event might have.
              {changesExist && <span className="ml-2 text-orange-600 text-base">(Changes detected)</span>}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-8">
          {/* Left Column - Read-only fields */}
          <div>
            <div>
            
              <div className="space-y-2 text-base text-gray-700 mb-4">
                <div>
                  <strong>Event Name:</strong> {formData.eventName || 'N/A'}
                </div>
                <div>
                  <strong>Event Description:</strong> {formData.eventDescription || 'N/A'}
                </div>
                <div>
                  <strong>Event Category:</strong>
                  {formData.categories && formData.categories.length > 0 ? (
                    <ul className="list-disc ml-6 mt-1">
                      {(Array.isArray(formData.categories) ? formData.categories : [formData.categories]).map((category, idx) => (
                        <li key={idx}>{category}</li>
                      ))}
                    </ul>
                  ) : (
                    ' N/A'
                  )}
                </div>
                <div>
                  <strong>Event Creator:</strong> {event.creator || 'N/A'}
                </div>
                <div>
                  <strong>Valence:</strong> {
                    formData.valence
                      ? formData.valence.charAt(0).toUpperCase() + formData.valence.slice(1)
                      : 'N/A'
                  }
                </div>
                <div>
                  <strong>Magnitude of Impact:</strong> {
                    formData.magnitude !== null && formData.magnitude !== undefined
                      ? `${formData.magnitude}%`
                      : 'Not defined'
                  }
                </div>
                <div>
                  <strong>Likelihood:</strong> {
                    formData.likelihood !== null && formData.likelihood !== undefined
                      ? `${formData.likelihood}%`
                      : 'Not defined'
                  }
                </div>
                <div>
                  <strong>Cause:</strong> {formData.cause || 'N/A'}
                </div>
                <div>
                  <strong>Associated Entities:</strong>
                  {formData.entities && formData.entities.length > 0 ? (
                    <ul className="list-disc ml-6 mt-1">
                      {(Array.isArray(formData.entities) ? formData.entities : [formData.entities]).map((entity, idx) => (
                        <li key={idx}>{entity}</li>
                      ))}
                    </ul>
                  ) : (
                    ' N/A'
                  )}
                </div>
                <div>
                  <strong>Why Event was added:</strong> {formData.reason || 'N/A'}
                </div>
              </div>
            </div>
          </div>

          {/* Right Column - Editable fields */}
          <div className="space-y-6">
            {/* Visual Indicator Box with Editable Fields */}
            <div className="bg-purple-50 border-2 border-purple-300 rounded-2xl p-6">
              <div className="mb-4">
                <p className="text-base font-medium text-purple-900">
                  Editable Fields
                </p>
                <p className="text-base mt-1">
                  Adjust the values to mirror your assessment of the impact you believe this event might have.
                </p>
              </div>

              <div className="space-y-6">
                <div>
                  <label className="block text-base font-medium text-gray-700 mb-1">Valence</label>
                  <label className="block text-base text-gray-500 mb-2">Is the event positive or negative?</label>
                  <div className="space-y-3">
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="radio"
                        name="valence"
                        value="positive"
                        checked={formData.valence === 'positive'}
                        onChange={(e) => handleInputChange('valence', e.target.value)}
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
                        onChange={(e) => handleInputChange('valence', e.target.value)}
                        className="w-4 h-4 text-purple-600 border-2 border-purple-200"
                      />
                      <span className="text-base">Negative</span>
                    </label>
                  </div>
                </div>

                <RangeSlider
                  label="Likelihood"
                  value={formData.likelihood}
                  helptext="How likely do you think it is this event will happen? (0=not at all, 100=certainly)"
                  onChange={(val) => handleSliderChange('likelihood', val)}
                />

                <RangeSlider
                  label="Magnitude"
                  value={formData.magnitude}
                  helptext="What do you think the magnitude of the impact would be? (0=none, 100=very large)"
                  onChange={(val) => handleSliderChange('magnitude', val)}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Save Button */}
        <div className="flex justify-between items-center mt-8 pt-6 border-t border-gray-200">
          <button
            onClick={onCancel}
            className="flex items-center gap-2 px-4 py-2 text-gray-600 border-2 border-purple-200 rounded-full hover:bg-purple-200 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Return to Audit Criteria Overview without saving 
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
            {isReadOnly ? 'Read-Only Mode' : changesExist ? 'Save Changes' : 'No Changes to Save'}
          </button>
        </div>
      </div>
    );
  }

  // FULL EDIT MODE - For user-created events (all fields editable)
  return (
    <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg w-full">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6 pb-4 border-b border-purple-200">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Edit Event</h1>
          <p className="text-base text-gray-600">
            Update the details for: <span className="font-medium">{event.name}</span>
            {changesExist && <span className="ml-2 text-orange-600 text-base">(Changes detected)</span>}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-8">
        {/* Left Column */}
        <div className="space-y-6">
          <div>
            <label className="block text-base font-medium text-gray-700 mb-1">Event Name *</label>
            <label className="block text-base text-gray-500 mb-2">Choose a name for this event:</label>
            <input
              type="text"
              placeholder="<Event Name>"
              value={formData.eventName}
              onChange={(e) => {
                handleInputChange('eventName', e.target.value);
                validateAndSetError('eventName', e.target.value);
              }}
              onBlur={() => {
                touchField('eventName');
                validateAndSetError('eventName', formData.eventName);
              }}
              className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors ${
                hasFieldError('eventName') ? 'border-red-500 focus:border-red-600' : 'border-purple-200 focus:border-purple-400'
              }`}
            />
            {hasFieldError('eventName') && (
              <p className="text-base text-red-600 mt-1">{getFieldError('eventName')}</p>
            )}
          </div>

          <div>
            <label className="block text-base font-medium text-gray-700 mb-1">Event Description *</label>
            <label className="block text-base text-gray-500 mb-2">Can you describe what happens when this event occurs?</label>
            <textarea
              placeholder="<Event Description>"
              value={formData.eventDescription}
              onChange={(e) => {
                handleInputChange('eventDescription', e.target.value);
                validateAndSetError('eventDescription', e.target.value);
              }}
              onBlur={() => {
                touchField('eventDescription');
                validateAndSetError('eventDescription', formData.eventDescription);
              }}
              rows={4}
              className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors ${
                hasFieldError('eventDescription') ? 'border-red-500 focus:border-red-600' : 'border-purple-200 focus:border-purple-400'
              }`}
            />
            {hasFieldError('eventDescription') && (
              <p className="text-base text-red-600 mt-1">{getFieldError('eventDescription')}</p>
            )}
          </div>

          <CreatableMultiSelect
            label="Categories *"
            helpText="Choose categories for this event (or create new ones)"
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
            isDisabled={false}
            hasError={hasFieldError('categories')}
            errorMessage={getFieldError('categories')}
          />
        </div>

        {/* Middle Column */}
        <div className="space-y-6">
          <CreatableMultiSelect
            label="Entities *"
            helpText="Choose entities that would be affected by this event"
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
            isDisabled={false}
            hasError={hasFieldError('entities')}
            errorMessage={getFieldError('entities')}
          />

          <div>
            <label className="block text-base font-medium text-gray-700 mb-1">Cause *</label>
            <label className="block text-base text-gray-500 mb-2">What could cause this event to happen?</label>
            <textarea
              placeholder="<Cause>"
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
            <label className="block text-base font-medium text-gray-700 mb-1">Why are you adding this event?</label>
            <label className="block text-base text-gray-500 mb-2">Explain why you chose add this event:</label>
            <textarea
              placeholder="<Reason for Adding>"
              value={formData.reason}
              onChange={(e) => handleInputChange('reason', e.target.value)}
              rows={4}
              className="w-full bg-purple px-4 py-3 border-2 border-purple-200 rounded-2xl focus:border-purple-400 focus:outline-none transition-colors"
            />
          </div>
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          <div>
            <label className="block text-base font-medium text-gray-700 mb-1">Valence *</label>
            <label className="block text-base text-gray-500 mb-2">Is the event positive or negative?</label>
            <div className={`space-y-3 p-3 rounded-2xl border-2 ${
              hasFieldError('valence') ? 'border-red-500' : 'border-transparent'
            }`}>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="radio"
                  name="valence-edit"
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
                  name="valence-edit"
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
            label="Likelihood"
            value={formData.likelihood}
            helptext="How likely do you think it is this event will happen? (0=not at all, 100=certainly)"
            onChange={(val) => handleSliderChange('likelihood', val)}
          />

          <RangeSlider
            label="Magnitude"
            value={formData.magnitude}
            helptext="What do you think the magnitude of the impact would be? (0=none, 100=very large)"
            onChange={(val) => handleSliderChange('magnitude', val)}
          />
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-between items-center mt-8 pt-6 border-t border-gray-200">
        <button
          onClick={onCancel}
          className="flex items-center gap-2 px-4 py-2 text-gray-600 border-2 border-purple-200 rounded-full hover:bg-purple-200 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Audit Criteria
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
          {isReadOnly ? 'Read-Only Mode' : changesExist ? 'Save Changes' : 'No Changes to Save'}
        </button>
      </div>
    </div>
  );
};

export default EditEventForm;