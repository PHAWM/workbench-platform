/**
 * Handlers for AuditCriteria page
 * Contains event and metric management functions
 */

/**
 * Creates handlers for audit criteria page
 * @param {Object} params - Parameters for creating handlers
 * @returns {Object} Handler functions
 */
export const createAuditCriteriaHandlers = ({
  setExpandedEvents,
  setIsVisible,
  updateModals,
  resetForms,
  setShowThresholdErrors,
  handlers,
  navigate,
  auditData,
  currentPage
}) => {
  /**
   * Toggle event expansion in the accordion
   * @param {number} index - Event index
   */
  const handleEventToggle = (index) => {
    setExpandedEvents(prev => ({ ...prev, [index]: !prev[index] }));
  };

  /**
   * Open create new event form
   */
  const handleCreateNewEvent = () => {
    resetForms();
    setIsVisible(false);
    updateModals({ showCreateEventForm: true });
  };

  /**
   * Open create metric type selection modal
   */
  const handleCreateMetric = () => {
    resetForms();
    setIsVisible(false);
    updateModals({ showMetricTypeModal: true });
  };

  /**
   * Open edit event form
   * @param {Object} event - Event to edit
   */
  const handleEditEvent = (event) => {
    resetForms();
    setIsVisible(false);
    updateModals({ editingEvent: event });
  };

  /**
   * Open edit metric form
   * @param {Object} metric - Metric to edit
   * @param {number} eventId - Parent event ID
   */
  const handleEditMetric = (metric, eventId) => {
    resetForms();
    setIsVisible(false);
    updateModals({ editingMetric: { ...metric, eventId } });
  };

  /**
   * Handle navigation with threshold validation
   * @param {string} pageId - Target page ID
   * @param {Function} getSelectedMetricsWithoutThreshold - Function to get metrics without thresholds
   */
  const handleNavigationWithValidation = async (pageId, getSelectedMetricsWithoutThreshold) => {
    // If navigating to performance, check for missing thresholds
    if (pageId === 'performance') {
      const metricsWithoutThreshold = getSelectedMetricsWithoutThreshold(auditData.events || []);
      if (metricsWithoutThreshold.length > 0) {
        setShowThresholdErrors(true);
      } else {
        setShowThresholdErrors(false);
      }
    }
    await handlers.handleNavigation(pageId, navigate, auditData.events || [], currentPage);
  };

  /**
   * Navigate to performance page with validation
   * @param {Function} getSelectedMetricsWithoutThreshold - Function to get metrics without thresholds
   */
  const handleNavigateToPerformance = async (getSelectedMetricsWithoutThreshold) => {
    await handleNavigationWithValidation('performance', getSelectedMetricsWithoutThreshold);
  };

  return {
    handleEventToggle,
    handleCreateNewEvent,
    handleCreateMetric,
    handleEditEvent,
    handleEditMetric,
    handleNavigationWithValidation,
    handleNavigateToPerformance
  };
};

/**
 * Check if any events have selected metrics
 * @param {Array} events - Array of events
 * @returns {boolean} True if any metrics are selected
 */
export const hasAnySelectedMetrics = (events) => {
  if (!events || !Array.isArray(events)) return false;
  return events.some(event =>
    event.metrics && event.metrics.some(metric => metric.isSelected)
  );
};

/**
 * Get selected metrics that don't have thresholds
 * @param {Array} events - Array of events
 * @returns {Array} Array of metrics without thresholds
 */
export const getSelectedMetricsWithoutThreshold = (events) => {
  if (!events || !Array.isArray(events)) return [];

  const metricsWithoutThreshold = [];
  events.forEach(event => {
    if (event.metrics) {
      event.metrics.forEach(metric => {
        if (metric.isSelected && !metric.threshold) {
          metricsWithoutThreshold.push({
            ...metric,
            eventName: event.name || event.event_name
          });
        }
      });
    }
  });
  return metricsWithoutThreshold;
};
