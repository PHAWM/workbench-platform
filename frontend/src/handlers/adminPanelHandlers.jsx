import { adminAPI } from '../api/apiService';

// Map the application form to the API payload (shared by create and update).
export const buildApplicationPayload = (formData) => {
  const testingEvaluation = {};
  if (formData.te_model_details) testingEvaluation.model_details = formData.te_model_details;
  if (formData.te_dataset_details) testingEvaluation.dataset_details = formData.te_dataset_details;
  if (formData.te_testing_details) testingEvaluation.testing_details = formData.te_testing_details;
  if (formData.te_audit_instigator_details) testingEvaluation.audit_instigator_details = formData.te_audit_instigator_details;

  const deployment = {};
  if (formData.deploy_version) deployment.version = formData.deploy_version;
  if (formData.deploy_environment) deployment.environment = formData.deploy_environment;

  return {
    name: formData.name,
    description: formData.description,
    organisation: formData.organisation,
    url: formData.url,
    access_type: parseInt(formData.access_type) || 0,
    testing_evaluation: testingEvaluation,
    deployment: deployment,
    business_case: formData.business_case || '',
    legal_framework: formData.legal_framework || '',
  };
};

export const handleCreateApplication = async (formData) => {
  try {
    const result = await adminAPI.createApplication(buildApplicationPayload(formData));
    return { success: true, data: result };
  } catch (error) {
    return { success: false, error: error.message || 'Failed to create application' };
  }
};

export const handleCreateModel = async (formData) => {
  try {
    const payload = {
      name: formData.name,
      model_type: parseInt(formData.model_type) || 0,
      task: formData.task,
      with_api_key: formData.with_api_key === true || formData.with_api_key === 'true',
    };
    if (formData.location) payload.location = formData.location;
    if (formData.mcp_tool_name) payload.mcp_tool_name = formData.mcp_tool_name;
    if (formData.acceptable_formats) {
      try {
        payload.acceptable_formats = JSON.parse(formData.acceptable_formats);
      } catch {
        payload.acceptable_formats = formData.acceptable_formats.split(',').map(s => s.trim()).filter(Boolean);
      }
    }
    if (formData.output_context) payload.output_context = formData.output_context;
    const result = await adminAPI.createModelMetadata(payload);
    return { success: true, data: result };
  } catch (error) {
    return { success: false, error: error.message || 'Failed to create model' };
  }
};

export const handleScaffoldModel = async (formData) => {
  try {
    const payload = {
      service_name: formData.service_name,
      tool_name: formData.tool_name,
      port: parseInt(formData.port) || 8010,
      description: formData.description || '',
      model_type: parseInt(formData.model_type) || 0,
      task: formData.task || 'classification',
      needs_s3: formData.needs_s3 === true || formData.needs_s3 === 'true',
    };
    if (formData.acceptable_formats) {
      try {
        payload.acceptable_formats = JSON.parse(formData.acceptable_formats);
      } catch {
        payload.acceptable_formats = formData.acceptable_formats.split(',').map(s => s.trim()).filter(Boolean);
      }
    }
    const result = await adminAPI.scaffoldModel(payload);
    return { success: true, data: result };
  } catch (error) {
    return { success: false, error: error.message || 'Failed to scaffold model' };
  }
};

export const handleCreateApiKey = async (formData, modelId) => {
  try {
    const payload = {
      model_api_key: formData.model_api_key,
      costing_policy: formData.costing_policy || 'pay-per-request',
      model_metadata_id: parseInt(modelId),
    };
    const result = await adminAPI.createApiKey(payload);
    return { success: true, data: result };
  } catch (error) {
    return { success: false, error: error.message || 'Failed to create API key' };
  }
};

export const handleCreateDataset = async (formData) => {
  try {
    const payload = {
      purpose: formData.purpose,
      input_metadata: formData.input_metadata || {},
      output_metadata: formData.output_metadata || {},
      target_features: formData.target_features || [],
    };
    if (formData.copyright_agreement !== undefined) {
      payload.copyright_agreement = formData.copyright_agreement;
    }
    const result = await adminAPI.createDatasetMetadata(payload);
    return { success: true, data: result };
  } catch (error) {
    return { success: false, error: error.message || 'Failed to create dataset' };
  }
};

export const handleCreateAudit = async (formData, applicationId, modelIds, datasetIds) => {
  try {
    const payload = {
      name: formData.name,
      description: formData.description,
      application_id: parseInt(applicationId),
      model_ids: modelIds.map(id => parseInt(id)),
      dataset_ids: datasetIds.map(id => parseInt(id)),
    };
    const result = await adminAPI.createAudit(payload);
    return { success: true, data: result };
  } catch (error) {
    return { success: false, error: error.message || 'Failed to create audit' };
  }
};

export const handleCreateEvent = async (formData, auditId) => {
  try {
    const payload = {
      audit_id: parseInt(auditId),
      name: formData.name,
      description: formData.description,
      cause: formData.cause || '',
      reason: formData.reason || '',
      likelihood: parseFloat(formData.likelihood) || 0.0,
      magnitude: parseFloat(formData.magnitude) || 0.0,
      valence: parseFloat(formData.valence) || 0.0,
      is_user_defined: formData.is_user_defined ?? true,
      is_template: formData.is_template ?? false,
      categories: formData.category_ids?.length
        ? formData.category_ids.map(id => ({ category_id: parseInt(id) }))
        : [],
      entities: formData.entity_ids?.length
        ? formData.entity_ids.map(id => ({ entity_id: parseInt(id) }))
        : [],
      metrics: formData.metric_ids?.length
        ? formData.metric_ids.map(id => ({ metric_id: parseInt(id), values_id: null }))
        : [],
      users: formData.user_audit_ids?.length
        ? formData.user_audit_ids.map(id => ({ user_audit_id: parseInt(id) }))
        : [],
    };
    const result = await adminAPI.createEvent(payload);
    return { success: true, data: result };
  } catch (error) {
    return { success: false, error: error.message || 'Failed to create event' };
  }
};

// Convert scale_points from either [{label, value}] or {label: value} into the
// {label: value} object the backend expects. Returns null if no points are set.
const normalizeScalePoints = (raw) => {
  if (!raw) return null;
  if (Array.isArray(raw)) {
    if (raw.length === 0) return null;
    return raw.reduce((acc, p) => {
      if (p && p.label !== undefined) acc[p.label] = p.value;
      return acc;
    }, {});
  }
  if (typeof raw === 'object') return raw;
  return null;
};

export const handleCreateMetric = async (formData, auditId) => {
  try {
    let result;
    // Support one or more selected events. Fall back to the legacy single event_id.
    const eventIds = formData.event_ids?.length
      ? formData.event_ids
      : (formData.event_id != null && formData.event_id !== '' ? [formData.event_id] : []);
    const eventMappings = eventIds.map(id => ({ event_id: parseInt(id) }));
    // Parse a feature's optional comma-separated ranges string into an array of trimmed values
    const rangesFor = (featureId) => {
      const raw = formData.feature_ranges?.[featureId];
      if (!raw) return [];
      return raw.split(',').map(r => r.trim()).filter(Boolean);
    };
    if (formData.type === 'quantitative') {
      const metricValue = {
        threshold: formData.threshold || '0',
        output: null,
        scale_points: null,
        underlying_features: formData.underlying_feature_ids?.length
          ? formData.underlying_feature_ids.map(id => ({ feature_id: parseInt(id), ranges: rangesFor(id) }))
          : [],
        target_features: formData.target_feature_id
          ? [{ feature_id: parseInt(formData.target_feature_id), ranges: rangesFor(formData.target_feature_id) }]
          : [],
      };
      const payload = {
        audit_id: parseInt(auditId),
        name: formData.name,
        description: formData.description,
        reason: formData.reason || '',
        formula: formData.formula || '',
        metric_values: [metricValue],
        event_mappings: eventMappings,
      };
      result = await adminAPI.createQuantitativeMetric(payload);
    } else {
      const payload = {
        audit_id: parseInt(auditId),
        name: formData.name,
        description: formData.description,
        reason: formData.reason || '',
        definition: formData.definition || '',
        metric_values: [{
          threshold: formData.threshold || '',
          scale_points: normalizeScalePoints(formData.scale_points),
          output: null,
          underlying_features: [],
          target_features: formData.target_feature_id
            ? [{ feature_id: parseInt(formData.target_feature_id), ranges: rangesFor(formData.target_feature_id) }]
            : [],
        }],
        event_mappings: eventMappings,
      };
      result = await adminAPI.createQualitativeMetric(payload);
    }
    return { success: true, data: result };
  } catch (error) {
    return { success: false, error: error.message || 'Failed to create metric' };
  }
};

export const handleMapEventsToPipeline = async (auditPipelineId, mappings, auditId) => {
  try {
    const parsedPipelineId = parseInt(auditPipelineId);
    if (!parsedPipelineId || isNaN(parsedPipelineId)) {
      return { success: false, error: 'Audit pipeline ID is missing. Please complete the audit creation step first.' };
    }
    const payload = {
      audit_pipeline_id: parsedPipelineId,
      audit_id: parseInt(auditId),
      mappings: mappings.map(m => ({
        event_id: parseInt(m.event_id),
        metric_id: parseInt(m.metric_id),
      })),
    };
    const result = await adminAPI.batchCreatePipelineMappings(payload);
    return { success: true, data: result };
  } catch (error) {
    return { success: false, error: error.message || 'Failed to map events to pipeline' };
  }
};

export const handleImportDataset = async (formData) => {
  try {
    const payload = {
      source_type: formData.source_type,
      dataset_name: formData.dataset_name,
      purpose: formData.purpose || '',
    };
    if (formData.split) payload.split = formData.split;
    if (formData.subset) payload.subset = formData.subset;
    if (formData.max_samples) payload.max_samples = parseInt(formData.max_samples);
    if (formData.label_column) payload.label_column = formData.label_column;
    if (formData.text_column) payload.text_column = formData.text_column;
    if (formData.target_features && formData.target_features.length > 0) {
      payload.target_features = formData.target_features;
    }
    if (formData.underlying_feature_columns && formData.underlying_feature_columns.length > 0) {
      payload.underlying_feature_columns = formData.underlying_feature_columns;
    }
    if (formData.audit_id) payload.audit_id = parseInt(formData.audit_id);
    const result = await adminAPI.importDataset(payload);
    return { success: true, data: result };
  } catch (error) {
    return { success: false, error: error.message || 'Failed to import dataset' };
  }
};

export const handleInviteAuditor = async (email, auditId) => {
  try {
    const result = await adminAPI.inviteAuditor(auditId, email);
    return { success: true, data: result };
  } catch (error) {
    return { success: false, error: error.message || 'Failed to invite auditor' };
  }
};
