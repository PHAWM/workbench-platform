// hooks/useAuditData.js
import { useState, useEffect } from 'react';
import { eventsAPI, metricsAPI, handleApiError } from '../api/apiService';
import { transformApiEventsToComponentFormat } from '../utils/auditUtils';

export const useAuditData = (auditId) => {
  const [state, setState] = useState({
    loading: true,
    error: null,
    events: [],
    availableMetrics: [],
    eventCategories: [],
    entities: [],
    availableUnderlyingFeatures: [],
    availableTargetFeatures: [],
    hasSelectedMetrics: false,
    hasEvaluated: false
  });

  const updateState = (updates) => setState(prev => ({ ...prev, ...updates }));

  const loadAuditData = async () => {
    try {
      updateState({ loading: true, error: null });
      
      const [eventsResponse, entitiesResponse, categoriesResponse, availableMetricsData] = await Promise.allSettled([
        eventsAPI.getEvents(auditId),
        eventsAPI.getEntities(parseInt(auditId)),
        eventsAPI.getUserEventCategories(parseInt(auditId)),
        metricsAPI.getMetrics(auditId)
      ]);

      const events = eventsResponse.status === 'fulfilled' ? transformApiEventsToComponentFormat(eventsResponse.value) : [];

      // Parse entities response (contains user_entities and event_entities)
      let allEntities = [];
      if (entitiesResponse.status === 'fulfilled' && entitiesResponse.value?.entities) {
        const userEntities = entitiesResponse.value.entities.user_entities || [];
        const eventEntities = entitiesResponse.value.entities.event_entities || [];
        allEntities = [...userEntities, ...eventEntities];
      }

      // Parse categories response (contains user_categories and system_categories)
      let eventCategories = [];
      if (categoriesResponse.status === 'fulfilled' && categoriesResponse.value?.categories) {
        const userCategories = categoriesResponse.value.categories.user_categories || [];
        const systemCategories = categoriesResponse.value.categories.system_categories || [];
        eventCategories = [...userCategories, ...systemCategories];
      }
      const availableMetrics = availableMetricsData.status === 'fulfilled' ? availableMetricsData.value : [];

      // Check persisted state
      const persistedState = localStorage.getItem(`audit_state_${auditId}`);
      const { hasSelectedMetrics: persistedHasSelectedMetrics, hasEvaluated: persistedHasEvaluated } =
        persistedState ? JSON.parse(persistedState) : { hasSelectedMetrics: false, hasEvaluated: false };

      // Calculate current hasSelectedMetrics from events
      const currentHasSelectedMetrics = events.some(event =>
        event.metrics && event.metrics.some(metric => metric.useInAudit)
      ) || persistedHasSelectedMetrics;

      updateState({
        events,
        entities: allEntities,
        eventCategories,
        availableMetrics,
        hasSelectedMetrics: currentHasSelectedMetrics,
        hasEvaluated: persistedHasEvaluated
      });
      
    } catch (err) {
      updateState({ error: handleApiError(err, 'Failed to load audit data') });
    } finally {
      updateState({ loading: false });
    }
  };

  const loadMetadata = async () => {
    try {
      const [categoriesData, entitiesData, featuresData] = await Promise.allSettled([
        eventsAPI.getUserEventCategories(parseInt(auditId)),
        eventsAPI.getEntities(parseInt(auditId)),
        eventsAPI.getUnderlyingFeatures(parseInt(auditId)), // This returns both underlying AND targets
        // eventsAPI.getTargetFeatures(parseInt(auditId))
      ]);

      // Parse entities response (contains user_entities and event_entities)
      let allEntities = [];
      if (entitiesData.status === 'fulfilled' && entitiesData.value?.entities) {
        const userEntities = entitiesData.value.entities.user_entities || [];
        const eventEntities = entitiesData.value.entities.event_entities || [];
        allEntities = [...userEntities, ...eventEntities];
      }

      // Parse categories response (contains user_categories and system_categories)
      let eventCategories = [];
      if (categoriesData.status === 'fulfilled' && categoriesData.value?.categories) {
        const userCategories = categoriesData.value.categories.user_categories || [];
        const systemCategories = categoriesData.value.categories.system_categories || [];
        eventCategories = [...userCategories, ...systemCategories];
      }

      // Parse features response (contains user_features, dataset_features, and target_features)
      let allUnderlyingFeatures = [];
      let allTargetFeatures = [];

      if (featuresData.status === 'fulfilled' && featuresData.value) {
        const response = featuresData.value;

        // Underlying features (Distinguishing Factors): dataset_features + user_features
        const datasetUnderFeatures = response.underlying_features?.dataset_features || [];
        const userUnderFeatures = response.underlying_features?.user_features || [];
        allUnderlyingFeatures = [...datasetUnderFeatures, ...userUnderFeatures];

        // Target features: system_features + user_features
        const systemTargetFeatures = response.target_features?.system_features || [];
        const userTargetFeatures = response.target_features?.user_features || [];
        allTargetFeatures = [...systemTargetFeatures, ...userTargetFeatures];
      }

      updateState({
        eventCategories,
        entities: allEntities,
        availableUnderlyingFeatures: allUnderlyingFeatures,
        availableTargetFeatures: allTargetFeatures
      });
    } catch (err) {
      console.error('Error loading metadata:', err);
    }
  };

  // Fetch only the features (target + underlying). loadAuditData already fetches
  // entities and categories, so on initial mount we avoid re-requesting those here.
  const loadFeatures = async () => {
    try {
      const featuresData = await eventsAPI.getUnderlyingFeatures(parseInt(auditId));

      let allUnderlyingFeatures = [];
      let allTargetFeatures = [];
      if (featuresData) {
        const datasetUnderFeatures = featuresData.underlying_features?.dataset_features || [];
        const userUnderFeatures = featuresData.underlying_features?.user_features || [];
        allUnderlyingFeatures = [...datasetUnderFeatures, ...userUnderFeatures];

        const systemTargetFeatures = featuresData.target_features?.system_features || [];
        const userTargetFeatures = featuresData.target_features?.user_features || [];
        allTargetFeatures = [...systemTargetFeatures, ...userTargetFeatures];
      }

      updateState({
        availableUnderlyingFeatures: allUnderlyingFeatures,
        availableTargetFeatures: allTargetFeatures
      });
    } catch (err) {
      console.error('Error loading features:', err);
    }
  };

  const reloadData = async () => {
    await Promise.all([
      loadAuditData(),
      loadMetadata()
    ]);
  };

  useEffect(() => {
    if (auditId) {
      // loadAuditData covers events/entities/categories/metrics; loadFeatures covers
      // the remaining feature lists. This avoids the duplicate entities/categories
      // requests that firing loadAuditData + loadMetadata together previously caused.
      loadAuditData();
      loadFeatures();
    }
  }, [auditId]);

  return {
    ...state,
    updateState,
    reloadData,
    loadAuditData
  };
};