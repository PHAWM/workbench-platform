// utils/formUtils.js
import { eventsAPI } from '../api/apiService';

// Helper function to detect and create new entities
// Returns a mapping of entity names to their IDs (both existing and newly created)
export const detectAndCreateNewEntities = async (formData, availableEntities, auditId) => {
  // console.log('🔍 detectAndCreateNewEntities called with:', {
  //   formData,
  //   availableEntities: availableEntities?.length,
  //   auditId
  // });

  // Create a mapping of entity names to IDs
  const entityNameToIdMap = {};
  const newEntities = [];

  // Check entities
  if (formData.entities && Array.isArray(formData.entities)) {
    // console.log('Checking entities:', formData.entities);
    for (const entityName of formData.entities) {
      const existingEntity = availableEntities?.find(e =>
        e.name === entityName || e.entity_name === entityName
      );

      if (existingEntity) {
        // Entity already exists - use its ID
        // API can return id, entity_id, or entities_id
        const entityId = existingEntity.id || existingEntity.entity_id || existingEntity.entities_id;
        // console.log(`  - ${entityName}: exists with ID ${entityId}`);
        entityNameToIdMap[entityName] = entityId;
      } else if (typeof entityName === 'string') {
        // New entity - mark for creation
        // console.log(`  - ${entityName}: NEW - needs to be created`);
        newEntities.push(entityName);
      }
    }
  }

  // Check if we need to get num_individuals from formData
  // This will be populated from the popup
  const entityDetails = formData.entityDetails || {};

  // Post new entities to the API and get their IDs
  const createdEntities = [];

  for (const entityName of newEntities) {
    try {
      // Get num_individuals from formData, default to 1 if not specified
      const numIndividuals = entityDetails[entityName] || 1;

      // console.log(`Posting new entity: ${entityName} with ${numIndividuals} individuals for audit ${auditId}`);
      const result = await eventsAPI.createEntity(entityName, numIndividuals, parseInt(auditId));
      createdEntities.push(result);

      // Map the entity name to its newly created ID
      // API can return id, entity_id, or entities_id
      const entityId = result.id || result.entity_id || result.entities_id;
      entityNameToIdMap[entityName] = entityId;

      // console.log(`Created new entity: ${entityName} with ID ${entityId}`, result);
    } catch (error) {
      console.error(`Failed to create entity: ${entityName}`, error);
      throw error; // Re-throw to prevent event creation with missing entities
    }
  }

  // console.log(`Created ${createdEntities.length} new entity/entities. Entity map:`, entityNameToIdMap);

  return {
    createdEntities,
    entityNameToIdMap
  };
};

// Helper function to detect and create new features
// Returns a mapping of feature names to their IDs (both existing and newly created)
export const detectAndCreateNewFeatures = async (formData, availableUnderlyingFeatures, availableTargetFeatures, auditId) => {
  // console.log('🔍 detectAndCreateNewFeatures called with:', {
  //   formData,
  //   availableUnderlyingFeatures: availableUnderlyingFeatures?.length,
  //   availableTargetFeatures: availableTargetFeatures?.length,
  //   auditId
  // });

  // Create a mapping of feature names to IDs
  const featureNameToIdMap = {};
  const newUnderlyingFeatures = [];
  const newTargetFeatures = [];

  // Check distinguishing factors (for both quant and qual metrics)
  if (formData.underlyingFeatures && Array.isArray(formData.underlyingFeatures)) {
    // console.log('Checking distinguishing factors:', formData.underlyingFeatures);
    for (const featureName of formData.underlyingFeatures) {
      const existingFeature = availableUnderlyingFeatures?.find(f =>
        f.feature_name === featureName || f.name === featureName
      );

      if (existingFeature) {
        // Feature already exists - use its ID
        // console.log(`  - ${featureName}: exists with ID ${existingFeature.id}`);
        featureNameToIdMap[featureName] = existingFeature.id;
      } else if (typeof featureName === 'string') {
        // New feature - mark for creation
        // console.log(`  - ${featureName}: NEW - needs to be created`);
        newUnderlyingFeatures.push(featureName);
      }
    }
  }

  // Check targets (for quantitative metrics)
  if (formData.targetFeatures && Array.isArray(formData.targetFeatures)) {
    // console.log('Checking targets:', formData.targetFeatures);
    for (const featureName of formData.targetFeatures) {
      const existingFeature = availableTargetFeatures?.find(f =>
        f.target_feature === featureName || f.name === featureName
      );

      if (existingFeature) {
        // Feature already exists - use its ID
        // console.log(`  - ${featureName}: exists with ID ${existingFeature.id}`);
        featureNameToIdMap[featureName] = existingFeature.id;
      } else if (typeof featureName === 'string') {
        // New target feature - mark for creation
        // console.log(`  - ${featureName}: NEW target feature - needs to be created`);
        newTargetFeatures.push(featureName);
      }
    }
  }

  // Post new distinguishing factors to the API and get their IDs
  const createdFeatures = [];

  for (const featureName of newUnderlyingFeatures) {
    try {
      // console.log(`Posting new underlying feature: ${featureName} for audit ${auditId}`);
      const result = await eventsAPI.createUserFeature(featureName, auditId);
      createdFeatures.push(result);

      // Map the feature name to its newly created ID
      const featureId = result.id || result.feature_id;
      featureNameToIdMap[featureName] = featureId;

      // console.log(`Created new underlying feature: ${featureName} with ID ${featureId}`, result);
    } catch (error) {
      console.error(`Failed to create underlying feature: ${featureName}`, error);
      throw error; // Re-throw to prevent metric creation with missing features
    }
  }

  // Post new targets to the API and get their IDs
  for (const featureName of newTargetFeatures) {
    try {
      // console.log(`Posting new target feature: ${featureName} for audit ${auditId}`);
      const result = await eventsAPI.createUserTargetFeature(featureName, auditId);
      createdFeatures.push(result);

      // Map the feature name to its newly created ID
      const featureId = result.id || result.feature_id;
      featureNameToIdMap[featureName] = featureId;

      // console.log(`Created new target feature: ${featureName} with ID ${featureId}`, result);
    } catch (error) {
      console.error(`Failed to create target feature: ${featureName}`, error);
      throw error; // Re-throw to prevent metric creation with missing features
    }
  }

  // console.log(`Created ${createdFeatures.length} new feature(s) (${newUnderlyingFeatures.length} underlying, ${newTargetFeatures.length} target). Feature map:`, featureNameToIdMap);

  return {
    createdFeatures,
    featureNameToIdMap
  };
};

// Feature ID/Name mapping utilities (PRESERVED)
export const getUnderlyingFeatureId = (selectedValue, availableFeatures, featureNameToIdMap = null) => {
  if (typeof selectedValue === 'number') return selectedValue;

  // First, check if we have a mapping from newly created features
  if (featureNameToIdMap && featureNameToIdMap[selectedValue]) {
    // console.log(`Using mapped ID for feature: ${selectedValue} -> ${featureNameToIdMap[selectedValue]}`);
    return featureNameToIdMap[selectedValue];
  }

  if (!availableFeatures || !Array.isArray(availableFeatures)) {
    console.warn('availableUnderlyingFeatures is not available or not an array');
    return selectedValue;
  }

  let feature = availableFeatures.find(f => f.feature_name === selectedValue);

  if (!feature) {
    feature = availableFeatures.find(f =>
      f.feature_name.toLowerCase() === selectedValue.toLowerCase()
    );
  }

  if (!feature) {
    feature = availableFeatures.find(f =>
      f.feature_name.trim() === selectedValue.trim()
    );
  }

  if (feature) {
    // console.log(`Found feature: ${feature.feature_name} with ID: ${feature.id}`);
    return feature.id;
  }

  return selectedValue;
};

export const getTargetFeatureId = (selectedValue, availableFeatures, featureNameToIdMap = null) => {
  if (typeof selectedValue === 'number') return selectedValue;

  // First, check if we have a mapping from newly created features
  if (featureNameToIdMap && featureNameToIdMap[selectedValue]) {
    // console.log(`Using mapped ID for target feature: ${selectedValue} -> ${featureNameToIdMap[selectedValue]}`);
    return featureNameToIdMap[selectedValue];
  }

  if (!availableFeatures || !Array.isArray(availableFeatures)) {
    console.warn('availableTargetFeatures is not available or not an array');
    return selectedValue;
  }

  let feature = availableFeatures.find(f => f.target_feature === selectedValue);

  if (!feature) {
    feature = availableFeatures.find(f =>
      f.target_feature?.toLowerCase() === selectedValue.toLowerCase()
    );
  }

  if (!feature) {
    feature = availableFeatures.find(f =>
      f.target_feature?.trim() === selectedValue.trim()
    );
  }

  if (feature) {
    // console.log(`Found target feature: ${feature.target_feature} with ID: ${feature.id}`);
    return feature.id;
  }

  return selectedValue;
};

export const getUnderlyingFeatureName = (selectedValue, availableFeatures) => {
  if (typeof selectedValue === 'string') return selectedValue;
  const feature = availableFeatures.find(f => f.id === selectedValue);
  return feature ? feature.feature_name : selectedValue.toString();
};

// Form data transformation utilities (PRESERVED)
export const stringToArray = (value) => {
  if (Array.isArray(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    return value.split(',').map(item => item.trim()).filter(item => item);
  }
  return [];
};

export const parseUnderlyingFeatures = (featuresData, availableUnderlyingFeatures) => {
  // console.log('Parsing distinguishing factors:', featuresData);
  if (!featuresData) return [];
  
  if (Array.isArray(featuresData)) {
    return featuresData.map(f => {
      if (typeof f === 'object' && f.feature_id) {
        const feature = availableUnderlyingFeatures.find(af => af.id === f.feature_id);
        const featureName = feature ? (feature.feature_name || feature.name || `Feature ${f.feature_id}`) : `Feature ${f.feature_id}`;
        // console.log(`Converted feature object ${JSON.stringify(f)} to string: ${featureName}`);
        return featureName;
      }
      return typeof f === 'string' ? f : String(f);
    });
  }
  
  if (typeof featuresData === 'string') {
    return featuresData.split(',').map(f => f.trim()).filter(f => f);
  }
  
  return [];
};

export const parseTargetFeatures = (featuresData, availableTargetFeatures) => {
  // console.log('Parsing targets:', featuresData);
  if (!featuresData) return [];
  
  if (Array.isArray(featuresData)) {
    return featuresData.map(f => {
      if (typeof f === 'object' && f.target_feature_id) {
        const feature = availableTargetFeatures.find(af => af.id === f.target_feature_id);
        const featureName = feature ? (feature.target_feature || feature.name || `Target ${f.target_feature_id}`) : `Target ${f.target_feature_id}`;
        // console.log(`Converted target feature object ${JSON.stringify(f)} to string: ${featureName}`);
        return featureName;
      }
      return typeof f === 'string' ? f : String(f);
    });
  }
  
  return [];
};

export const parseScalePoints = (scalePointsData) => {
  // console.log('parseScalePoints input:', scalePointsData);

  if (!scalePointsData) return { points: '', labels: [], scalePointsArray: [] };

  if (typeof scalePointsData === 'object') {
    let scalePoints = null;

    // Handle nested structure: {scale_points: {"Low": 1, "Medium": 2}}
    if (scalePointsData.scale_points) {
      scalePoints = scalePointsData.scale_points;
    }
    // Handle direct structure: {"Low": 1, "Medium": 2, "High": 3}
    // Check if all values are numbers (likely a direct scale_points object)
    else if (Object.keys(scalePointsData).length > 0) {
      const allValuesAreNumbers = Object.values(scalePointsData).every(
        val => typeof val === 'number' || !isNaN(parseFloat(val))
      );

      if (allValuesAreNumbers && !scalePointsData.points && !scalePointsData.labels) {
        scalePoints = scalePointsData;
      }
    }

    // If we found scale points data (either nested or direct)
    if (scalePoints) {
      const points = Object.keys(scalePoints).length.toString();
      const labels = Object.keys(scalePoints);

      // Create array with correct structure: {value: number, label: string}
      // Use parseFloat to handle both integers and floats
      const scalePointsArray = Object.entries(scalePoints)
        .map(([label, value]) => ({
          value: parseFloat(value),
          label: label
        }))
        .sort((a, b) => a.value - b.value);

      // console.log('Parsed scalePointsArray:', scalePointsArray);
      return { points: points, labels, scalePointsArray };
    }

    // Fallback for other object structures (legacy format)
    const points = scalePointsData.points || '';
    const labels = scalePointsData.labels || [];
    const scalePointsArray = labels.map((label, index) => ({
      value: index + 1,
      label
    }));
    return { points: points.toString(), labels, scalePointsArray };
  }

  if (typeof scalePointsData === 'string') {
    return { points: scalePointsData, labels: [], scalePointsArray: [] };
  }

  return { points: '', labels: [], scalePointsArray: [] };
};

export const parseFeatureRanges = (metric, availableUnderlyingFeatures) => {
  if (metric.featureRanges) return metric.featureRanges;
  
  if (metric.underlyingFeatures && Array.isArray(metric.underlyingFeatures)) {
    const ranges = {};
    metric.underlyingFeatures.forEach(feature => {
      let featureData = feature;
      
      if (typeof feature === 'string' && feature.startsWith('{')) {
        try {
          featureData = JSON.parse(feature);
        } catch (e) {
          return;
        }
      }
      
      if (featureData?.ranges && Array.isArray(featureData.ranges)) {
        const foundFeature = availableUnderlyingFeatures?.find(af => af.id === featureData.feature_id);
        const featureName = foundFeature ? foundFeature.feature_name : `Feature ${featureData.feature_id}`;
        
        ranges[featureName] = {
          group1: featureData.ranges[0] || '',
          group2: featureData.ranges[1] || ''
        };
      }
    });
    if (Object.keys(ranges).length > 0) return ranges;
  }
  
  return {};
};

// Form validation utilities (PRESERVED)
export const validateRequiredFields = (formData, requiredFields) => {
  const missingFields = requiredFields.filter(field => {
    if (field === 'targetFeatures' || field === 'underlyingFeatures' || field === 'categories' || field === 'entities') {
      return !formData[field] || formData[field].length === 0;
    }
    return !formData[field];
  });
  return missingFields;
};

export const validateFeatureRanges = (formData) => {
  // Determine the number of groups that should be validated
  const numGroups = formData.featureGroups === 'Minimum of 2'
    ? 2
    : parseInt(formData.featureGroups) || 2;

  return formData.underlyingFeatures?.filter(feature => {
    const ranges = formData.featureRanges?.[feature];
    if (!ranges) return true;

    // Check that all groups have values
    for (let i = 1; i <= numGroups; i++) {
      if (!ranges[`group${i}`]) {
        return true; // Feature is incomplete
      }
    }
    return false; // Feature is complete
  }) || [];
};

// Change detection utilities (PRESERVED)
// Enhanced change detection utilities with deep object comparison
export const deepEqual = (obj1, obj2) => {
  if (obj1 === obj2) return true;
  
  if (obj1 == null || obj2 == null) return obj1 === obj2;
  
  if (typeof obj1 !== typeof obj2) return false;
  
  if (Array.isArray(obj1) && Array.isArray(obj2)) {
    if (obj1.length !== obj2.length) return false;
    const sorted1 = [...obj1].sort();
    const sorted2 = [...obj2].sort();
    return sorted1.every((val, index) => deepEqual(val, sorted2[index]));
  }
  
  if (typeof obj1 === 'object') {
    const keys1 = Object.keys(obj1);
    const keys2 = Object.keys(obj2);
    
    if (keys1.length !== keys2.length) return false;
    
    return keys1.every(key => 
      keys2.includes(key) && deepEqual(obj1[key], obj2[key])
    );
  }
  
  return obj1 === obj2;
};

export const hasFormChanges = (formData, originalData) => {
  if (!originalData) return Object.keys(formData).length > 0;
  if (!formData) return Object.keys(originalData).length > 0;
  
  // Check if any keys are different
  const allKeys = new Set([...Object.keys(formData), ...Object.keys(originalData)]);
  
  for (const key of allKeys) {
    if (!(key in formData) || !(key in originalData)) {
      return true; // Key was added or removed
    }
    
    if (!deepEqual(formData[key], originalData[key])) {
      return true;
    }
  }
  
  return false;
};

export const getFormChanges = (formData, originalData) => {
  const changes = {};
  
  // Handle null/undefined cases
  if (!originalData || typeof originalData !== 'object') {
    // No original data - everything in formData is new
    if (formData && typeof formData === 'object') {
      for (const key in formData) {
        if (formData[key] !== undefined) {
          changes[key] = { from: undefined, to: formData[key] };
        }
      }
    }
    return changes;
  }
  
  if (!formData || typeof formData !== 'object') {
    // No form data - everything in originalData was removed
    for (const key in originalData) {
      if (originalData[key] !== undefined) {
        changes[key] = { from: originalData[key], to: undefined };
      }
    }
    return changes;
  }

  // Get all unique keys from both objects
  const allKeys = new Set([...Object.keys(formData), ...Object.keys(originalData)]);

  for (const key of allKeys) {
    const hasInForm = key in formData;
    const hasInOriginal = key in originalData;
    const currentValue = formData[key];
    const originalValue = originalData[key];
    
    if (!hasInForm && hasInOriginal) {
      // Key was removed
      changes[key] = { from: originalValue, to: undefined };
    } else if (hasInForm && !hasInOriginal) {
      // Key was added
      changes[key] = { from: undefined, to: currentValue };
    } else if (hasInForm && hasInOriginal) {
      // Key exists in both - check if values changed
      if (!deepEqual(currentValue, originalValue)) {
        changes[key] = { from: originalValue, to: currentValue };
      }
    }
  }

  return changes;
};

// Helper function to get a flat representation of changes for logging/display
export const getChangesSummary = (changes) => {
  const summary = [];
  
  for (const [key, change] of Object.entries(changes)) {
    const { from, to } = change;
    
    if (from === undefined) {
      summary.push(`${key}: added (${JSON.stringify(to)})`);
    } else if (to === undefined) {
      summary.push(`${key}: removed (was ${JSON.stringify(from)})`);
    } else {
      summary.push(`${key}: changed from ${JSON.stringify(from)} to ${JSON.stringify(to)}`);
    }
  }
  
  return summary;
};

// Helper function to check if a specific field has changes
export const hasFieldChanged = (fieldName, formData, originalData) => {
  if (!originalData) return fieldName in formData;
  if (!formData) return fieldName in originalData;
  
  const currentValue = formData[fieldName];
  const originalValue = originalData[fieldName];
  
  return !deepEqual(currentValue, originalValue);
};

// CORRECTED: API payload builders to match original exactly
export const buildQuantitativeMetricValues = (formData, availableUnderlyingFeatures, availableTargetFeatures, featureNameToIdMap = null) => {
  // EXACTLY as in original QuantitativeMetricForm
  const underlyingFeaturesWithIds = formData.underlyingFeatures?.map(feature => {
    const featureId = getUnderlyingFeatureId(feature, availableUnderlyingFeatures, featureNameToIdMap);
    const featureName = getUnderlyingFeatureName(feature, availableUnderlyingFeatures);

    // Determine number of groups and collect all group ranges dynamically
    const numGroups = formData.featureGroups === 'Minimum of 2'
      ? 2
      : parseInt(formData.featureGroups) || 2;

    const ranges = [];
    if (formData.featureRanges?.[featureName]) {
      for (let i = 1; i <= numGroups; i++) {
        const groupValue = formData.featureRanges[featureName][`group${i}`];
        if (groupValue) {
          ranges.push(groupValue);
        }
      }
    }

    const mappedFeature = {
      feature_id: featureId,
      ranges: ranges
    };

    // console.log(`Mapped feature "${featureName}" to:`, mappedFeature);
    return mappedFeature;
  }) || [];

  const targetFeaturesWithIds = formData.targetFeatures?.map(feature => {
    const featureId = getTargetFeatureId(feature, availableTargetFeatures, featureNameToIdMap);

    const mappedFeature = {
      feature_id: featureId,
    };
    return mappedFeature;
  }) || [];

  return [{
    output: null,
    threshold: formData.threshold?.toString() || "0",
    underlying_features: underlyingFeaturesWithIds,
    target_features: targetFeaturesWithIds,
    scale_points: null
  }];
};

export const buildQualitativeMetricValues = (formData, availableUnderlyingFeatures, featureNameToIdMap = null) => {
  // CORRECTED: Use the right field name - it's formData.features in qualitative forms, not underlyingFeatures
  const featuresArray = formData.underlyingFeatures?.map(feature => {
    const featureId = getUnderlyingFeatureId(feature, availableUnderlyingFeatures, featureNameToIdMap);
    const featureName = getUnderlyingFeatureName(feature, availableUnderlyingFeatures);

    const mappedFeature = {
      feature_id: featureId,
      ranges: formData.featureRanges?.[featureName] ?
        [formData.featureRanges[featureName].group1, formData.featureRanges[featureName].group2] : []
    };

    // console.log(`Mapped feature  "${featureName}" to:`, mappedFeature);
    return mappedFeature;
  }) || [];

  const scalePoints = formData.scalePointsArray?.reduce((acc, item) => {
    acc[item.label] = item.value;
    return acc;
  }, {}) || {};

  return [{
    output: null,
    threshold: formData.threshold || 'Not specified',
    underlying_features: featuresArray,
    scale_points: scalePoints
  }];
};

// Event form utilities (PRESERVED exactly as original)
export const transformCategoriesForAPI = (categories, eventCategories) => {
  if (!Array.isArray(categories) || categories.length === 0) return [];
  
  return categories.map(categoryName => {
    const matchingCategory = eventCategories.find(cat => 
      (cat.event_name || cat.name || cat) === categoryName
    );
    
    if (matchingCategory?.id) {
      return { category_id: matchingCategory.id };
    }
    
    console.warn(`Category "${categoryName}" not found in available categories`);
    return null;
  }).filter(Boolean);
};

export const transformEntitiesForAPI = (entityNames, entities) => {
  if (!Array.isArray(entityNames) || entityNames.length === 0) return [];
  
  return entityNames.map(entityName => {
    const matchingEntity = entities.find(ent => 
      (ent.name || ent.entity_name || ent) === entityName
    );
    
    if (matchingEntity?.id) {
      return { entity_id: matchingEntity.id };
    }
    
    console.warn(`Entity "${entityName}" not found in available entities`);
    return null;
  }).filter(Boolean);
};

// CORRECTED: Event API payload builder to handle both new events and edits
export const buildEventApiPayload = (formData, auditId, changes = null, eventCategories = [], entities = []) => {
  const basePayload = {
    audit_id: parseInt(auditId)
  };

  // For edits - only include changed fields 
  if (changes) {
    if (changes.eventName || changes.name) {
      basePayload.name = (formData.eventName || formData.name)?.trim();
    }
    if (changes.eventDescription || changes.description) {
      basePayload.description = (formData.eventDescription || formData.description)?.trim();
    }
    if (changes.cause) basePayload.cause = formData.cause?.trim();
    if (changes.reason) basePayload.reason = formData.reason?.trim();
    if (changes.likelihood) basePayload.likelihood = parseFloat((formData.likelihood / 100).toFixed(2));
    if (changes.magnitude) basePayload.magnitude = parseFloat((formData.magnitude / 100).toFixed(2));
    if (changes.valence) basePayload.valence = formData.valence === 'positive' ? 1.0 : -1.0;
    
    if (changes.entities) {
      const transformedEntities = transformEntitiesForAPI(formData.entities, entities);
      basePayload.entities = transformedEntities.length > 0 ? transformedEntities : null;
    }
    if (changes.categories) {
      const transformedCategories = transformCategoriesForAPI(formData.categories, eventCategories);
      basePayload.categories = transformedCategories.length > 0 ? transformedCategories : null;
    }
  } else {
    // For new events - include all fields exactly as original
    basePayload.name = (formData.eventName || formData.name)?.trim();
    basePayload.description = (formData.eventDescription || formData.description)?.trim();
    basePayload.cause = formData.cause?.trim();
    basePayload.reason = formData.reason?.trim();
    basePayload.likelihood = formData.likelihood / 100;
    basePayload.magnitude = formData.magnitude / 100;
    basePayload.valence = formData.valence === 'positive' ? 1.0 : -1.0;
    basePayload.is_user_defined = true;
    basePayload.is_template = false;
    
    // CORRECTED: Transform for API format
    basePayload.entities = transformEntitiesForAPI(formData.entities, entities);
    basePayload.categories = transformCategoriesForAPI(formData.categories, eventCategories);
    basePayload.metrics = formData.selectedMetricIds?.map(metricId => ({ 
      metric_id: metricId, 
      values_id: null 
    })) || [];
  }

  return basePayload;
};

// Form field handlers (PRESERVED)
export const createFormHandlers = (formData, setFormData) => {
  const handleInputChange = (field, value) => {
    setFormData(prev => {
      // If changing featureGroups, update all feature ranges to match
      if (field === 'featureGroups') {
        const numGroups = value === 'Minimum of 2' ? 2 : parseInt(value) || 2;
        const newFeatureRanges = { ...prev.featureRanges };

        // Update all existing features to have the correct number of groups
        Object.keys(newFeatureRanges).forEach(featureName => {
          const existingRanges = newFeatureRanges[featureName];
          const updatedRanges = {};
          for (let i = 1; i <= numGroups; i++) {
            updatedRanges[`group${i}`] = existingRanges?.[`group${i}`] || '';
          }
          newFeatureRanges[featureName] = updatedRanges;
        });

        return { ...prev, [field]: value, featureRanges: newFeatureRanges };
      }

      return { ...prev, [field]: value };
    });
  };

  const handleSliderChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: parseInt(value) }));
  };

  const handleUnderlyingFeaturesChange = (features) => {
    setFormData(prev => {
      const newFeatureRanges = { ...prev.featureRanges };

      // Determine number of groups
      const numGroups = prev.featureGroups === 'Minimum of 2'
        ? 2
        : parseInt(prev.featureGroups) || 2;

      // Remove ranges for features no longer selected
      Object.keys(newFeatureRanges).forEach(featureName => {
        const stillSelected = features.some(f =>
          (typeof f === 'string' ? f : f.toString()) === featureName
        );
        if (!stillSelected) {
          delete newFeatureRanges[featureName];
        }
      });

      // Add empty ranges for new features with dynamic number of groups
      features.forEach(feature => {
        const featureName = typeof feature === 'string' ? feature : feature.toString();
        if (!newFeatureRanges[featureName]) {
          const ranges = {};
          for (let i = 1; i <= numGroups; i++) {
            ranges[`group${i}`] = '';
          }
          newFeatureRanges[featureName] = ranges;
        } else {
          // Update existing features to match the current number of groups
          const existingRanges = newFeatureRanges[featureName];
          const updatedRanges = {};
          for (let i = 1; i <= numGroups; i++) {
            updatedRanges[`group${i}`] = existingRanges[`group${i}`] || '';
          }
          newFeatureRanges[featureName] = updatedRanges;
        }
      });

      return {
        ...prev,
        underlyingFeatures: features,
        featureRanges: newFeatureRanges
      };
    });
  };

  const handleFeatureRangeChange = (feature, group, value) => {
    setFormData(prev => ({
      ...prev,
      featureRanges: {
        ...prev.featureRanges,
        [feature]: {
          ...prev.featureRanges[feature],
          [group]: value
        }
      }
    }));
  };

  return {
    handleInputChange,
    handleSliderChange,
    handleUnderlyingFeaturesChange,
    handleFeatureRangeChange
  };
};