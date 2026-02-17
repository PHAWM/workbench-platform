// context/ApiContext.js
import React, { createContext, useContext, useReducer, useCallback } from 'react';
import { 
  dashboardAPI, 
  aiApplicationAPI, 
  eventsAPI, 
  metricsAPI, 
  handleApiError,
  AUDIT_STATUS 
} from '../api/apiService';

// Helper to get persisted state
const getPersistedAuditState = (auditId) => {
  if (!auditId) return { hasSelectedMetrics: false, hasEvaluated: false };

  try {
    const stored = localStorage.getItem(`audit_state_${auditId}`);
    return stored ? JSON.parse(stored) : { hasSelectedMetrics: false, hasEvaluated: false };
  } catch {
    return { hasSelectedMetrics: false, hasEvaluated: false };
  }
};

// Helper to persist state
const persistAuditState = (auditId, hasSelectedMetrics, hasEvaluated) => {
  if (!auditId) return;

  try {
    localStorage.setItem(`audit_state_${auditId}`, JSON.stringify({
      hasSelectedMetrics,
      hasEvaluated
    }));
  } catch (error) {
    console.error('Failed to persist audit state:', error);
  }
};

// Initial state
const initialState = {
  // Loading states
  loading: {
    applications: false,
    events: false,
    metrics: false,
    audit: false,
  },

  // Error states
  errors: {
    applications: null,
    events: null,
    metrics: null,
    audit: null,
  },

  // Data states
  applications: [],
  currentApplication: null,
  currentAudit: null,
  auditStatus: "",
  accessType: "",
  events: [],
  metrics: [],

  // UI states
  hasSelectedMetrics: false,
  hasEvaluated: false,
  currentPage: 'dashboard',

  // Output Evaluation cache - keyed by auditId
  evaluationCache: {},
};

// Action types
const ActionTypes = {
  SET_LOADING: 'SET_LOADING',
  SET_ERROR: 'SET_ERROR',
  SET_APPLICATIONS: 'SET_APPLICATIONS',
  SET_CURRENT_APPLICATION: 'SET_CURRENT_APPLICATION',
  SET_CURRENT_AUDIT: 'SET_CURRENT_AUDIT',
  SET_AUDIT_STATUS: 'SET_AUDIT_STATUS',
  SET_ACCESS_TYPE: 'SET_ACCESS_TYPE',
  SET_EVENTS: 'SET_EVENTS',
  SET_METRICS: 'SET_METRICS',
  UPDATE_EVENT: 'UPDATE_EVENT',
  UPDATE_METRIC: 'UPDATE_METRIC',
  SET_CURRENT_PAGE: 'SET_CURRENT_PAGE',
  TOGGLE_METRIC_FOR_AUDIT: 'TOGGLE_METRIC_FOR_AUDIT',
  UPDATE_THRESHOLD: 'UPDATE_THRESHOLD',
  CLEAR_ERROR: 'CLEAR_ERROR',
  // Evaluation cache actions
  SET_EVALUATION_CACHE: 'SET_EVALUATION_CACHE',
  UPDATE_EVALUATION_CACHE: 'UPDATE_EVALUATION_CACHE',
  CLEAR_EVALUATION_CACHE: 'CLEAR_EVALUATION_CACHE',
};

// Reducer
const apiReducer = (state, action) => {
  switch (action.type) {
    case ActionTypes.SET_LOADING:
      return {
        ...state,
        loading: {
          ...state.loading,
          [action.key]: action.value,
        },
      };
      
    case ActionTypes.SET_ERROR:
      return {
        ...state,
        errors: {
          ...state.errors,
          [action.key]: action.value,
        },
      };
      
    case ActionTypes.CLEAR_ERROR:
      return {
        ...state,
        errors: {
          ...state.errors,
          [action.key]: null,
        },
      };
      
    case ActionTypes.SET_APPLICATIONS:
      return {
        ...state,
        applications: action.value,
      };
      
    case ActionTypes.SET_CURRENT_APPLICATION:
      return {
        ...state,
        currentApplication: action.value,
      };
      
    case ActionTypes.SET_CURRENT_AUDIT:
      return {
        ...state,
        currentAudit: action.value,
      };

    case ActionTypes.SET_AUDIT_STATUS:
      return {
        ...state,
        auditStatus: action.value,
      };

    case ActionTypes.SET_ACCESS_TYPE:
      return {
        ...state,
        accessType: action.value,
      };

    case ActionTypes.SET_EVENTS:
      const storedState = getPersistedAuditState(action.auditId);
      const hasSelectedMetrics = action.value.some(event =>
        event.metrics && event.metrics.some(metric => metric.useInAudit)
      ) || storedState.hasSelectedMetrics;

      // Persist state if it changed
      if (action.auditId && hasSelectedMetrics !== storedState.hasSelectedMetrics) {
        persistAuditState(action.auditId, hasSelectedMetrics, storedState.hasEvaluated);
      }

      return {
        ...state,
        events: action.value,
        hasSelectedMetrics,
        hasEvaluated: storedState.hasEvaluated,
      };
      
    case ActionTypes.SET_METRICS:
      return {
        ...state,
        metrics: action.value,
      };
      
    case ActionTypes.UPDATE_EVENT:
      const updatedEvents = state.events.map(event =>
        event.id === action.eventId ? { ...event, ...action.updates } : event
      );
      const updatedHasSelectedMetrics = updatedEvents.some(event =>
        event.metrics && event.metrics.some(metric => metric.useInAudit)
      );

      // Persist updated state
      if (action.auditId) {
        const currentState = getPersistedAuditState(action.auditId);
        persistAuditState(action.auditId, updatedHasSelectedMetrics, currentState.hasEvaluated);
      }

      return {
        ...state,
        events: updatedEvents,
        hasSelectedMetrics: updatedHasSelectedMetrics,
      };
      
    case ActionTypes.UPDATE_METRIC:
      return {
        ...state,
        metrics: state.metrics.map(metric =>
          metric.id === action.metricId ? { ...metric, ...action.updates } : metric
        ),
      };
      
    case ActionTypes.TOGGLE_METRIC_FOR_AUDIT:
      return {
        ...state,
        events: state.events.map(event =>
          event.id === action.eventId
            ? {
                ...event,
                metrics: event.metrics.map(metric =>
                  metric.id === action.metricId
                    ? { ...metric, useInAudit: action.useInAudit }
                    : metric
                ),
              }
            : event
        ),
      };
      
    case ActionTypes.UPDATE_THRESHOLD:
      return {
        ...state,
        events: state.events.map(event =>
          event.id === action.eventId
            ? {
                ...event,
                metrics: event.metrics.map(metric =>
                  metric.id === action.metricId
                    ? { 
                        ...metric, 
                        threshold: action.threshold,
                        thresholdDetails: action.thresholdDetails
                      }
                    : metric
                ),
              }
            : event
        ),
      };
      
    case ActionTypes.SET_CURRENT_PAGE:
      return {
        ...state,
        currentPage: action.value,
      };

    // Evaluation cache actions
    case ActionTypes.SET_EVALUATION_CACHE:
      return {
        ...state,
        evaluationCache: {
          ...state.evaluationCache,
          [action.auditId]: {
            data: action.data,
            flags: action.flags,
            timestamp: Date.now(),
          },
        },
      };

    case ActionTypes.UPDATE_EVALUATION_CACHE:
      // Update a specific metric's evaluation data within the cache
      const existingCache = state.evaluationCache[action.auditId] || { data: {}, flags: {} };
      return {
        ...state,
        evaluationCache: {
          ...state.evaluationCache,
          [action.auditId]: {
            data: {
              ...existingCache.data,
              [action.criteriaId]: action.evaluationData,
            },
            flags: {
              ...existingCache.flags,
              [action.criteriaId]: true,
            },
            timestamp: Date.now(),
          },
        },
      };

    case ActionTypes.CLEAR_EVALUATION_CACHE:
      if (action.auditId) {
        const { [action.auditId]: _, ...rest } = state.evaluationCache;
        return {
          ...state,
          evaluationCache: rest,
        };
      }
      return {
        ...state,
        evaluationCache: {},
      };

    default:
      return state;
  }
};

// Create context
const ApiContext = createContext();

// Context provider component
export const ApiProvider = ({ children }) => {
  const [state, dispatch] = useReducer(apiReducer, initialState);

  // Helper functions
  const setLoading = useCallback((key, value) => {
    dispatch({ type: ActionTypes.SET_LOADING, key, value });
  }, []);

  const setError = useCallback((key, error) => {
    const errorMessage = typeof error === 'string' ? error : handleApiError(error);
    dispatch({ type: ActionTypes.SET_ERROR, key, value: errorMessage });
  }, []);

  const clearError = useCallback((key) => {
    dispatch({ type: ActionTypes.CLEAR_ERROR, key });
  }, []);

  // API action creators
  const actions = {
    // Dashboard actions
    loadApplications: useCallback(async () => {
      try {
        setLoading('applications', true);
        clearError('applications');
        
        const applications = await dashboardAPI.getApplications();
        dispatch({ type: ActionTypes.SET_APPLICATIONS, value: applications });
        
        return applications;
      } catch (error) {
        setError('applications', error);
        throw error;
      } finally {
        setLoading('applications', false);
      }
    }, [setLoading, setError, clearError]),

    createApplication: useCallback(async (applicationData) => {
      try {
        setLoading('applications', true);
        clearError('applications');
        
        const newApplication = await dashboardAPI.createApplication(applicationData);
        
        // Reload applications to get updated list
        const applications = await dashboardAPI.getApplications();
        dispatch({ type: ActionTypes.SET_APPLICATIONS, value: applications });
        
        return newApplication;
      } catch (error) {
        setError('applications', error);
        throw error;
      } finally {
        setLoading('applications', false);
      }
    }, [setLoading, setError, clearError]),

    createAudit: useCallback(async (auditData) => {
      try {
        setLoading('audit', true);
        clearError('audit');
        
        const newAudit = await dashboardAPI.createAudit(auditData);
        
        // Reload applications to show new audit
        const applications = await dashboardAPI.getApplications();
        dispatch({ type: ActionTypes.SET_APPLICATIONS, value: applications });
        
        return newAudit;
      } catch (error) {
        setError('audit', error);
        throw error;
      } finally {
        setLoading('audit', false);
      }
    }, [setLoading, setError, clearError]),

    // Application overview actions
    loadApplication: useCallback(async (applicationId) => {
      try {
        setLoading('applications', true);
        clearError('applications');
        
        const application = await aiApplicationAPI.getApplicationOverview(applicationId);
        dispatch({ type: ActionTypes.SET_CURRENT_APPLICATION, value: application });
        
        return application;
      } catch (error) {
        setError('applications', error);
        throw error;
      } finally {
        setLoading('applications', false);
      }
    }, [setLoading, setError, clearError]),

    updateApplication: useCallback(async (applicationId, applicationData) => {
      try {
        setLoading('applications', true);
        clearError('applications');
        
        const updatedApplication = await aiApplicationAPI.updateApplicationOverview(applicationId, applicationData);
        dispatch({ type: ActionTypes.SET_CURRENT_APPLICATION, value: updatedApplication });
        
        return updatedApplication;
      } catch (error) {
        setError('applications', error);
        throw error;
      } finally {
        setLoading('applications', false);
      }
    }, [setLoading, setError, clearError]),

    // Audit actions
    loadAudit: useCallback(async (auditId) => {
      try {
        setLoading('audit', true);
        clearError('audit');

        const audit = await dashboardAPI.getAudit(auditId);
        dispatch({ type: ActionTypes.SET_CURRENT_AUDIT, value: audit });
        dispatch({ type: ActionTypes.SET_AUDIT_STATUS, value: audit.status_text || "" });
        dispatch({ type: ActionTypes.SET_ACCESS_TYPE, value: audit.access_type || "" });

        return audit;
      } catch (error) {
        setError('audit', error);
        throw error;
      } finally {
        setLoading('audit', false);
      }
    }, [setLoading, setError, clearError]),

    // Set audit status and access type
    setAuditStatus: useCallback((status) => {
      dispatch({ type: ActionTypes.SET_AUDIT_STATUS, value: status });
    }, []),

    setAccessType: useCallback((accessType) => {
      dispatch({ type: ActionTypes.SET_ACCESS_TYPE, value: accessType });
    }, []),

    // Events actions
    loadEvents: useCallback(async (auditId) => {
      try {
        setLoading('events', true);
        clearError('events');
        
        const events = await eventsAPI.getEvents(auditId);
        
        // Transform API response to component format
        const transformedEvents = events.map(event => ({
          id: event.id,
          name: event.description,
          description: event.description,
          category: event.event_categories?.length > 0
            ? event.event_categories.map(cat => cat.event_name).join(', ')
            : 'Uncategorized',
          creator: event.created_by?.full_name || 'Unknown',
          valence: event.valence > 0 ? 'Positive' : 'Negative',
          magnitude: Math.round(event.magnitude * 100),
          likelihood: Math.round(event.likelihood * 100),
          cause: event.cause,
          entities: event.associated_entities?.map(e => e.entity_name).join(', ') || '',
          reason: event.custom_values?.description || 'No reason provided',
          isUserCreated: event.is_user_defined || false,
          metrics: event.associated_metrics?.map(metric => ({
            id: metric.metric_id,
            name: metric.metric_description,
            description: metric.metric_description,
            definition: metric.definition || metric.formula,
            creator: 'System',
            features: metric.features?.join(', ') || '',
            threshold: metric.metric_value_threshold?.toString() || '',
            reason: metric.reason || '',
            labels: metric.metric_type || '',
            useInAudit: false, // Default to false, will be updated by user interaction
            isUserCreated: metric.is_user_created || false
          })) || []
        }));
        
        dispatch({ type: ActionTypes.SET_EVENTS, value: transformedEvents });
        
        return transformedEvents;
      } catch (error) {
        setError('events', error);
        throw error;
      } finally {
        setLoading('events', false);
      }
    }, [setLoading, setError, clearError]),

    createEvent: useCallback(async (auditId, eventData) => {
      try {
        setLoading('events', true);
        clearError('events');
        
        // Transform UI data to API format
        const apiEventData = {
          description: eventData.name,
          cause: eventData.cause,
          likelihood: eventData.likelihood / 100,
          magnitude: eventData.magnitude / 100,
          valence: eventData.valence === 'positive' ? 1.0 : -1.0,
          is_user_defined: true,
          is_template: false,
          category: eventData.category
        };
        
        const newEvent = await eventsAPI.createEvent(apiEventData);
        
        // Reload events to get updated list
        await actions.loadEvents(auditId);
        
        return newEvent;
      } catch (error) {
        setError('events', error);
        throw error;
      } finally {
        setLoading('events', false);
      }
    }, [setLoading, setError, clearError]),

    updateEvent: useCallback(async (auditId, eventId, eventData) => {
      try {
        setLoading('events', true);
        clearError('events');
        
        // Transform UI data to API format
        const apiEventData = {
          description: eventData.name,
          cause: eventData.cause,
          likelihood: eventData.likelihood / 100,
          magnitude: eventData.magnitude / 100,
          valence: eventData.valence === 'positive' ? 1.0 : -1.0,
          category: eventData.category
        };
        
        const updatedEvent = await eventsAPI.updateEvent(eventId, apiEventData);
        
        // Update local state
        dispatch({ 
          type: ActionTypes.UPDATE_EVENT, 
          eventId, 
          updates: eventData 
        });
        
        return updatedEvent;
      } catch (error) {
        setError('events', error);
        throw error;
      } finally {
        setLoading('events', false);
      }
    }, [setLoading, setError, clearError]),

    // Metrics actions
    toggleMetricForAudit: useCallback(async (auditId, eventId, metricId) => {
      try {
        // Find current state
        const event = state.events.find(e => e.id === eventId);
        const metric = event?.metrics?.find(m => m.id === metricId);
        const newUseInAudit = !metric?.useInAudit;
        
        // Update via API
        await metricsAPI.toggleMetricForAudit(auditId, metricId, newUseInAudit);
        
        // Update local state
        dispatch({
          type: ActionTypes.TOGGLE_METRIC_FOR_AUDIT,
          eventId,
          metricId,
          useInAudit: newUseInAudit,
        });
      } catch (error) {
        setError('metrics', error);
        throw error;
      }
    }, [state.events, setError]),

    updateThreshold: useCallback(async (eventId, metricId, thresholdData) => {
      try {
        // Update threshold via API
        await metricsAPI.updateThreshold(metricId, thresholdData);
        
        // Update local state
        dispatch({
          type: ActionTypes.UPDATE_THRESHOLD,
          eventId,
          metricId,
          threshold: thresholdData.value.toString(),
          thresholdDetails: thresholdData,
        });
      } catch (error) {
        setError('metrics', error);
        throw error;
      }
    }, [setError]),

    createQualitativeMetric: useCallback(async (metricData) => {
      try {
        setLoading('metrics', true);
        clearError('metrics');
        
        const newMetric = await metricsAPI.createQualitativeMetric(metricData);
        
        return newMetric;
      } catch (error) {
        setError('metrics', error);
        throw error;
      } finally {
        setLoading('metrics', false);
      }
    }, [setLoading, setError, clearError]),

    createQuantitativeMetric: useCallback(async (metricData) => {
      try {
        setLoading('metrics', true);
        clearError('metrics');
        
        const newMetric = await metricsAPI.createQuantitativeMetric(metricData);
        
        return newMetric;
      } catch (error) {
        setError('metrics', error);
        throw error;
      } finally {
        setLoading('metrics', false);
      }
    }, [setLoading, setError, clearError]),

    // Navigation actions
    setCurrentPage: useCallback((page) => {
      dispatch({ type: ActionTypes.SET_CURRENT_PAGE, value: page });
    }, []),

    // Evaluation cache actions
    setEvaluationCache: useCallback((auditId, data, flags) => {
      dispatch({
        type: ActionTypes.SET_EVALUATION_CACHE,
        auditId,
        data,
        flags,
      });
    }, []),

    updateEvaluationCache: useCallback((auditId, criteriaId, evaluationData) => {
      dispatch({
        type: ActionTypes.UPDATE_EVALUATION_CACHE,
        auditId,
        criteriaId,
        evaluationData,
      });
    }, []),

    clearEvaluationCache: useCallback((auditId = null) => {
      dispatch({
        type: ActionTypes.CLEAR_EVALUATION_CACHE,
        auditId,
      });
    }, []),

    getEvaluationCache: useCallback((auditId) => {
      return state.evaluationCache[auditId] || null;
    }, [state.evaluationCache]),

    // Utility actions
    clearAllErrors: useCallback(() => {
      Object.keys(state.errors).forEach(key => {
        if (state.errors[key]) {
          clearError(key);
        }
      });
    }, [state.errors, clearError]),

    refreshData: useCallback(async (auditId) => {
      try {
        await Promise.all([
          actions.loadEvents(auditId),
          // Add other data refresh calls as needed
        ]);
      } catch (error) {
        console.error('Error refreshing data:', error);
      }
    }, []),
  };

  // Computed values
  const computed = {
    // Calculate audit progress based on selected metrics
    auditProgress: useCallback(() => {
      const totalMetrics = state.events.reduce((total, event) => 
        total + (event.metrics?.length || 0), 0
      );
      const selectedMetrics = state.events.reduce((total, event) => 
        total + (event.metrics?.filter(m => m.useInAudit)?.length || 0), 0
      );
      
      if (totalMetrics === 0) return 0;
      return Math.round((selectedMetrics / totalMetrics) * 50); // 50% for criteria selection
    }, [state.events]),

    // Get audit status text
    auditStatusText: useCallback((status) => {
      return AUDIT_STATUS[status] || 'Unknown';
    }, []),

    // Get events by category
    eventsByCategory: useCallback(() => {
      const categories = {};
      state.events.forEach(event => {
        const category = event.category || 'Uncategorized';
        if (!categories[category]) {
          categories[category] = [];
        }
        categories[category].push(event);
      });
      return categories;
    }, [state.events]),

    // Get metrics summary
    metricsSummary: useCallback(() => {
      const total = state.events.reduce((acc, event) => 
        acc + (event.metrics?.length || 0), 0
      );
      const selected = state.events.reduce((acc, event) => 
        acc + (event.metrics?.filter(m => m.useInAudit)?.length || 0), 0
      );
      const qualitative = state.events.reduce((acc, event) => 
        acc + (event.metrics?.filter(m => m.labels?.includes('qualitative'))?.length || 0), 0
      );
      const quantitative = total - qualitative;

      return {
        total,
        selected,
        qualitative,
        quantitative,
        selectionPercentage: total > 0 ? Math.round((selected / total) * 100) : 0
      };
    }, [state.events]),
  };

  const value = {
    // State
    ...state,
    
    // Actions
    ...actions,
    
    // Computed values
    ...computed,
    
    // Utility functions
    setLoading,
    setError,
    clearError,
  };

  return (
    <ApiContext.Provider value={value}>
      {children}
    </ApiContext.Provider>
  );
};

// Custom hook to use the API context
export const useApi = () => {
  const context = useContext(ApiContext);
  if (!context) {
    throw new Error('useApi must be used within an ApiProvider');
  }
  return context;
};

// Selectors for optimized re-renders
export const useApiSelector = (selector) => {
  const context = useContext(ApiContext);
  if (!context) {
    throw new Error('useApiSelector must be used within an ApiProvider');
  }
  return selector(context);
};

// Higher-order component for API integration
export const withApi = (Component) => {
  return (props) => {
    const api = useApi();
    return <Component {...props} api={api} />;
  };
};

export default ApiContext;