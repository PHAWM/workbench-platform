const API_BASE_URL = import.meta.env.VITE_API_URL;

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
  }
};

// Generic API request handler
const apiRequest = async (endpoint, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  const token = TokenStorage.getToken();

  // Build headers
  const headers = {};

  // Always add Authorization if token exists
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
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
        window.location.href = '/403';
        throw new Error('Access forbidden. Redirecting to login...');
      }

      if (response.status === 401) {
        console.error('401 Unauthorized: Token expired or invalid');
        // Clear any stored authentication data
        TokenStorage.clearToken();

        // Redirect to login page
        window.location.href = '/login';
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
  getUnderlyingFeatures: (auditId) => apiRequest(`/events/features/user/${auditId}`),

  // Get Targets (same endpoint returns target_features)
  getTargetFeatures: (auditId) => apiRequest(`/events/features/target`),

  // Get features
  getFeatures: (auditId) => apiRequest(`/events/features/${auditId}`),

  // Create user-defined underlying feature
  createUserFeature: (featureName, auditId) => apiRequest(`/events/features/user/`, {
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
      name: featureName,
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

export const performanceAPI = {
  // Get the summary of evaluations for an audit -this one for the performance analysis.
  getEvaluationSummary: (auditId) =>
    apiRequest(`/evaluation/results/${auditId}/summary`),

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
        // Don't set Content-Type, let browser set it for FormData
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
    return fetch(`${API_BASE_URL}/users/forgot-password/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
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
    return fetch(`${API_BASE_URL}/users/reset-password/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
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
  deleteUploadedDataset: (auditId, data) => {apiRequest(`/upload/dataset/${auditId}`, {
      method: 'DELETE',
      body: JSON.stringify(data),
    })
  },

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
  0: 'Black Box',
  1: 'Grey Box',
  2: 'White Box'
};

export const EVALUATION_STATUS = {
  0: 'Not Evaluated',
  1: 'Evaluated'
};

// Helper function to translate access type code to string
export const getAccessTypeLabel = (accessTypeCode) => {
  return ACCESS_TYPES[accessTypeCode] || 'Unknown';
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
  handleApiError,
  healthCheck,
  AUDIT_STATUS,
  AUDIT_RECOMMENDATION,
  MODEL_TYPES,
  ACCESS_TYPES,
  EVALUATION_STATUS,
  getAccessTypeLabel,
};