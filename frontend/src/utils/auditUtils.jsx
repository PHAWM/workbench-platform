// utils/auditUtils.js

/**
 * Formats a threshold value for display
 * - All numeric values are treated as percentages
 * - Examples: 0.1 → 0.1%, 5 → 5%, 80 → 80%
 * @param {string|number} threshold - The threshold value
 * @returns {string} Formatted threshold string
 */
export const formatThreshold = (threshold) => {
  if (!threshold && threshold !== 0) return 'Not set';

  const numValue = parseFloat(threshold);

  // If not a valid number, return as-is
  if (isNaN(numValue)) return threshold.toString();

  // All numeric values are treated as percentages
  return `${numValue}%`;
};

export const extractFeatures = (metricData) => {
  if (Array.isArray(metricData.features)) {
    return metricData.features.map(f => typeof f === 'object' && f.feature_id ? f.feature_id : f).join(', ');
  }
  return metricData.features;
};

export const extractScalePoints = (metricData) => {
  return typeof metricData.scale_points === 'object' ? metricData.scale_points : null;
};

export const transformApiEventsToComponentFormat = (apiResponse) => {
  const eventsArray = apiResponse.events || apiResponse;
  if (!Array.isArray(eventsArray)) return [];

  const transformedEvents = eventsArray.map(event => {
    const creator = event.created_by?.full_name || event.created_by?.username ||
                   (event.is_user_defined ? 'Auditor' : event.is_audit_instigator ? 'Audit Instigator' : 'Auditor');

    const category = event.event_categories?.length > 0
      ? event.event_categories.map(cat => cat.event_name).join(', ')
      : event.primary_category || 'Uncategorized';
    const entities = event.associated_entities?.map(e => e.entity_name || e.name).join(', ') || '';

    return {
      id: event.id,
      name: event.name || event.description,
      description: event.description,
      category,
      creator,
      valence: event.valence > 0 ? 'Positive' : event.valence < 0 ? 'Negative' : 'Neutral',
      magnitude: Math.round(event.magnitude * 100),
      likelihood: Math.round(event.likelihood * 100),
      cause: event.cause || 'No cause specified',
      reason: event.reason || 'No reason provided',
      entities,
      isUserCreated: event.is_user_defined || !event.is_audit_instigator,
      metrics: (event.associated_metrics || []).map(metric => ({
        id: metric.metric_id,
        name: metric.metric_name || metric.metric_description,
        description: metric.metric_description,
        definition: metric.formula || metric.definition || 'Assessment method',
        creator: 'System',
        features: extractFeatures(metric),
        threshold: metric.threshold?.toString() || 'Not set',
        reason: metric.reason || 'Metric associated with event',
        labels: metric.metric_type || 'unknown',
        useInAudit: event.associated_pipelines.map(p => p.metric_id).includes(metric.metric_id),
        isUserCreated: metric.is_user_defined,
        metricType: metric.metric_type,
        formula: metric.formula,
        scale_points: extractScalePoints(metric),
        targetFeatures: metric.target_features,
        underlyingFeatures: metric.underlying_features,
        featureRanges: metric.feature_ranges
      }))
    };
  });

  // Sort events by id in ascending order
  return transformedEvents.sort((a, b) => a.id - b.id);
};

export const buildEventApiPayload = (eventData, auditId, changes = null, eventCategories = null, availableEntities = null, entityNameToIdMap = null) => {
  // Helper to get entity ID from name
  const getEntityId = (entityName) => {
    if (typeof entityName === 'object' && (entityName.entity_id || entityName.entities_id || entityName.id)) {
      return entityName.entity_id || entityName.entities_id || entityName.id;
    }

    // Try to get ID from the mapping (for newly created entities)
    if (entityNameToIdMap && entityNameToIdMap[entityName]) {
      return entityNameToIdMap[entityName];
    }

    // Try to find in available entities
    if (availableEntities) {
      const entity = availableEntities.find(e =>
        (e.name === entityName || e.entity_name === entityName)
      );
      if (entity) {
        return entity.id || entity.entity_id || entity.entities_id;
      }
    }

    // Fallback: if it's a number, use it as ID
    if (typeof entityName === 'number') {
      return entityName;
    }

    console.warn(`Could not find entity ID for: ${entityName}`);
    return null;
  };

  // Helper to get category ID from name
  const getCategoryId = (categoryName) => {
    if (typeof categoryName === 'object' && (categoryName.category_id || categoryName.id)) {
      return categoryName.category_id || categoryName.id;
    }

    // Try to find in available categories
    if (eventCategories) {
      const category = eventCategories.find(c =>
        (c.event_name === categoryName || c.name === categoryName)
      );
      if (category) {
        return category.id || category.category_id;
      }
    }

    // Fallback: if it's a number, use it as ID
    if (typeof categoryName === 'number') {
      return categoryName;
    }

    console.warn(`Could not find category ID for: ${categoryName}`);
    return null;
  };

  return {
    audit_id: parseInt(auditId),
    name: eventData.name || eventData.eventName,
    description: eventData.description || eventData.eventDescription || eventData.name || eventData.eventName,
    cause: eventData.cause,
    reason: eventData.reason,
    likelihood: (eventData.likelihood || 50) / 100,
    magnitude: (eventData.magnitude || 50) / 100,
    valence: eventData.valence === 'positive' ? 1.0 : -1.0,
    is_user_defined: true,
    is_template: false,
    entities: eventData.entities?.map(entity => {
      const entityId = getEntityId(entity);
      return entityId ? { entity_id: entityId } : null;
    }).filter(e => e !== null) || [],
    categories: eventData.categories?.map(category => {
      const categoryId = getCategoryId(category);
      return categoryId ? { category_id: categoryId } : null;
    }).filter(c => c !== null) || [],
    metrics: eventData.selectedMetricPairs?.length
      // Preferred path — newly-created metrics carry the values_id returned
      // from their POST so the event<->metric_value mapping is preserved.
      ? eventData.selectedMetricPairs.map(p => ({
          metric_id: p.metric_id,
          values_id: p.values_id ?? null,
        }))
      // Fallback — older callers only pass metric IDs.
      : (eventData.selectedMetricIds?.map(metricId => ({ metric_id: metricId, values_id: null })) || []),
  };
};

export const buildMetricApiPayload = (metricData, auditId, metricType) => {
  const basePayload = {
    audit_id: parseInt(auditId),
    name: metricData.name,
    description: metricData.description,
    reason: metricData.reason,
    metric_values: metricData.metric_values || [],
  };

  // Build event_mappings consistently: pull event_id off the event object.
  const eventMappings = (metricData.events || metricData.selectedEventIds || []).map(event => {
    if (typeof event === 'object' && event !== null) {
      const id = event.id ?? event.event_id;
      return id != null ? { event_id: parseInt(id) } : null;
    }
    if (typeof event === 'number' || (typeof event === 'string' && /^\d+$/.test(event))) {
      return { event_id: parseInt(event) };
    }
    return null;
  }).filter(m => m !== null);

  if (metricType === 'quantitative') {
    return {
      ...basePayload,
      formula: metricData.definition || metricData.formula || '',
      event_mappings: eventMappings,
    };
  }

  if (metricType === 'qualitative') {
    return {
      ...basePayload,
      definition: metricData.definition || '',
      event_mappings: eventMappings,
    };
  }

  return basePayload;
};

export const getSelectedMetricEventPairs = (events) => {
  const pairs = [];
  events.forEach(event => {
    event.metrics?.forEach(metric => {
      if (metric.useInAudit) {
        pairs.push({ eventId: event.id, metricId: metric.id });
      }
    });
  });
  return pairs;
};

export const hasAnySelectedMetrics = (events) => {
  return events.some(event => event.metrics?.some(metric => metric.useInAudit));
};

/**
 * Gets all selected metrics that have null/empty thresholds
 * @param {Array} events - Array of events with metrics
 * @returns {Array} Array of objects with eventId, metricId, and metricName for metrics missing thresholds
 */
export const getSelectedMetricsWithoutThreshold = (events) => {
  const metricsWithoutThreshold = [];
  events.forEach(event => {
    event.metrics?.forEach(metric => {
      if (metric.useInAudit) {
        const threshold = metric.threshold;
        // Check if threshold is null, undefined, empty string, or 'Not set' (case insensitive)
        const hasNoThreshold = threshold === null ||
          threshold === undefined ||
          threshold === '' ||
          (typeof threshold === 'string' && threshold.toLowerCase() === 'not set');
        if (hasNoThreshold) {
          metricsWithoutThreshold.push({
            eventId: event.id,
            metricId: metric.id,
            metricName: metric.name || metric.description || 'Unnamed Metric',
            eventName: event.name || event.description || 'Unnamed Event'
          });
        }
      }
    });
  });
  return metricsWithoutThreshold;
};

export const updateMetricInEvents = (events, eventId, metricId, updates) => {
  return events.map(event => 
    event.id === eventId 
      ? {
          ...event,
          metrics: event.metrics.map(metric =>
            metric.id === metricId ? { ...metric, ...updates } : metric
          )
        }
      : event
  );
};

export const checkEventMetricStatus = (auditData) => {
  const pairs = [];
  let length_pairs=0;
  auditData.events.forEach(event => {
    event.metrics?.forEach(metric => {
      // // console.log(metric)
      if (metric.recommendation !== "Not Evaluated") {
        pairs.push(true);
      }
      length_pairs+=1;
    });
  });
  // // console.log(pairs);
  return pairs.length === length_pairs ;
};

/**
 * Determines if an audit should be in read-only mode based on its status
 * @param {string} auditStatus - The status of the audit (e.g., "Finished", "In Progress")
 * @returns {boolean} - True if audit is read-only (finished), false otherwise
 */
export const isAuditReadOnly = (auditStatus) => {
  return auditStatus === "Submitted";
};