import React, { useState, useEffect, useRef } from 'react';
import { ChevronDown, ChevronUp, ArrowLeft, User } from 'lucide-react';
import { CreateEventForm } from '../event/EventCreate';
import { eventsAPI } from '../../api/apiService';
import { detectAndCreateNewEntities } from '../../utils/formUtils';

const EventAssignmentModal = ({
  metricData,
  onClose,
  onComplete,
  onBack,
  eventCategories = [],
  entities = [],
  availableMetrics = [],
  eventsExisting = [],
  auditId,
  initialSelectedEvents = [],
  onSelectionChange = null, // Callback to notify parent of selection changes
  availableUnderlyingFeatures = [],
  availableTargetFeatures = [],
  toast = null // Optional toast for notifications
}) => {
  // Helper for notifications - uses toast if available, falls back to alert
  const notify = {
    success: (message) => toast ? toast.success(message) : alert(message),
    error: (message) => toast ? toast.error(message) : alert(message),
    warning: (message) => toast ? toast.warning(message) : alert(message),
    info: (message) => toast ? toast.info(message) : alert(message)
  };
  // Initialize with previously selected events
  const [selectedEvents, setSelectedEvents] = useState(initialSelectedEvents);
  const [expandedEvents, setExpandedEvents] = useState({});
  
  // States for nested event creation
  const [showCreateEvent, setShowCreateEvent] = useState(false);
  const [savedMetricData, setSavedMetricData] = useState(null);

  const [availableEvents, setAvailableEvents] = useState(eventsExisting);
  const isInitialRender = useRef(true);

  useEffect(() => {
    if (!isInitialRender.current && onSelectionChange) {
      onSelectionChange(selectedEvents);
    }
    isInitialRender.current = false;
  }, [selectedEvents]);
  
  const handleEventToggle = (eventId) => {
    setSelectedEvents(prev => {
      const newSelection = prev.includes(eventId) 
        ? prev.filter(id => id !== eventId)
        : [...prev, eventId];
      return newSelection;
    });
  };

  const handleEventExpand = (eventId) => {
    setExpandedEvents(prev => ({
      ...prev,
      [eventId]: !prev[eventId]
    }));
  };

  const handleComplete = () => {
    const metricWithEvents = {
      ...metricData,
      id: `metric-${Date.now()}`,
      isUserCreated: true,
      creator: 'Current User',
      features: metricData.targetFeature || metricData.targetFeatures?.join(', ') || 'User Generated',
      threshold: metricData.threshold || 'Custom Threshold',
      labels: 'Custom, User Created',
      selectedEventIds: selectedEvents, // Keep track of selected IDs
      events: selectedEvents.map(eventId => {
        const event = availableEvents.find(e => e.id === eventId);
        return {
          ...event,
          useInAudit: true
        };
      })
    };
    
    onComplete(metricWithEvents);
  };

  // NEW: Enhanced back handler that preserves selections
  const handleBackToMetricForm = () => {
    // Don't clear selections - let parent handle the state
    if (onBack) {
      onBack(selectedEvents); // Pass current selections back
    }
  };

  // NEW: Enhanced close handler that preserves selections
  const handleClose = () => {
    // Don't clear selections - let parent handle the state
    if (onClose) {
      onClose(selectedEvents); // Pass current selections back
    }
  };

  // Handlers for creating new event
  const handleCreateNewEvent = () => {
    setSavedMetricData(metricData);
    setShowCreateEvent(true);
  };

  const handleEventFormComplete = async (newEventData) => {
    try {
      // console.log('🚀 Starting event creation in EventAssignment modal...');

      // Use updated categories/entities from the form if provided (includes system entities the
      // user selected and any newly created ones with IDs). Mirrors handleEventFormComplete in
      // auditHandlers so entity dedup matches the standalone "create event" flow — otherwise a
      // system entity is treated as new and the backend rejects it as already existing.
      const categoriesToUse = newEventData._updatedCategories || eventCategories;
      const entitiesToUse = newEventData._updatedEntities || entities;

      // Step 1: Detect and create new entities FIRST
      const { createdEntities, entityNameToIdMap } = await detectAndCreateNewEntities(
        newEventData,
        entitiesToUse,
        auditId
      );

      if (createdEntities.length > 0) {
        // console.log(`✨ Created ${createdEntities.length} new entity/entities:`, createdEntities.map(e => e.name).join(', '));
      }

      // Step 2: Map categories
      const mappedCategories = newEventData.categories ? newEventData.categories.map(categoryName => {
        const category = categoriesToUse.find(cat =>
          (cat.event_name || cat.name || cat) === categoryName
        );
        return {
          category_id: category?.id || 1
        };
      }) : [];

      // Step 3: Map entities using the ID mapping
      const mappedEntities = newEventData.entities ? newEventData.entities.map(entityName => {
        // First check if we just created this entity
        if (entityNameToIdMap[entityName]) {
          return {
            entity_id: entityNameToIdMap[entityName]
          };
        }

        // Otherwise find in existing entities
        const entity = entitiesToUse.find(ent =>
          (ent.name || ent.entity_name || ent) === entityName
        );
        return {
          entity_id: entity?.id || entity?.entity_id || 1
        };
      }) : [];

      const apiEventData = {
        audit_id: parseInt(auditId || savedMetricData?.audit_id || 1),
        name: newEventData.name,
        description: newEventData.name,
        cause: newEventData.cause,
        reason: newEventData.reason,
        likelihood: newEventData.likelihood / 100,
        magnitude: newEventData.magnitude / 100,
        valence: newEventData.valence === 'positive' ? 1.0 : -1.0,
        is_user_defined: true,
        is_template: false,

        entities: mappedEntities,
        categories: mappedCategories,
        metrics: [],
      };

      // console.log('📦 Creating event with entity IDs:', apiEventData);
      const createdEvent = await eventsAPI.createEvent(apiEventData);

      const newEvent = {
        id: createdEvent.id,
        name: newEventData.name,
        description: newEventData.description,
        category: Array.isArray(newEventData.categories) ? newEventData.categories[0] : newEventData.categories,
        creator: 'Current User',
        valence: newEventData.valence === 'positive' ? 'Positive' : 'Negative',
        magnitude: newEventData.magnitude.toString(),
        likelihood: newEventData.likelihood.toString(),
        cause: newEventData.cause,
        entities: Array.isArray(newEventData.entities) ? newEventData.entities.join(', ') : newEventData.entities,
        reason: newEventData.reason,
        isUserCreated: true
      };

      setAvailableEvents(prev => [...prev, newEvent]);
      setSelectedEvents(prev => [...prev, newEvent.id]);
      setShowCreateEvent(false);
      setSavedMetricData(null);

      const entityMessage = createdEntities.length > 0
        ? ` ${createdEntities.length} new entity/entities were also created.`
        : '';
      notify.success(`Event "${newEvent.name}" created successfully and added to selection!${entityMessage}`);

    } catch (error) {
      console.error('Error creating event:', error);
      notify.error(`Failed to create event: ${error.message}`);
    }
  };

  const handleEventFormCancel = () => {
    setShowCreateEvent(false);
    setSavedMetricData(null);
  };

  const EventCard = ({ event }) => {
    const isSelected = selectedEvents.includes(event.id);
    const isExpanded = expandedEvents[event.id];

    return (
      <div className={`border-2 rounded-2xl p-4 transition-all ${
        isSelected 
          ? 'border-purple-300 bg-gradient-to-r from-purple-50 to-pink-50' 
          : 'border-gray-200 bg-white hover:border-gray-300'
      }`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3 flex-1">
            <input
              type="checkbox"
              checked={isSelected}
              onChange={() => handleEventToggle(event.id)}
              className="w-4 h-4 text-purple-600 border-2 border-purple-200 rounded focus:ring-purple-500"
            />
            <div className="flex items-center gap-2">
              {event.isUserCreated && (
                <div className="w-6 h-6 bg-purple-200 rounded-full flex items-center justify-center">
                  <User className="w-3 h-3 text-purple-600" />
                </div>
              )}
              <span className="font-medium">{event.name}</span>
            </div>
          </div>
          <button 
            onClick={() => handleEventExpand(event.id)}
            className="p-1 hover:bg-gray-100 rounded-full transition-colors"
          >
            {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
          </button>
        </div>

        {!isExpanded && (
          <div className="text-sm text-gray-700 ml-7">
            <strong>Description:</strong> {event.description}
          </div>
        )}

        {isExpanded && (
          <div className="ml-7 space-y-2 text-sm text-gray-700">
            <div><strong>Description:</strong> {event.description}</div>
            <div><strong>Event Category:</strong> {event.category}</div>
            <div><strong>Event Creator:</strong> {event.creator}</div>
            <div><strong>Valence:</strong> {event.valence}</div>
            <div><strong>Magnitude of Impact:</strong> {event.magnitude}</div>
            <div><strong>Likelihood:</strong> {event.likelihood}</div>
            <div><strong>Cause:</strong> {event.cause}</div>
            <div><strong>Associated Entities:</strong> {event.entities}</div>
            <div><strong>Why Event was added:</strong> {event.reason}</div>
            
            {isSelected && (
              <div className="mt-4 pt-3 border-t border-purple-200">
                <div className="flex items-center gap-2 text-purple-700 text-xs">
                  <span className="w-2 h-2 bg-purple-400 rounded-full"></span>
                  <span>This event will be associated with the metric</span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  // If we're in event creation mode, show the event creation form
  if (showCreateEvent) {
    return (
      <CreateEventForm
        onCancel={handleEventFormCancel}
        onComplete={handleEventFormComplete}
        eventCategories={eventCategories}
        entities={entities}
        availableMetrics={availableMetrics}
        showBackToAssignment={true}
        parentContext="metric-assignment"
        availableUnderlyingFeatures={availableUnderlyingFeatures}
        availableTargetFeatures={availableTargetFeatures}
        auditId={auditId}
      />
    );
  }

  return (
    <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg w-full">
      {/* Purpose Box */}
      <div className="mb-6 bg-b7efff rounded-2xl border-2 border-purple-300 p-6 shadow-md">
        <p className="text-gray-700">
          This is the Assign Events page. Here you can select existing events to associate with your metric, or create new custom events. Choose or create one or more event that the metric can measure. Once you have chosen or created the event(s), you can save that by clicking the Save Audit Criteria button or Return to Create Metric without saving.
        </p>
      </div>

      {/* Header */}
      <div className="flex items-center gap-3 mb-6 pb-4 border-b border-purple-200">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Assign Events to Metric</h1>
          <p className="text-base text-gray-600">
            Select existing events for: <strong>{metricData.name}</strong>
          </p>
          {initialSelectedEvents.length > 0 && (
            <p className="text-base text-blue-600 mt-1">
              ✓ Restored {initialSelectedEvents.length} previous selection{initialSelectedEvents.length !== 1 ? 's' : ''}
            </p>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="space-y-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-medium text-gray-700">Available Events</h3>
          <span className="text-sm text-gray-600 bg-purple-100 px-3 py-1 rounded-full">
            {selectedEvents.length} selected
          </span>
        </div>

        {/* Events List */}
        <div className="space-y-4">
          {availableEvents.map(event => (
            <EventCard key={event.id} event={event} />
          ))}
        </div>

        {/* Create New Event Button */}
        <div className="pt-4">
          <button
            onClick={handleCreateNewEvent}
            className="w-full border-2 border-dashed border-purple-300 rounded-2xl p-4 text-purple-600 hover:border-purple-400 hover:bg-purple-50 transition-colors"
          >
            + Create New Event
          </button>
        </div>
      </div>

      {/* Footer */}
      <div className="flex justify-between items-center mt-8 pt-6 border-t border-purple-200">
        {onBack ? (
          <button
            onClick={handleBackToMetricForm}
            className="flex items-center gap-2 px-4 py-2 text-gray-600 border-2 border-purple-200 rounded-full hover:bg-purple-200 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Return to Create Metric without saving
          </button>
        ) : (
          <button
            onClick={handleClose}
            className="flex items-center gap-2 px-4 py-2 text-gray-600 border-2 border-purple-200 rounded-full hover:bg-purple-200 transition-colors"
          >
            Return to Create Metric without saving
          </button>
        )}
        <button
          onClick={handleComplete}
          disabled={selectedEvents.length === 0}
          className={`px-6 py-2 rounded-full text-base font-semibold transition-colors ${
            selectedEvents.length > 0
              ? 'bg-purple-100 hover:bg-purple-200 border-2 border-purple-200'
              : 'bg-gray-300 text-gray-500 cursor-not-allowed border-2 border-gray-300'
          }`}
        >
          Save Audit Criteria
        </button>
      </div>
    </div>
  );
};

export default EventAssignmentModal;