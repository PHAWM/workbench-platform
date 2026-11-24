const API_BASE_URL = import.meta.env.VITE_API_URL;

// Tenant ID is a build-time constant — set via VITE_TENANT_ID env var.
// Each tenant gets its own deployment under /workbench/<tenantId>/.
const _resolveTenantId = () => import.meta.env.VITE_TENANT_ID || null;

// Token storage helper functions
const TokenStorage = {
  setToken: (token) => {
    // Store in both sessionStorage and memory for extra security
    sessionStorage.setItem('authToken', token);
    // Set expiry time (e.g., 24 hours from now)
    const expiryTime = Date.now() + (24 * 60 * 60 * 1000);
    sessionStorage.setItem('authTokenExpiry', expiryTime.toString());
  },

  getToken: () => {
    const token = sessionStorage.getItem('authToken');
    const expiry = sessionStorage.getItem('authTokenExpiry');

    // Check if token exists and is not expired
    if (token && expiry) {
      if (Date.now() < parseInt(expiry)) {
        return token;
      } else {
        // Token expired, clear it
        TokenStorage.clearToken();
        return null;
      }
    }
    return null;
  },

  clearToken: () => {
    sessionStorage.removeItem('authToken');
    sessionStorage.removeItem('authTokenExpiry');
    localStorage.removeItem('authToken'); // Clear legacy storage if exists
  },

  isTokenExpired: () => {
    const expiry = sessionStorage.getItem('authTokenExpiry');
    return expiry ? Date.now() >= parseInt(expiry) : true;
  },

  // Tenant ID — stored only for the duration of the session.
  // After login the JWT embeds the tenant (tid claim) so this is only
  // needed to send X-Tenant-ID on the login request itself.
  setTenantId: (tenantId) => {
    if (tenantId) {
      sessionStorage.setItem('tenantId', tenantId);
    }
  },

  getTenantId: () => sessionStorage.getItem('tenantId'),

  clearTenantId: () => sessionStorage.removeItem('tenantId'),
};

// Generic API request handler
const apiRequest = async (endpoint, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  const token = TokenStorage.getToken();

  // Build headers
  const headers = {};

  if (token) {
    // Authenticated request — Bearer token carries the tid claim so the
    // backend resolves the tenant schema automatically.
    headers['Authorization'] = `Bearer ${token}`;
  } else {
    // Unauthenticated request (invite, verify-email, forgot/reset-password).
    // The backend needs X-Tenant-ID to know which schema to query.
    const tenantId = _resolveTenantId();
    if (tenantId) {
      headers['X-Tenant-ID'] = tenantId;
    }
  }

  // Add Content-Type for JSON requests (unless it's a file upload)
  if (!options.isFileUpload) {
    headers['Content-Type'] = 'application/json';
  }

  // Merge with any custom headers (but don't override Authorization)
  if (options.headers) {
    Object.keys(options.headers).forEach(key => {
      if (key !== 'Authorization' && options.headers[key] !== null) {
        headers[key] = options.headers[key];
      }
    });
  }

  const config = {
    headers,
    ...options,
  };

  // Remove isFileUpload from config as it's not a fetch option
  delete config.isFileUpload;

  try {
    const response = await fetch(url, config);

    if (!response.ok) {

      let errorData;
      try {
        errorData = await response.json();
      } catch (parseError) {
        errorData = null; // In case the server didn't return JSON
      }

      // Handle 403 Forbidden errors
      if (response.status === 403) {
        console.error('403 Forbidden: Access denied');
        // Clear any stored authentication data
        TokenStorage.clearToken();

        // Redirect to 403 error page
        window.location.href = (import.meta.env.BASE_URL || '/') + '403';
        throw new Error('Access forbidden. Redirecting to login...');
      }

      if (response.status === 401) {
        console.error('401 Unauthorized: Token expired or invalid');
        // Clear any stored authentication data
        TokenStorage.clearToken();

        // Redirect to login page
        window.location.href = (import.meta.env.BASE_URL || '/') + 'login';
        throw new Error('Unauthorized. Please log in again.');
      }

      const customError = new Error(errorData?.detail || `HTTP error! status: ${response.status}`);
      customError.response = { 
        data: errorData, 
        status: response.status 
      };

      throw customError;
    }

    return await response.json();
  } catch (error) {
    // Don't log if it's a 403 (already handled)
    if (!error.message.includes('403') && !error.message.includes('forbidden')) {
      console.error(`API request failed: ${endpoint}`, error);
    }
    throw error;
  }
};

// Dashboard API - Based on Application and Audit tables
export const dashboardAPI = {
  // Get all audits 
  getApplications: () => apiRequest('/audits/'),

  // Get specific application with audits
  getApplication: (applicationId) => apiRequest(`/audits/${applicationId}`),

  // Update application
  updateApplication: (auditId, auditData) => apiRequest(`/audits/${auditId}`, {
    method: 'PUT',
    body: JSON.stringify(auditData),
  }),

  // Create new audit for application
  createAudit: (auditData) => apiRequest('/audits/', {
    method: 'POST',
    body: JSON.stringify(auditData),
  }),

  // Get audit details
  getAudit: (auditId) => apiRequest(`/audits/${auditId}`)
};

// AI Application Overview API - Based on Application table
export const aiApplicationAPI = {
  // Get application overview data (same as dashboard but focused on single app)
  getApplicationOverview: (auditId) => apiRequest(`/audits/${auditId}`),

  // Update application overview
  updateApplicationOverview: (applicationId, applicationData) => apiRequest(`/audits/applications/${applicationId}`, {
    method: 'PUT',
    body: JSON.stringify(applicationData),
  }),
};

// Events API - Based on Events, EventType, EventValues, and mapping tables
export const eventsAPI = {
  // Get all events with enhanced filtering
  getEvents: (auditId, params = {}) => {
    const queryParams = new URLSearchParams({
      audit_id: auditId,
      use_custom_values: 'true',
      ...params
    });
    return apiRequest(`/events/all?${queryParams}`);
  },

  // Get single event with full details
  getEvent: (eventId, useCustomValues = true) =>
    apiRequest(`/events/by-event/${eventId}?use_custom_values=${useCustomValues}`),

  // Create new event with type and custom values
  createEvent: (eventData) => apiRequest('/events/comprehensive', {
    method: 'POST',
    body: JSON.stringify(eventData),
  }),

  // Update existing event comprehensively
  updateEvent: (eventId, eventData) => apiRequest(`/events/${eventId}/comprehensive`, {
    method: 'PUT',
    body: JSON.stringify(eventData),
  }),


  // Customize event values
  updateEventCustomised: (eventId, eventData) => apiRequest(`/events/${eventId}/customise`, {
    method: 'PUT',
    body: JSON.stringify(eventData),
  }),

  // Customize event values for specific audit
  updateEventCustomizedForAudit: (eventId, auditId, eventData) => apiRequest(`/events/${eventId}/customise/${auditId}`, {
    method: 'PUT',
    body: JSON.stringify(eventData),
  }),


  // Get user-specific and system categories for an audit
  getUserEventCategories: (auditId) => apiRequest(`/events/categories/user/${auditId}`),

  // Create new event category
  createEventCategory: (categoryData) => apiRequest('/events/categories', {
    method: 'POST',
    body: JSON.stringify(categoryData),
  }),

  // Get Distinguishing Factors (returns both user-created and dataset features)
  getUnderlyingFeatures: (auditId) => apiRequest(`/events/features/underlying/${auditId}`),

  // Get Targets (same endpoint returns target_features)
  getTargetFeatures: (auditId) => apiRequest(`/events/features/target`),

  // Get features
  getFeatures: (auditId) => apiRequest(`/events/features/${auditId}`),

  // Create user-defined underlying feature
  createUserFeature: (featureName, auditId) => apiRequest(`/events/features/user`, {
    method: 'POST',
    body: JSON.stringify({
      feature_name: featureName,
      audit_id: parseInt(auditId)
    }),
  }),

  // Create user-defined target feature
  createUserTargetFeature: (featureName, auditId) => apiRequest(`/events/features/user/target`, {
    method: 'POST',
    body: JSON.stringify({
      target_feature: featureName,
      audit_id: parseInt(auditId)
    }),
  }),

  // Get entities (returns user_entities and event_entities)
  getEntities: (auditId) => apiRequest(`/events/entities/user/${auditId}`),

  // Create entity
  createEntity: (name, numIndividuals, auditId) => apiRequest('/events/entities', {
    method: 'POST',
    body: JSON.stringify({
      name: name,
      num_individuals: parseInt(numIndividuals),
      audit_id: parseInt(auditId)
    }),
  }),

  // Get events statistics
  getEventsStatistics: (auditId) => {
    const queryParams = auditId ? `?audit_id=${auditId}` : '';
    return apiRequest(`/events/statistics/summary${queryParams}`);
  },
};

// Metrics API - Based on Metrics, QuantitativeMetrics, QualitativeMetrics, MetricsValues
export const metricsAPI = {
  // Get all metrics for an audit
  getMetrics: (auditId) => apiRequest(`/metrics/by-audit/${auditId}/detailed`),

  // Get metrics simple list
  getMetricsSimple: (skip = 0, limit = 100, params = {}) => {
    const queryParams = new URLSearchParams({
      skip,
      limit,
      ...params
    });
    return apiRequest(`/metrics/?${queryParams}`);
  },

  // Get available metrics for selection
  getAvailableMetrics: () => apiRequest('/metrics/'),

  // Get single metric with full details
  getMetric: (metricId) => apiRequest(`/metrics/${metricId}`),

  // Get metrics by audit
  getMetricsByAudit: (auditId, skip = 0, limit = 100) =>
    apiRequest(`/metrics/by-audit/${auditId}?skip=${skip}&limit=${limit}`),

  // Get metrics by event
  getMetricsByEvent: (eventId, skip = 0, limit = 100) =>
    apiRequest(`/metrics/by-event/${eventId}?skip=${skip}&limit=${limit}`),

  // Get metric value features
  getMetricValueFeatures: (valueId) => apiRequest(`/metrics/values/${valueId}/features`),

  // Get metric value scale points
  getMetricValueScalePoints: (valueId) => apiRequest(`/metrics/values/${valueId}/scale-points`),

  // Create qualitative metric
  createQualitativeMetric: (metricData) => apiRequest('/metrics/qualitative/create', {
    method: 'POST',
    body: JSON.stringify(metricData),
  }),

  updateQualitativeMetric: (metric_id, metricData) => apiRequest(`/metrics/qualitative/${metric_id}`, {
    method: 'PUT',
    body: JSON.stringify(metricData),
  }),

  // Create quantitative metric
  createQuantitativeMetric: (metricData) => apiRequest('/metrics/quantitative/create', {
    method: 'POST',
    body: JSON.stringify(metricData),
  }),

  // Update quantitative metric
  updateQuantitativeMetric: (metric_id, metricData) => apiRequest(`/metrics/quantitative/${metric_id}`, {
    method: 'PUT',
    body: JSON.stringify(metricData),
  }),

  createMetric: (auditId, metricData) => {
    // console.log('Creating metric with type:', metricData.type);
    // console.log('Metric data:', metricData);

    // Route to appropriate creation method based on type
    if (metricData.type === 'qualitative') {
      // console.log('Creating qualitative metric...');
      return metricsAPI.createQualitativeMetric(metricData);
    } else if (metricData.type === 'quantitative') {
      // console.log('Creating quantitative metric...');
      return metricsAPI.createQuantitativeMetric(metricData);
    } else {
      throw new Error(`Unknown metric type: ${metricData.type}. Expected 'qualitative' or 'quantitative'.`);
    }
  },

  // Update existing metric
  updateMetric: (metricData) => {
    // console.log('Updating metric with type:', metricData.type);
    // console.log('Metric data:', metricData);

    // Route to appropriate update method based on type
    if (metricData.type === 'qualitative') {
      // console.log('Updating qualitative metric...');
      return metricsAPI.updateQualitativeMetric(metricData.metricId, metricData);
    } else if (metricData.type === 'quantitative') {
      // console.log('Updating quantitative metric...');
      return metricsAPI.updateQuantitativeMetric(metricData.metricId, metricData);
    } else {
      throw new Error(`Unknown metric type: ${metricData.type}. Expected 'qualitative' or 'quantitative'.`);
    }
  },

  // Update basic metric
  updateMetricBasic: (metricId, metricData) => apiRequest(`/metrics/${metricId}`, {
    method: 'PUT',
    body: JSON.stringify(metricData),
  }),

  // Delete metric
  deleteMetric: (metricId) => apiRequest(`/metrics/${metricId}`, {
    method: 'DELETE',
  }),

  // Update metric threshold (smart)
  updateThreshold: (metricId, thresholdData) => apiRequest(`/metrics/${metricId}/threshold`, {
    method: 'PUT',
    body: JSON.stringify(thresholdData),
  }),

  // Toggle metric for audit use
  toggleMetricForAudit: (auditId, metricId, useInAudit) => apiRequest(`/metrics/${metricId}/audit-status`, {
    method: 'PATCH',
    body: JSON.stringify({
      audit_id: auditId,
      use_in_audit: useInAudit
    }),
  }),

  // Assign metric to an event for a user audit
  assignMetricToEvent: (auditId, eventId, metricId, threshold = "0.5") => apiRequest('/metrics/assign-event', {
    method: 'POST',
    body: JSON.stringify({
      audit_id: parseInt(auditId),
      event_id: parseInt(eventId),
      metric_id: parseInt(metricId),
      threshold: threshold
    }),
  }),
};

// Association API - Based on MappingMetricsEvents and other mapping tables
export const associationAPI = {
  // Batch create audit pipeline mappings
  batchCreateAuditPipelineMappings: (mappings) =>
    apiRequest('/events/audit-pipeline-mapping/batch', {
      method: 'POST',
      body: JSON.stringify(mappings),
    }),

  // Delete audit pipeline mapping by audit_id, event_id, and metric_id
  deletePipelineMappingByIds: (auditId, eventId, metricId) =>
    apiRequest('/events/audit-pipeline-mapping', {
      method: 'DELETE',
      body: JSON.stringify({
        audit_id: parseInt(auditId),
        event_id: parseInt(eventId),
        metric_id: parseInt(metricId)
      }),
    }),
};

// In-flight request dedupe for the evaluation summary: the Performance Analysis page
// mounts two effects that both request the same summary. Sharing one promise while a
// request is pending collapses those into a single network call. Cleared when settled.
const _evaluationSummaryInFlight = new Map();

export const performanceAPI = {
  // Get the summary of evaluations for an audit -this one for the performance analysis.
  getEvaluationSummary: (auditId) => {
    const key = String(auditId);
    if (_evaluationSummaryInFlight.has(key)) {
      return _evaluationSummaryInFlight.get(key);
    }
    const promise = apiRequest(`/evaluation/results/${auditId}/summary`)
      .finally(() => _evaluationSummaryInFlight.delete(key));
    _evaluationSummaryInFlight.set(key, promise);
    return promise;
  },

  // Get outcome evaluation results (output evaluation)
  getOutcomeEvaluationResults: (auditId) =>
    apiRequest(`/evaluation/results/${auditId}/output`),
};

// Evaluation/Status API - Based on evaluation.md
export const evaluationAPI = {
  // Get status summary
  getStatusSummary: (auditId) => apiRequest(`/evaluation/status/${auditId}/summary`),

  // Submit audit with final outcome
  submitAudit: (auditId, submitData) => apiRequest(`/evaluation/status/${auditId}/submit`, {
    method: 'PUT',
    body: JSON.stringify(submitData),
  }),

  // Update individual event-metric status
  updateEventMetricStatus: (auditId, statusData) => apiRequest(`/evaluation/status/${auditId}`, {
    method: 'PUT',
    body: JSON.stringify(statusData),
  }),

  // Batch update event-metric status
  batchUpdateEventMetricStatus: (auditId, statusUpdates) => apiRequest(`/evaluation/status/${auditId}/batch`, {
    method: 'PUT',
    body: JSON.stringify(statusUpdates),
  }),


  getResults: (auditId) => apiRequest(`/evaluation/results/${auditId}/generate/`, {
    method: "POST"
  }),

  getOutputEvaluationResults: (auditId) => apiRequest(`/evaluation/results/${auditId}/generate/output`, {
    method: "POST"
  }),

  getOutputEvaluationSummary: (auditId) => apiRequest(`/evaluation/results/${auditId}/output/summary`, {
    method: "GET"
  }),

  saveOutputEvaluationAnalysis: (auditId, updateBatch) => apiRequest(`/evaluation/outcome/${auditId}/batch`, {
    method: "PUT",
    body: JSON.stringify(updateBatch),
  }),
};

// Audit Outcome API (kept for backwards compatibility)
export const auditOutcomeAPI = {
  // Get audit outcome
  getAuditOutcomeSummary: (auditId) => apiRequest(`/evaluation/status/${auditId}/summary`),

  // Update audit outcome
  updateAuditOutcome: (auditId, outcomeData) => apiRequest(`/evaluation/status/${auditId}/batch`, {
    method: 'PUT',
    body: JSON.stringify(outcomeData),
  }),

  // Finalize audit
  finaliseAudit: (auditId, submitData = {}) => apiRequest(`/evaluation/status/${auditId}/submit`, {
    method: 'PUT',
    body: JSON.stringify(submitData),
  }),
};

// User/Authentication API - Based on User table
export const authAPI = {
  // Login - Should use form data, not JSON
  login: (credentials) => {
    const formData = new FormData();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);

    return fetch(`${API_BASE_URL}/login/access-token`, {
      method: 'POST',
      headers: {
        // Don't set Content-Type, let browser set it for the FormData
      },
      body: formData,
    }).then(response => response.json());
  },

  logout: () => apiRequest('/logout', {
    method: 'POST',
  }),

  // Signup
  signup: (userData) => apiRequest('/users/signup', {
    method: 'POST',
    body: JSON.stringify(userData),
  }),

  // Password recovery - does not require authentication
  passwordRecovery: (email) => {
    const tenantId = _resolveTenantId();
    return fetch(`${API_BASE_URL}/users/forgot-password`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-tenant-id' : tenantId,
      },
      body: JSON.stringify({ "email": email }),
    }).then(response => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return response.json();
    });
  },

  // Reset password - does not require authentication
  resetPassword: (resetData) => {
    const tenantId = _resolveTenantId();
    return fetch(`${API_BASE_URL}/users/reset-password`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-tenant-id' : tenantId,
      },
      body: JSON.stringify(resetData),
    }).then(response => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return response.json();
    });
  },

  // Get current user
  getCurrentUser: () => apiRequest('/users/me'),

  // Update current user profile
  updateUserProfile: (profileData) => apiRequest('/users/me', {
    method: 'PATCH',
    body: JSON.stringify(profileData),
  }),

  // Update password
  updatePassword: (oldPassword, newPassword) => apiRequest('/users/me/password', {
    method: 'PATCH',
    body: JSON.stringify({
      current_password: oldPassword,
      new_password: newPassword
    }),
  }),

  // Refresh token
  refreshToken: () => apiRequest('/auth/refresh', {
    method: 'POST',
  }),

  // Verify email
  verifyEmail: (token) => apiRequest(`/users/verify-email?token=${token}`, {
    method: 'POST',
  }),

  // Resend verification email
  resendVerificationEmail: (email) => apiRequest('/users/resend-verification', {
    method: 'POST',
    body: JSON.stringify({ email }),
  }),

  // Accept invitation
  validateInvite: (token) => apiRequest('/users/accept-invite', {
    method: 'POST',
    body: JSON.stringify({ token }),
  }),

  // Set password with invitation token
  setPasswordWithInvite: (token, password) => apiRequest('/users/set-password-with-invite', {
    method: 'POST',
    body: JSON.stringify({ token, password }),
  }),
};

// Upload/File API - Based on storage.md
export const uploadAPI = {
  // Upload single dataset
  uploadSingleDataset: (auditId, file) => {
    const formData = new FormData();
    formData.append('file', file);

    return apiRequest(`/upload/dataset/${auditId}/single`, {
      method: 'POST',
      isFileUpload: true,
      body: formData,
    });
  },

  // Upload multiple datasets
  uploadMultipleDatasets: (auditId, files) => {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));

    return apiRequest(`/upload/dataset/${auditId}/multiple`, {
      method: 'POST',
      isFileUpload: true,
      body: formData,
    });
  },

  // List uploaded datasets
  listUploadedDatasets: (auditId) => apiRequest(`/upload/dataset/${auditId}`),

  // Delete uploaded dataset
  deleteUploadedDataset: (auditId, data) => apiRequest(`/upload/dataset/${auditId}`, {
    method: 'DELETE',
    body: JSON.stringify(data),
  }),

  // Upload audit input files (supports single or multiple files including metadata.csv)
  uploadAuditInput: (auditId, files) => {
    const formData = new FormData();
    const fileList = files instanceof FileList ? Array.from(files) : (Array.isArray(files) ? files : [files]);
    fileList.forEach(file => formData.append('files', file));

    return apiRequest(`/upload/audit/${auditId}/input`, {
      method: 'POST',
      isFileUpload: true,
      body: formData,
    });
  },

  // List all audit input files
  listAuditFiles: (auditId) => apiRequest(`/upload/audit/${auditId}/files`),

  // View/Download uploaded file
  viewFile: (auditId, filename) => {
    const token = TokenStorage.getToken();
    const url = `${API_BASE_URL}/upload/audit/${auditId}/view/${filename}`;

    return fetch(url, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
  },
};

// Admin Panel API - For audit instigators to set up audits
export const adminAPI = {
  // Step 1: Create Application
  createApplication: (data) => apiRequest('/audits/applications/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // Step 2: Create Model Metadata
  createModelMetadata: (data) => apiRequest('/pipeline/model-metadata/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // Step 2 (Option B): Scaffold a new MCP model service
  scaffoldModel: (data) => apiRequest('/pipeline/model/scaffold/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // Step 3: Create API Key for Model
  createApiKey: (data) => apiRequest('/pipeline/api-keys/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // Step 4: Create Dataset Metadata
  createDatasetMetadata: (data) => apiRequest('/pipeline/dataset/metadata/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // Step 5: Create Audit
  createAudit: (data) => apiRequest('/audits/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // Step 6: Create Event
  createEvent: (data) => apiRequest('/events/comprehensive', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // Step 7: Create Metrics
  createQuantitativeMetric: (data) => apiRequest('/metrics/quantitative/create', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  createQualitativeMetric: (data) => apiRequest('/metrics/qualitative/create', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // Step 8: Map Events to Pipeline
  batchCreatePipelineMappings: (data) => apiRequest('/events/audit-pipeline-mapping/batch', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // Step 9: Invite Auditor by email (backend handles lookup + role assignment + invitation email)
  inviteAuditor: (auditId, email) => apiRequest(`/audits/${auditId}/invite`, {
    method: 'POST',
    body: JSON.stringify({ email }),
  }),

  // Aggregated auditor results for an audit (per-auditor criteria + recommendations)
  getAuditResults: (auditId) => apiRequest(`/admin/audit-results/${auditId}`),

  // Audit timing
  recordSessionChunk: (auditId, durationSeconds) => apiRequest(`/audits/${auditId}/session`, {
    method: 'POST',
    body: JSON.stringify({ duration_seconds: durationSeconds }),
  }),
  submitAuditTiming: (auditId) => apiRequest(`/audits/${auditId}/submit`, { method: 'POST' }),
  getAuditTiming: (auditId) => apiRequest(`/audits/${auditId}/timing`),

  // Tenant-wide underlying features catalogue
  listTenantUnderlyingFeatures: () => apiRequest('/admin/underlying-features/'),
  createTenantUnderlyingFeature: (featureName) => apiRequest('/admin/underlying-features/', {
    method: 'POST',
    body: JSON.stringify({ feature_name: featureName }),
  }),
  updateTenantUnderlyingFeature: (id, featureName) => apiRequest(`/admin/underlying-features/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ feature_name: featureName }),
  }),
  deleteTenantUnderlyingFeature: (id) => apiRequest(`/admin/underlying-features/${id}`, { method: 'DELETE' }),

  // Tenant-wide target features catalogue
  listTenantTargetFeatures: () => apiRequest('/admin/target-features/'),
  createTenantTargetFeature: (targetFeature, functionName) => apiRequest('/admin/target-features/', {
    method: 'POST',
    body: JSON.stringify(functionName ? { target_feature: targetFeature, function_name: functionName } : { target_feature: targetFeature }),
  }),
  updateTenantTargetFeature: (id, body) => apiRequest(`/admin/target-features/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  }),
  deleteTenantTargetFeature: (id) => apiRequest(`/admin/target-features/${id}`, { method: 'DELETE' }),

  // Read helpers
  getAudits: () => apiRequest('/audits/'),
  getAudit: (auditId) => apiRequest(`/audits/${auditId}`),
  getAuditComplete: (auditId) => apiRequest(`/audits/${auditId}/complete`),
  getModels: () => apiRequest('/pipeline/model/'),
  getMcpStatus: (modelId) => apiRequest(`/pipeline/model/${modelId}/mcp-status/`),
  getDatasets: () => apiRequest('/pipeline/dataset/').catch(() => []),
  getDataset: (datasetId) => apiRequest(`/pipeline/dataset/metadata/${datasetId}`),
  getDatasetColumns: (datasetId) => apiRequest(`/pipeline/dataset/columns/${datasetId}`),
  getAvailableMetrics: () => apiRequest('/pipeline/available-metrics/'),
  getEventsByAudit: (auditId) => apiRequest(`/events/audit/${auditId}`),
  getMetricsByAudit: (auditId) => apiRequest(`/metrics/?audit_id=${auditId}`),
  getMetricsByAuditDetailed: (auditId) => apiRequest(`/metrics/by-audit/${auditId}/detailed`),
  getEntitiesByAudit: (auditId) => apiRequest(`/entities/by-audit/${auditId}`),
  getPipelineMappings: (pipelineId) => apiRequest(`/events/audit-pipeline-mapping/${pipelineId}`),
  // Step 5b: pipeline wiring
  getAuditPipeline: (auditId) => apiRequest(`/audits/${auditId}/pipeline`),
  addPipelinePair: (auditId, data) => apiRequest(`/audits/${auditId}/pipeline/model-dataset`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  removePipelinePair: (auditId, mappingId) => apiRequest(`/audits/${auditId}/pipeline/model-dataset/${mappingId}`, {
    method: 'DELETE',
  }),
  getCategories: () => apiRequest('/events/categories'),
  getEntities: (auditId) => apiRequest(`/events/entities/user/${auditId}`),
  getUnderlyingFeatures: (auditId) => apiRequest(`/events/features/underlying/${auditId}`),
  getTargetFeatures: () => apiRequest('/events/features/target'),
  getEvaluationResults: (auditId) => apiRequest(`/evaluation/results/${auditId}/summary`),

  // Import dataset (superuser only)
  importDataset: (data) => apiRequest('/pipeline/dataset/import/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // Update operations
  updateAudit: (auditId, data) => apiRequest(`/audits/${auditId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  updateApplication: (applicationId, data) => apiRequest(`/audits/applications/${applicationId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  updateEvent: (eventId, data) => apiRequest(`/events/${eventId}/comprehensive`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  updateMetric: (metricId, data) => apiRequest(`/metrics/${metricId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  updateQuantitativeMetric: (metricId, data) => apiRequest(`/metrics/quantitative/${metricId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  updateQualitativeMetric: (metricId, data) => apiRequest(`/metrics/qualitative/${metricId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  updateMetricThreshold: (metricId, data) => apiRequest(`/metrics/${metricId}/threshold`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  updateModel: (modelId, data) => apiRequest(`/pipeline/model/${modelId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  updateDataset: (datasetId, data) => apiRequest(`/pipeline/dataset/metadata/${datasetId}/all`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  updateApiKey: (apiKeyId, data) => apiRequest(`/pipeline/api-keys/${apiKeyId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),

  // Delete operations
  deleteAudit: (auditId) => apiRequest(`/audits/${auditId}`, {
    method: 'DELETE',
  }),
  deleteApplication: (applicationId) => apiRequest(`/audits/applications/${applicationId}`, {
    method: 'DELETE',
  }),
  deleteEvent: (eventId) => apiRequest(`/events/${eventId}`, {
    method: 'DELETE',
  }),
  deleteEventsBatch: (eventIds) => apiRequest('/events/batch/delete', {
    method: 'POST',
    body: JSON.stringify({ event_ids: eventIds }),
  }),
  deleteMetric: (metricId) => apiRequest(`/metrics/${metricId}`, {
    method: 'DELETE',
  }),
  deleteModel: (modelId) => apiRequest(`/pipeline/model/${modelId}`, {
    method: 'DELETE',
  }),
  deleteDataset: (datasetId) => apiRequest(`/pipeline/dataset/metadata/${datasetId}`, {
    method: 'DELETE',
  }),
  deleteApiKey: (apiKeyId) => apiRequest(`/pipeline/api-keys/${apiKeyId}`, {
    method: 'DELETE',
  }),
  deletePipelineMapping: (mappingId) => apiRequest(`/events/audit-pipeline-mapping/${mappingId}`, {
    method: 'DELETE',
  }),
  deleteUnderlyingFeature: (featureId, auditId) => apiRequest(`/events/features/user/${featureId}?audit_id=${auditId}`, {
    method: 'DELETE',
  }),
  deleteTargetFeature: (targetFeatureId, auditId) => apiRequest(`/events/features/user/target/${targetFeatureId}?audit_id=${auditId}`, {
    method: 'DELETE',
  }),

  // Mapping delete operations
  removeUserFromAudit: (userId, auditId) => apiRequest(`/mappings/user-audit/?user_id=${userId}&audit_id=${auditId}`, {
    method: 'DELETE',
  }),
  removeUserEvent: (userAuditId, eventId) => apiRequest(`/mappings/user-event/?user_audit_id=${userAuditId}&event_id=${eventId}`, {
    method: 'DELETE',
  }),
  removeEventEntity: (eventId, entityId) => apiRequest(`/mappings/event-entity/?event_id=${eventId}&entity_id=${entityId}`, {
    method: 'DELETE',
  }),
  removeMetricEvent: (metricId, eventId) => apiRequest(`/mappings/metric-event/?metric_id=${metricId}&event_id=${eventId}`, {
    method: 'DELETE',
  }),
  removeEventCategory: (eventId, categoryId) => apiRequest(`/mappings/event-category/?event_id=${eventId}&category_id=${categoryId}`, {
    method: 'DELETE',
  }),
  removeEventAuditStatus: (eventId, auditId) => apiRequest(`/mappings/event-audit-status/?event_id=${eventId}&audit_id=${auditId}`, {
    method: 'DELETE',
  }),
  removeAuditModel: (modelId, auditId) => apiRequest(`/mappings/audit-model/?model_id=${modelId}&audit_id=${auditId}`, {
    method: 'DELETE',
  }),
  removeAuditApplication: (auditId, applicationId) => apiRequest(`/mappings/audit-application/?audit_id=${auditId}&application_id=${applicationId}`, {
    method: 'DELETE',
  }),

  // Create helpers for features, entities, categories
  createUserFeature: (featureName, auditId) => apiRequest('/events/features/user', {
    method: 'POST',
    body: JSON.stringify({ feature_name: featureName, audit_id: parseInt(auditId) }),
  }),
  createUserTargetFeature: (targetFeature, auditId) => apiRequest('/events/features/user/target', {
    method: 'POST',
    body: JSON.stringify({ target_feature: targetFeature, audit_id: parseInt(auditId) }),
  }),
  createEntity: (name, numIndividuals, auditId) => apiRequest('/events/entities', {
    method: 'POST',
    body: JSON.stringify({ name, num_individuals: parseInt(numIndividuals), audit_id: parseInt(auditId) }),
  }),
  createCategory: (eventName, auditId) => apiRequest('/events/categories', {
    method: 'POST',
    body: JSON.stringify({ event_name: eventName, audit_id: parseInt(auditId) }),
  }),

  // --- Instigator setup edits (admin panel) ---
  // Partial in-place edits of shared rows scoped to an audit. Each returns the
  // updated row plus `also_used_by_audits` (other audits referencing the same row).

  // Edit an event linked to this audit
  adminEditEvent: (auditId, eventId, data) => apiRequest(`/admin/audits/${auditId}/events/${eventId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  }),
  // Edit a metric linked to this audit (formula for quantitative, definition for qualitative)
  adminEditMetric: (auditId, metricId, data) => apiRequest(`/admin/audits/${auditId}/metrics/${metricId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  }),
  // Edit an entity linked to this audit
  adminEditEntity: (auditId, entityId, data) => apiRequest(`/admin/audits/${auditId}/entities/${entityId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  }),

  // Event categories catalogue (superuser / tenant admin / any instigator)
  listEventCategories: () => apiRequest('/admin/event-categories/'),
  editEventCategory: (categoryId, data) => apiRequest(`/admin/event-categories/${categoryId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  }),

  // Taxonomy groups catalogue (superuser / tenant admin / any instigator)
  listTaxonomyGroups: () => apiRequest('/admin/taxonomy-groups/'),
  editTaxonomyGroup: (taxonomyId, data) => apiRequest(`/admin/taxonomy-groups/${taxonomyId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  }),

  // Reactivate a submitted audit — reopens the edit window (instigator / tenant admin).
  // Pass userAuditId to reopen a single auditor's submission; omit for all.
  reactivateAudit: (auditId, userAuditId = null) =>
    apiRequest(
      `/admin/audits/${auditId}/reactivate${userAuditId != null ? `?user_audit_id=${userAuditId}` : ''}`,
      { method: 'POST' }
    ),
};

// Error handling helper
export const handleApiError = (error, defaultMessage = 'An error occurred') => {
  if (error.response) {
    // Server responded with error status
    return error.response.data?.message || defaultMessage;
  } else if (error.request) {
    // Request was made but no response received
    return 'Network error - please check your connection';
  } else {
    // Something else happened
    return error.message || defaultMessage;
  }
};

// API status checker
export const healthCheck = () => apiRequest('/health');

// Constants based on schema
export const AUDIT_STATUS = {
  0: 'Not Started',
  1: 'In Progress',
  2: 'Finished'
};

export const AUDIT_RECOMMENDATION = {
  0: 'Not Evaluated',
  1: 'Inconclusive',
  2: 'Fail',
  3: 'Pass'
};

export const MODEL_TYPES = {
  0: 'Predictive AI',
  1: 'Generative AI'
};

export const ACCESS_TYPES = {
  0: 'Opaque',
  1: 'Translucent',
  2: 'Transparent'
};

export const EVALUATION_STATUS = {
  0: 'Not Evaluated',
  1: 'Evaluated'
};

// Helper function to translate access type code to string
export const getAccessTypeLabel = (accessTypeCode) => {
  return ACCESS_TYPES[accessTypeCode] || 'Unknown';
};

export const demoAPI = {
  resetDemo: () => apiRequest('/demo/reset', { method: 'POST' }),
};

// Export TokenStorage for use in AuthContext
export { TokenStorage };

export default {
  dashboardAPI,
  aiApplicationAPI,
  eventsAPI,
  metricsAPI,
  associationAPI,
  evaluationAPI,
  auditOutcomeAPI,
  authAPI,
  uploadAPI,
  adminAPI,
  handleApiError,
  healthCheck,
  AUDIT_STATUS,
  AUDIT_RECOMMENDATION,
  MODEL_TYPES,
  ACCESS_TYPES,
  EVALUATION_STATUS,
  getAccessTypeLabel,
};
