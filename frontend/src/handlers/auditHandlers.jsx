// handlers/auditHandlers.js
import { eventsAPI, metricsAPI, associationAPI, evaluationAPI, handleApiError } from '../api/apiService';
import {
  buildEventApiPayload,
  buildMetricApiPayload,
  transformApiEventsToComponentFormat,
  updateMetricInEvents,
  getSelectedMetricEventPairs,
  getSelectedMetricsWithoutThreshold
} from '../utils/auditUtils';
import { detectAndCreateNewFeatures, detectAndCreateNewEntities } from '../utils/formUtils';

export const createAuditHandlers = (auditId, updateState, updateModals, updatePreserved, reloadData, availableEntities = [], eventCategories = [], updateVisibility=null, toast=null) => {
  // Helper to show notifications - uses toast if available, falls back to alert
  const notify = {
    success: (message) => toast ? toast.success(message) : alert(message),
    error: (message) => toast ? toast.error(message) : alert(message),
    warning: (message) => toast ? toast.warning(message) : alert(message),
    info: (message) => toast ? toast.info(message) : alert(message)
  };
  
  const handleMetricToggle = async (eventId, metricId, events) => {
    try {
      const event = events.find(e => e.id === eventId);
      const metric = event?.metrics?.find(m => m.id === metricId);
      const newUseInAudit = !metric?.useInAudit;

      const updatedEvents = updateMetricInEvents(events, eventId, metricId, { useInAudit: newUseInAudit });
      updateState({ events: updatedEvents });

      // If unchecking (newUseInAudit = false), delete the pipeline mapping
      if (!newUseInAudit) {
        try {
          await associationAPI.deletePipelineMappingByIds(auditId, eventId, metricId);
          // console.log(`Pipeline mapping deleted for audit ${auditId}, event ${eventId}, metric ${metricId}`);
        } catch (deleteErr) {
          console.warn('Failed to delete pipeline mapping (might not exist):', deleteErr);
          // Don't throw - allow UI update to proceed even if delete fails
        }
      }

    } catch (err) {
      updateState({ error: handleApiError(err, 'Failed to update metric') });
    }
  };

  const handleThresholdUpdate = async (eventId, metricId, thresholdData, events) => {
    try {
      const updatedEvents = updateMetricInEvents(events, eventId, metricId, { 
        threshold: `${thresholdData.value}`, 
        thresholdDetails: thresholdData 
      });
      updateState({ events: updatedEvents });
      
      await metricsAPI.updateThreshold(metricId, {
        audit_id: parseInt(auditId),
        event_id: eventId,
        threshold: thresholdData.value.toString()
      });
      
    } catch (err) {
      updateState({ error: handleApiError(err, 'Failed to update threshold') });
    }
  };

  const handleEventFormComplete = async (newEventData) => {
    try {
      // console.log('🚀 Starting event creation process...');
      // console.log('Event data received:', newEventData);
      // console.log('Entity details:', newEventData.entityDetails);

      // Use updated categories/entities from form if provided (includes newly created ones with IDs)
      const categoriesToUse = newEventData._updatedCategories || eventCategories;
      const entitiesToUse = newEventData._updatedEntities || availableEntities;

      // console.log('Using categories:', categoriesToUse);
      // console.log('Using entities:', entitiesToUse);

      // Step 1: Detect and create new entities FIRST, get the entity ID mappings
      const { createdEntities, entityNameToIdMap } = await detectAndCreateNewEntities(
        newEventData,
        entitiesToUse,
        auditId
      );

      if (createdEntities.length > 0) {
        // console.log(`Created ${createdEntities.length} new entity/entities:`, createdEntities.map(e => e.name).join(', '));
        // console.log('Entity ID mapping:', entityNameToIdMap);
      }

      // Step 2: Build the API payload with actual entity IDs and category IDs
      const apiEventData = buildEventApiPayload(newEventData, auditId, null, categoriesToUse, entitiesToUse, entityNameToIdMap);

      // Step 3: Create the event
      // console.log('Creating event with entity IDs:', apiEventData);
      const createdEvent = await eventsAPI.createEvent(apiEventData);

      // Close form and clear preserved data immediately
      updateModals({ showCreateEventForm: false });
      updatePreserved({ currentEventFormData: null, metricSelections: [] });

      // Step 4: Reload data to get complete event with all relationships
      // This ensures entities and categories are properly displayed
      await reloadData();

      const entityMessage = createdEntities.length > 0
        ? ` ${createdEntities.length} new entity/entities were also created.`
        : '';
      updateVisibility(true);
      notify.success(`Event "${newEventData.name}" created successfully!${entityMessage}`);
    } catch (err) {
      console.error('Error in handleEventFormComplete:', err);
      updateVisibility(true);
      updateState({ error: handleApiError(err, 'Failed to create event') });
    }
  };

  const handleEventEditSave = async (updatedEventData) => {
    try {
      if (!updatedEventData._hasChanges) {
        updateModals({ editingEvent: null });
        return;
      }

      let updatedEvent = null

      if (updatedEventData._apiPayload.is_user_defined) {
        updatedEvent = await eventsAPI.updateEvent(
          updatedEventData.id,
          updatedEventData._apiPayload
        )
      } else{
        updatedEvent = await eventsAPI.updateEventCustomised(
          updatedEventData.id,
          updatedEventData._apiPayload
        )
      }

      const transformedEvent = transformApiEventsToComponentFormat([updatedEvent])[0];

      updateState(prev => ({
        events: prev.events.map(event =>
          event.id === transformedEvent.id ? transformedEvent : event
        )
      }));

      updateModals({ editingEvent: null });

      const changeCount = Object.keys(updatedEventData._changes).length;
      notify.success(`Event "${updatedEventData.name}" updated successfully! (${changeCount} field${changeCount !== 1 ? 's' : ''} changed)`);
      
      updateVisibility(true);
      // Reload data to ensure all updates are reflected in the UI
      setTimeout(reloadData, 500);
      
    } catch (err) {
      updateState({ error: handleApiError(err, 'Failed to update event') });
    }
  };

  const handleMetricEditSave = async (updatedMetricData, events, availableUnderlyingFeatures = [], availableTargetFeatures = []) => {
    try {
      if (!updatedMetricData._hasChanges) {
        updateModals({ editingMetric: null });
        return;
      }

      const metricType = updatedMetricData.metricType || updatedMetricData.metric_type;
      let payload = { ...updatedMetricData._apiPayload, audit_id: auditId };

      // Check if metric_values contains new features that need to be created
      if (payload.metric_values && payload.metric_values.length > 0) {
        // Detect and create new features first (same as handleEventAssignmentComplete)
        const { createdFeatures, featureNameToIdMap } = await detectAndCreateNewFeatures(
          updatedMetricData,
          availableUnderlyingFeatures,
          availableTargetFeatures,
          auditId
        );

        if (createdFeatures.length > 0) {
          // console.log(`Created ${createdFeatures.length} new feature(s):`, createdFeatures.map(f => f.feature_name || f.name).join(', '));

          // Rebuild metric_values with actual feature IDs
          const { buildQuantitativeMetricValues, buildQualitativeMetricValues } = await import('../utils/formUtils');

          if (metricType === 'quantitative') {
            payload.metric_values = buildQuantitativeMetricValues(
              updatedMetricData,
              availableUnderlyingFeatures,
              availableTargetFeatures,
              featureNameToIdMap
            );
          } else if (metricType === 'qualitative') {
            // For qualitative, use features field mapped to underlyingFeatures
            const qualitativeFormData = {
              ...updatedMetricData,
              underlyingFeatures: updatedMetricData.features || updatedMetricData.underlyingFeatures || []
            };
            payload.metric_values = buildQualitativeMetricValues(
              qualitativeFormData,
              availableUnderlyingFeatures,
              availableTargetFeatures,
              featureNameToIdMap
            );
          }

          // Add event_id and audit_id to each metric value
          payload.metric_values = payload.metric_values.map(mv => ({
            ...mv,
            event_id: updatedMetricData.eventId,
            audit_id: parseInt(auditId)
          }));
        }
      }

      let updatedMetric;
      if (metricType === 'quantitative') {
        updatedMetric = await metricsAPI.updateQuantitativeMetric(payload.metric_id, payload);
      } else if (metricType === 'qualitative') {
        updatedMetric = await metricsAPI.updateQualitativeMetric(payload.metric_id, payload);
      } else {
        updatedMetric = await metricsAPI.updateMetric(payload.metric_id, payload);
      }

      const updatedEvents = events.map(event => ({
        ...event,
        metrics: event.metrics.map(metric =>
          metric.id === payload.metric_id
            ? { ...metric, ...updatedMetricData, useInAudit: metric.useInAudit }
            : metric
        )
      }));

      updateState({ events: updatedEvents });
      updateModals({ editingMetric: null });

      const changeCount = Object.keys(updatedMetricData._changes).length;
      notify.success(`Metric updated successfully! (${changeCount} field${changeCount !== 1 ? 's' : ''} changed)`);

      updateVisibility(true);
      setTimeout(reloadData, 500);

    } catch (err) {
      updateState({ error: handleApiError(err, 'Failed to update metric') });
    }
  };

  const handleMetricFormComplete = (metricData) => {
    updatePreserved({ 
      currentMetricFormData: metricData, 
      savedMetricData: metricData 
    });
    updateModals({ 
      currentMetricForm: null, 
      showEventAssignment: true 
    });
  };

  const handleEventAssignmentComplete = async (metricWithEvents, currentMetricFormData, availableUnderlyingFeatures = [], availableTargetFeatures = []) => {
    try {
      const metricType = metricWithEvents.type;

      console.log('[metric-create] metricWithEvents going into handler:', {
        type: metricType,
        threshold: metricWithEvents.threshold,
        underlyingFeatures: metricWithEvents.underlyingFeatures,
        targetFeatures: metricWithEvents.targetFeatures,
        scalePointsArray: metricWithEvents.scalePointsArray,
        featureRanges: metricWithEvents.featureRanges,
        events: metricWithEvents.events,
      });

      // Step 1: Detect and create new features FIRST, get the feature ID mappings
      // console.log('🚀 Starting feature creation process...');
      const { createdFeatures, featureNameToIdMap } = await detectAndCreateNewFeatures(
        metricWithEvents,
        availableUnderlyingFeatures,
        availableTargetFeatures,
        auditId
      );

      if (createdFeatures.length > 0) {
        // console.log(`Created ${createdFeatures.length} new feature(s):`, createdFeatures.map(f => f.feature_name || f.name).join(', '));
        // console.log('Feature ID mapping:', featureNameToIdMap);
      }

      // Step 2: Rebuild metric_values with the actual feature IDs (including newly created ones)
      const { buildQuantitativeMetricValues, buildQualitativeMetricValues } = await import('../utils/formUtils');

      if (metricType === 'quantitative') {
        metricWithEvents.metric_values = buildQuantitativeMetricValues(
          metricWithEvents,
          availableUnderlyingFeatures,
          availableTargetFeatures,
          featureNameToIdMap
        );
      } else if (metricType === 'qualitative') {
        metricWithEvents.metric_values = buildQualitativeMetricValues(
          metricWithEvents,
          availableUnderlyingFeatures,
          availableTargetFeatures,
          featureNameToIdMap
        );
      }

      // Step 3: Build the API payload with the updated metric_values
      const apiPayload = buildMetricApiPayload(metricWithEvents, auditId, metricType);

      console.log('[metric-create] Final API payload:', JSON.stringify(apiPayload, null, 2));

      // Step 4: Create the metric
      if (metricType === 'quantitative') {
        await metricsAPI.createQuantitativeMetric(apiPayload);
      } else if (metricType === 'qualitative') {
        await metricsAPI.createQualitativeMetric(apiPayload);
      }

      // Step 5: Reload all data (including newly created features)
      // console.log('Reloading audit data...');
      await reloadData();

      updatePreserved({
        eventSelections: [],
        currentMetricFormData: null
      });
      updateModals({ showEventAssignment: false });

      const featureMessage = createdFeatures.length > 0
        ? ` ${createdFeatures.length} new feature(s) were also created.`
        : '';
      updateVisibility(true);
      notify.success(`Metric "${metricWithEvents.name}" created successfully and assigned to ${metricWithEvents.events?.length || 0} event(s)!${featureMessage}`);

    } catch (err) {
      console.error('Error in handleEventAssignmentComplete:', err);
      updateState({ error: handleApiError(err, 'Failed to create metric') });
    }
  };

  const handleGenerateOutputEvaluation = async () => {
    try {
      // // console.log('Generating output evaluation results...');
      updateState({ loading: true, error: null });

      // Call the API to generate output evaluation (uses getResults)
      const results = await evaluationAPI.getResults(auditId);

      // // console.log('Output evaluation results generated:', results);

      // Reload data to get the updated results
      await reloadData();

      updateState({ loading: false });

      return results;
    } catch (err) {
      console.error('Error generating output evaluation:', err);
      updateState({
        error: handleApiError(err, 'Failed to generate output evaluation'),
        loading: false
      });
      throw err;
    }
  };

  const handleNavigation = async (pageId, navigate, events = [], currentPage = 'audit-criteria') => {
    updateState({ currentPage: pageId });

    if (pageId === 'dashboard') return navigate('/dashboard');

    if (pageId === 'profile') return navigate('/profile');

    // console.log(events)

    // Calculate hasSelectedMetrics from events (only if events have useInAudit property)
    const hasSelectedMetricsFromEvents = events.length > 0 && events.some(event => event.metrics?.some(metric => metric.useInAudit));

    // Check if events actually have the useInAudit property (only audit-criteria page has this)
    const eventsHaveUseInAuditProperty = events.length > 0 && events.some(event =>
      event.metrics?.some(metric => metric.hasOwnProperty('useInAudit'))
    );

    // Get current localStorage state
    let currentState = {};
    try {
      const stored = localStorage.getItem(`audit_state_${auditId}`);
      currentState = stored ? JSON.parse(stored) : {};
    } catch (error) {
      console.error('Failed to read localStorage:', error);
    }

    // Only update hasSelectedMetrics in localStorage if:
    // 1. Events actually have the useInAudit property (meaning we're on audit-criteria page with real data), OR
    // 2. We calculated true (always safe to set true)
    // Never overwrite true with false unless we have authoritative data
    let newHasSelectedMetrics = currentState.hasSelectedMetrics || false;
    if (hasSelectedMetricsFromEvents) {
      // Always safe to set true
      newHasSelectedMetrics = true;
    } else if (eventsHaveUseInAuditProperty) {
      // Only set false if we have authoritative data (events with useInAudit property)
      newHasSelectedMetrics = false;
    }
    // Otherwise, preserve existing value

    try {
      localStorage.setItem(`audit_state_${auditId}`, JSON.stringify({
        ...currentState,
        hasSelectedMetrics: newHasSelectedMetrics
      }));
    } catch (error) {
      console.error('Failed to persist hasSelectedMetrics:', error);
    }

    // Get effective hasSelectedMetrics for navigation check
    const effectiveHasSelectedMetrics = newHasSelectedMetrics;

    // Check if navigating to performance without selected metrics
    if (pageId === 'performance' && !effectiveHasSelectedMetrics) {
      notify.warning('Please select at least one audit criteria for audit before proceeding to performance analysis.');
      return;
    }

    // Check if any selected metrics are missing thresholds
    if (pageId === 'performance' && events.length > 0) {
      const metricsWithoutThreshold = getSelectedMetricsWithoutThreshold(events);
      if (metricsWithoutThreshold.length > 0) {
        const metricNames = metricsWithoutThreshold.map(m => `"${m.metricName}"`).join(', ');
        notify.warning(`Please set thresholds for the following selected metrics before proceeding: ${metricNames}`);
        return { metricsWithoutThreshold };
      }
    }

    if (events.length > 0 && hasSelectedMetricsFromEvents) {

      // Submit mappings when navigating away from audit-criteria (but not to performance) and hasSelectedMetrics is true
      if (currentPage === 'audit-criteria' && pageId !== 'performance' && pageId !== 'audit-criteria' && hasSelectedMetricsFromEvents) {
        try {
          const selectedPairs = getSelectedMetricEventPairs(events);
          if (selectedPairs.length > 0) {
            const mappings = {
              mappings: selectedPairs.map(mapping => ({
                event_id: mapping.eventId,
                metric_id: mapping.metricId
              })),
              audit_id: parseInt(auditId)
            };

            await associationAPI.batchCreateAuditPipelineMappings(mappings);
            // console.log("Associations have been created when navigating away from audit criteria");
          }
        } catch (error) {
          console.error('Failed to create associations when navigating away:', error);
        }
      }
    }

    if (pageId === 'performance') {
      try {
        const selectedPairs = getSelectedMetricEventPairs(events);
        const mappings = {
          mappings: selectedPairs.map(mapping => ({
            event_id: mapping.eventId,
            metric_id: mapping.metricId
          })),
          audit_id: parseInt(auditId)
        };

        await associationAPI.batchCreateAuditPipelineMappings(mappings);
        // console.log("Associations have been created correctly");
      } catch (error) {
        console.error('Failed to create associations:', error);
      }
    }

    navigate(`/${pageId}/${auditId}`);
  };

  const handleBackwardNavigation = async(pageId, navigate) => {
    let newPageId= ''
    if (pageId === 'audit-outcome') {newPageId="performance"}
    if (pageId === 'performance') {newPageId="audit-criteria"}
    if (pageId === 'audit-criteria') {newPageId="ai-application"}
    if (pageId === 'ai-application') {
      navigate('/dashboard');
      return;
    }

    // When navigating back from performance analysis, ensure hasSelectedMetrics stays true
    // (if you're on performance, you must have selected metrics)
    if (pageId === 'performance') {
      try {
        const stored = localStorage.getItem(`audit_state_${auditId}`);
        const currentState = stored ? JSON.parse(stored) : {};
        const newState = {
          ...currentState,
          hasSelectedMetrics: true
        };
        localStorage.setItem(`audit_state_${auditId}`, JSON.stringify(newState));

        // Dispatch custom event to notify Navigation component of the change
        window.dispatchEvent(new CustomEvent('auditStateChange', {
          detail: { auditId, state: newState }
        }));
      } catch (error) {
        console.error('Failed to persist hasSelectedMetrics:', error);
      }
    }

    navigate(`/${newPageId}/${auditId}`);
  }

  return {
    handleMetricToggle,
    handleThresholdUpdate,
    handleEventFormComplete,
    handleEventEditSave,
    handleMetricEditSave,
    handleMetricFormComplete,
    handleEventAssignmentComplete,
    handleGenerateOutputEvaluation,
    handleNavigation,
    handleBackwardNavigation
  };
};