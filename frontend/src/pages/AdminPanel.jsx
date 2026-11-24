import { useState, useEffect } from 'react';
import { Navigation } from '../components/navigation/Navigation';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../components/auth/AuthContext';
import { tenantPath } from '../utils/tenant';
import { Settings, ChevronRight, ChevronLeft, Check, Plus, Trash2, AlertCircle, Download, FileText, ChevronDown, ChevronUp, Upload, X } from 'lucide-react';
import { adminAPI, uploadAPI, eventsAPI, metricsAPI } from '../api/apiService';
import {
  handleCreateApplication,
  buildApplicationPayload,
  handleCreateModel,
  handleScaffoldModel,
  handleCreateApiKey,
  handleCreateDataset,
  handleImportDataset,
  handleCreateAudit,
  handleCreateEvent,
  handleCreateMetric,
  handleMapEventsToPipeline,
  handleInviteAuditor,
} from '../handlers/adminPanelHandlers';
import ProgressNav from '../components/admin/ProgressNav';
import AuditInfoPage from '../components/admin/pages/AuditInfoPage';
import ApplicationPage from '../components/admin/pages/ApplicationPage';

const STEPS = [
  { id: 1, title: 'Audit', description: 'Name your audit' },
  { id: 2, title: 'Application', description: 'Create the AI application' },
  { id: 3, title: 'Model', description: 'Define model metadata' },
  { id: 4, title: 'API Key', description: 'Create API key for the model' },
  { id: 5, title: 'Dataset', description: 'Create or import dataset' },
  { id: '5b', title: 'Factors', description: 'Select distinguishing factors' },
  { id: '5c', title: 'Metrics', description: 'Select target metrics' },
  { id: '5d', title: 'Upload', description: 'Upload dataset files' },
  { id: '5e', title: 'Pipeline', description: 'Confirm model-dataset wiring' },
  { id: 6, title: 'Entities', description: 'Define entities for events' },
  { id: 7, title: 'Events', description: 'Define audit criteria events' },
  { id: 8, title: 'Metrics', description: 'Create metrics for events' },
  { id: 9, title: 'Pipeline', description: 'Map events and metrics to pipeline' },
  { id: 10, title: 'Invite', description: 'Add auditors to the audit' },
];

const AdminPanel = () => {
  const navigate = useNavigate();
  const { auditId: routeAuditId } = useParams();
  const isEdit = !!routeAuditId; // /admin/edit/:auditId → edit an existing audit
  useAuth();
  const [currentStep, setCurrentStep] = useState(1);
  const [editLoading, setEditLoading] = useState(!!routeAuditId);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Categories loaded from API
  const [categories, setCategories] = useState([]);

  // Step 4b/4c data
  const [datasetColumns, setDatasetColumns] = useState(null);
  const [selectedUnderlyingFeatures, setSelectedUnderlyingFeatures] = useState([]);
  const [availableMetrics, setAvailableMetrics] = useState(null);
  const [selectedTargetFeatures, setSelectedTargetFeatures] = useState([]);
  const [expandedCategories, setExpandedCategories] = useState({});

  // Step 4d: file upload state
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [isUploading, setIsUploading] = useState(false);

  // Step 5e: pipeline wiring state
  const [pipelineOverview, setPipelineOverview] = useState(null);
  const [pipelineLoading, setPipelineLoading] = useState(false);

  // Step 8: feature data for metric creation
  const [underlyingFeatures, setUnderlyingFeatures] = useState([]);
  const [targetFeatures, setTargetFeatures] = useState([]);

  // Step 3: existing model picker
  const [existingModels, setExistingModels] = useState([]);
  const [existingModelsLoading, setExistingModelsLoading] = useState(false);

  // Step 5b (Black Box): tenant-wide underlying feature catalogue
  const [tenantUnderlyingFeatures, setTenantUnderlyingFeatures] = useState([]);
  const [newUnderlyingFeatureName, setNewUnderlyingFeatureName] = useState('');

  // Step 5c: custom target metric input (freeform — no registry entry needed)
  const [newTargetFeatureName, setNewTargetFeatureName] = useState('');
  const [customTargetFeatures, setCustomTargetFeatures] = useState([]);

  useEffect(() => {
    adminAPI.getCategories()
      .then(data => {
        const list = Array.isArray(data) ? data : data.categories || [];
        setCategories(list);
      })
      .catch(() => {});
  }, []);

  // Pre-load existing models when entering the model step
  useEffect(() => {
    if (currentStep === 3) loadExistingModels();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStep]);

  // Wizard state - stores IDs from created resources
  const [wizardData, setWizardData] = useState({
    applicationId: null,
    modelId: null,
    apiKeyId: null,
    datasetId: null,
    auditId: null,
    auditPipelineId: null,
    createdEntities: [],
    createdEvents: [],
    createdMetrics: [],
    pipelineMappings: [],
    invitedAuditors: [],
  });

  // Form states for each step
  const [applicationForm, setApplicationForm] = useState({
    name: '', description: '', organisation: '', url: '',
    access_type: '0', business_case: '', legal_framework: '',
    te_model_details: '', te_dataset_details: '', te_testing_details: '', te_audit_instigator_details: '',
    deploy_version: '', deploy_environment: '',
  });

  const [modelForm, setModelForm] = useState({
    name: '', model_type: '0', task: '',
    location: '', mcp_tool_name: '', acceptable_formats: '', output_context: '',
    with_api_key: false,
  });

  const [apiKeyForm, setApiKeyForm] = useState({
    model_api_key: '', costing_policy: 'pay-per-request',
    use_api_key: true,
  });

  // Model mode: 'pick' (select existing) | 'register' (new MCP) | 'scaffold' (generate files)
  const [modelMode, setModelMode] = useState('pick');

  const [scaffoldForm, setScaffoldForm] = useState({
    service_name: '', tool_name: '', port: '8010',
    description: '', model_type: '0', task: 'classification',
    acceptable_formats: '', needs_s3: false,
  });

  // Dataset mode: 'manual' (Option A) or 'import' (Option B)
  const [datasetMode, setDatasetMode] = useState('manual');

  const [datasetForm, setDatasetForm] = useState({
    purpose: '',
    copyright_agreement: false,
    input_columns: [{ name: '', type: '', range: '' }],
    input_benchmark: false, input_location: '',
    output_columns: [{ name: '', type: '', range: '' }],
    output_benchmark: false, output_location: '',
    target_features: '',
  });

  const [importForm, setImportForm] = useState({
    source_type: 'huggingface',
    dataset_name: '',
    split: 'test',
    subset: '',
    max_samples: '',
    purpose: '',
    label_column: '',
    text_column: '',
  });

  const [auditForm, setAuditForm] = useState({
    name: '', description: '',
  });

  const [entityForm, setEntityForm] = useState({
    name: '', num_individuals: '',
  });

  const [eventForm, setEventForm] = useState({
    name: '', description: '', cause: '', reason: '',
    likelihood: '0', magnitude: '0', valence: '0',
    category_ids: [], entity_ids: [],
  });

  const [metricForm, setMetricForm] = useState({
    type: 'quantitative', name: '', description: '', reason: '',
    event_ids: [], threshold: '', formula: '',
    definition: '', scale_points_text: '',
    target_feature_id: '', underlying_feature_ids: [],
    // Optional comma-separated ranges per feature id, e.g. { 10: "0-100, 200-300" }
    feature_ranges: {},
  });

  // Expand/collapse state for the metric form's event cards, keyed by event id
  const [expandedMetricEvents, setExpandedMetricEvents] = useState({});

  // Toggle an event id in the metric form's multi-select event list (ids stored as strings)
  const toggleMetricEventId = (id) => {
    const strId = String(id);
    setMetricForm(p => ({
      ...p,
      event_ids: p.event_ids.includes(strId)
        ? p.event_ids.filter(e => e !== strId)
        : [...p.event_ids, strId],
    }));
  };

  const toggleMetricEventExpand = (id) => {
    setExpandedMetricEvents(p => ({ ...p, [id]: !p[id] }));
  };

  // Edit mode: which existing metric is loaded into the form for editing (null = creating new)
  const [editingMetricId, setEditingMetricId] = useState(null);
  // metricId -> [event_ids] derived from the events' associated_metrics during pre-load
  const [metricEventMap, setMetricEventMap] = useState({});

  // Load a full existing metric into metricForm for editing.
  const startEditMetric = async (metricId) => {
    setError('');
    try {
      const m = await metricsAPI.getMetric(metricId);
      const type = (m.metric_type || m.type || '').toLowerCase() === 'qualitative' ? 'qualitative' : 'quantitative';
      // Metric values may carry threshold / scale_points / features
      const mv = (m.metric_values && m.metric_values[0]) || {};
      const targetFeat = (mv.target_features && mv.target_features[0]) || {};
      const scalePoints = mv.scale_points || m.scale_points || null;
      setMetricForm({
        type,
        name: m.name || m.metric_name || '',
        description: m.description || m.metric_description || '',
        reason: m.reason || '',
        event_ids: (() => {
          const fromMetric = (m.event_mappings || m.events || []).map(e => String(e.event_id ?? e.id)).filter(Boolean);
          return fromMetric.length ? fromMetric : (metricEventMap[metricId] || []);
        })(),
        threshold: mv.threshold ?? m.threshold ?? '',
        formula: m.formula || '',
        definition: m.definition || '',
        scale_points_text: scalePoints ? JSON.stringify(scalePoints) : '',
        target_feature_id: targetFeat.feature_id ? String(targetFeat.feature_id) : '',
        underlying_feature_ids: (mv.underlying_features || []).map(f => String(f.feature_id)),
        feature_ranges: (mv.underlying_features || []).reduce((acc, f) => {
          if (f.ranges && f.ranges.length) acc[f.feature_id] = f.ranges.join(', ');
          return acc;
        }, {}),
      });
      setEditingMetricId(metricId);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load metric for editing');
    }
  };

  const cancelEditMetric = () => {
    setEditingMetricId(null);
    setMetricForm({
      type: 'quantitative', name: '', description: '', reason: '',
      event_ids: [], threshold: '', formula: '',
      definition: '', scale_points_text: '',
      target_feature_id: '', underlying_feature_ids: [], feature_ranges: {},
    });
  };

  // Edit mode: existing event / entity being edited
  const [editingEventId, setEditingEventId] = useState(null);
  const [editingEntityId, setEditingEntityId] = useState(null);

  const startEditEvent = (evt) => {
    setError('');
    setEventForm({
      name: evt.name || '', description: evt.description || '',
      cause: evt.cause || '', reason: evt.reason || '',
      likelihood: evt.likelihood ?? '0', magnitude: evt.magnitude ?? '0', valence: evt.valence ?? '0',
      // Pre-select the event's linked categories and entities
      category_ids: evt.category_ids || [],
      entity_ids: evt.entity_ids || [],
    });
    setEditingEventId(evt.id);
  };
  const cancelEditEvent = () => {
    setEditingEventId(null);
    setEventForm({ name: '', description: '', cause: '', reason: '', likelihood: '0', magnitude: '0', valence: '0', category_ids: [], entity_ids: [] });
  };

  const startEditEntity = (en) => {
    setError('');
    setEntityForm({ name: en.name || '', num_individuals: en.num_individuals ?? '' });
    setEditingEntityId(en.id);
  };
  const cancelEditEntity = () => {
    setEditingEntityId(null);
    setEntityForm({ name: '', num_individuals: '' });
  };

  const [pipelineMappingForm, setPipelineMappingForm] = useState({
    event_id: '', metric_id: '',
  });

  const [auditorForm, setAuditorForm] = useState({ email: '' });

  // --- Edit mode: pre-load an existing audit's data into the wizard forms ---
  useEffect(() => {
    if (!routeAuditId) return;
    let cancelled = false;
    (async () => {
      setEditLoading(true);
      setError('');
      try {
        const aId = parseInt(routeAuditId);
        const [auditRes, eventsRes, metricsRes, entitiesRes] = await Promise.allSettled([
          adminAPI.getAudit(aId),
          eventsAPI.getEvents(aId),
          adminAPI.getMetricsByAuditDetailed(aId),
          adminAPI.getEntities(aId),
        ]);
        if (cancelled) return;

        // Audit core + ids
        const audit = auditRes.status === 'fulfilled' ? auditRes.value : {};
        setAuditForm({ name: audit.name || '', description: audit.description || '' });
        setWizardData(prev => ({
          ...prev,
          auditId: aId,
          applicationId: audit.application_id ?? prev.applicationId,
          modelId: (audit.model_association_ids || [])[0] ?? prev.modelId,
        }));

        // Application form — the audit response (/audits/{id}) already carries the full
        // application details (same endpoint AIApplicationOverview reads).
        setApplicationForm(prev => ({
          ...prev,
          name: audit.application_name || audit.name || '',
          description: audit.application_description || '',
          organisation: audit.application_organisation || '',
          url: audit.application_url || '',
          access_type: String(audit.access_type ?? '0'),
          business_case: audit.business_case || '',
          legal_framework: audit.legal_framework || '',
          te_model_details: audit.testing_evaluation?.model_details || '',
          te_dataset_details: audit.testing_evaluation?.dataset_details || '',
          te_testing_details: audit.testing_evaluation?.testing_details || '',
          te_audit_instigator_details: audit.testing_evaluation?.audit_instigator_details || '',
          deploy_version: audit.deployment?.version || '',
          deploy_environment: audit.deployment?.environment || '',
        }));

        // Events
        const rawEvents = eventsRes.status === 'fulfilled'
          ? (eventsRes.value?.events || eventsRes.value || []) : [];
        // Metrics (detailed)
        const rawMetrics = metricsRes.status === 'fulfilled'
          ? (metricsRes.value?.metrics || metricsRes.value || []) : [];
        // Entities (user + event)
        const enVal = entitiesRes.status === 'fulfilled' ? entitiesRes.value : null;
        const rawEntities = enVal?.entities
          ? [...(enVal.entities.user_entities || []), ...(enVal.entities.event_entities || [])]
          : (enVal?.entities || enVal || []);

        setWizardData(prev => ({
          ...prev,
          createdEvents: (Array.isArray(rawEvents) ? rawEvents : []).map(ev => ({
            id: ev.id, name: ev.name, description: ev.description,
            cause: ev.cause, reason: ev.reason,
            likelihood: ev.likelihood, magnitude: ev.magnitude, valence: ev.valence,
            // Linked category/entity ids (as strings) so editing pre-checks them
            category_ids: (ev.event_categories || ev.categories || []).map(c => String(c.id ?? c.category_id)).filter(Boolean),
            entity_ids: (ev.associated_entities || ev.entities || []).map(e => (e.id ?? e.entity_id)).filter(v => v != null),
          })),
          createdMetrics: (Array.isArray(rawMetrics) ? rawMetrics : []).map(m => ({
            id: m.id ?? m.metric_id, name: m.name || m.metric_name,
            description: m.description || m.metric_description,
            metric_type: m.metric_type || m.type,
          })),
          createdEntities: (Array.isArray(rawEntities) ? rawEntities : []).map(en => ({
            id: en.id ?? en.entity_id, name: en.name || en.entity_name,
            num_individuals: en.num_individuals,
          })),
        }));

        // Build metricId -> [event_ids] from the events' associated_metrics, so editing a
        // metric can pre-check the events it's linked to.
        const mMap = {};
        (Array.isArray(rawEvents) ? rawEvents : []).forEach(ev => {
          (ev.associated_metrics || ev.metrics || []).forEach(m => {
            const mid = m.metric_id ?? m.id;
            if (mid == null) return;
            (mMap[mid] = mMap[mid] || []).push(String(ev.id));
          });
        });
        setMetricEventMap(mMap);

        // Try to resolve the pipeline id for the map-events step
        try {
          const pipeline = await adminAPI.getAuditPipeline(aId);
          if (!cancelled) setWizardData(prev => ({ ...prev, auditPipelineId: pipeline?.pipeline_id ?? prev.auditPipelineId }));
        } catch (e) { /* pipeline optional */ }
      } catch (err) {
        if (!cancelled) setError(err?.response?.data?.detail || err?.message || 'Failed to load audit for editing');
      } finally {
        if (!cancelled) setEditLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [routeAuditId]);

  const showSuccess = (msg) => {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(''), 3000);
  };

  // Black box models have no dataset — skip dataset/upload steps but still pick underlying + target features
  const isBlackBox = applicationForm.access_type === '0';
  const nextAfterModel = isBlackBox ? '5b' : 5;

  const handleNavigation = (pageId) => {
    if (pageId === 'dashboard') navigate(tenantPath('/dashboard'));
    if (pageId === 'admin') navigate(tenantPath('/admin'));
    if (pageId === 'profile') navigate(tenantPath('/profile'));
  };

  // Step 1: Collect Audit info (no API call — audit is created after dataset)
  const submitAuditInfo = () => {
    if (!auditForm.name || !auditForm.description) {
      setError('Please fill in name and description');
      return;
    }
    setError('');
    showSuccess('Audit info saved. Now set up the application.');
    setCurrentStep(2);
  };

  // Step 2: Create Application
  const submitApplication = async () => {
    if (!applicationForm.name || !applicationForm.description || !applicationForm.organisation || !applicationForm.url) {
      setError('Please fill in all required fields (name, description, organisation, url)');
      return;
    }
    setIsSubmitting(true);
    setError('');
    // If we already created the application (e.g. the user went Back and returned),
    // update it in place instead of creating a duplicate.
    if (wizardData.applicationId) {
      try {
        await adminAPI.updateApplication(wizardData.applicationId, buildApplicationPayload(applicationForm));
        setIsSubmitting(false);
        showSuccess(`Application "${applicationForm.name}" updated.`);
        setCurrentStep(3);
      } catch (err) {
        setIsSubmitting(false);
        setError(err?.response?.data?.detail || err?.message || 'Failed to update application');
      }
      return;
    }
    const result = await handleCreateApplication(applicationForm);
    setIsSubmitting(false);
    if (result.success) {
      setWizardData(prev => ({ ...prev, applicationId: result.data.id }));
      showSuccess(`Application "${applicationForm.name}" created successfully!`);
      setCurrentStep(3);
    } else {
      setError(result.error);
    }
  };

  // Step 3: Create Model
  const submitModel = async () => {
    if (!modelForm.name || !modelForm.task) {
      setError('Please fill in name and task');
      return;
    }
    setIsSubmitting(true);
    setError('');
    // If a model is already associated (created earlier or picked), don't create a
    // duplicate — reuse the existing id and just advance.
    if (wizardData.modelId) {
      setIsSubmitting(false);
      const existingId = wizardData.modelId;
      if (!modelForm.with_api_key && isBlackBox) {
        const ok = await createAuditForBlackBox(existingId);
        if (ok) { loadTenantUnderlyingFeatures(); setCurrentStep('5b'); }
      } else {
        setCurrentStep(modelForm.with_api_key ? 4 : nextAfterModel);
      }
      return;
    }
    const result = await handleCreateModel(modelForm);
    setIsSubmitting(false);
    if (result.success) {
      const newModelId = result.data.id;
      setWizardData(prev => ({ ...prev, modelId: newModelId }));
      showSuccess(`Model "${modelForm.name}" created successfully!`);
      if (!modelForm.with_api_key && isBlackBox) {
        const ok = await createAuditForBlackBox(newModelId);
        if (ok) { loadTenantUnderlyingFeatures(); setCurrentStep('5b'); }
      } else {
        setCurrentStep(modelForm.with_api_key ? 4 : nextAfterModel);
      }
    } else {
      setError(result.error);
    }
  };

  // Step 3 (Option B): Scaffold MCP model
  const submitScaffoldModel = async () => {
    if (!scaffoldForm.service_name || !scaffoldForm.tool_name) {
      setError('Please fill in service name and tool name');
      return;
    }
    setIsSubmitting(true);
    setError('');
    const result = await handleScaffoldModel(scaffoldForm);
    setIsSubmitting(false);
    if (result.success) {
      const newModelId = result.data.model_metadata_id;
      setWizardData(prev => ({ ...prev, modelId: newModelId }));
      showSuccess(`MCP service "${scaffoldForm.service_name}" scaffolded! Model ID: ${newModelId}`);
      if (isBlackBox) {
        const ok = await createAuditForBlackBox(newModelId);
        if (ok) { loadTenantUnderlyingFeatures(); setCurrentStep('5b'); }
      } else {
        setCurrentStep(nextAfterModel);
      }
    } else {
      setError(result.error);
    }
  };

  // Step 4: Create API Key
  const submitApiKey = async () => {
    if (!apiKeyForm.use_api_key) {
      showSuccess('Skipping API key creation.');
      if (isBlackBox) {
        const ok = await createAuditForBlackBox();
        if (ok) { loadTenantUnderlyingFeatures(); setCurrentStep('5b'); }
      } else {
        setCurrentStep(nextAfterModel);
      }
      return;
    }
    if (!apiKeyForm.model_api_key) {
      setError('Please provide the model API key');
      return;
    }
    setIsSubmitting(true);
    setError('');
    const result = await handleCreateApiKey(apiKeyForm, wizardData.modelId);
    setIsSubmitting(false);
    if (result.success) {
      setWizardData(prev => ({ ...prev, apiKeyId: result.data.id }));
      showSuccess('API Key created successfully!');
      if (isBlackBox) {
        const ok = await createAuditForBlackBox();
        if (ok) { loadTenantUnderlyingFeatures(); setCurrentStep('5b'); }
      } else {
        setCurrentStep(nextAfterModel);
      }
    } else {
      setError(result.error);
    }
  };

  // Step 5b (Black Box): load tenant-wide underlying features catalogue
  const loadTenantUnderlyingFeatures = async () => {
    try {
      const data = await adminAPI.listTenantUnderlyingFeatures();
      setTenantUnderlyingFeatures(Array.isArray(data) ? data : []);
    } catch {
      setTenantUnderlyingFeatures([]);
    }
  };

  // Step 5c: add a custom target feature (no METRICS_REGISTRY entry required)
  const addCustomTargetFeature = () => {
    const name = newTargetFeatureName.trim();
    if (!name) return;
    setNewTargetFeatureName('');
    setCustomTargetFeatures(prev => prev.includes(name) ? prev : [...prev, name]);
    setSelectedTargetFeatures(prev => prev.includes(name) ? prev : [...prev, name]);
    showSuccess(`Custom metric "${name}" added.`);
  };

  // Step 5b (Black Box): create a new feature in the tenant catalogue
  const createTenantUnderlyingFeature = async () => {
    const name = newUnderlyingFeatureName.trim();
    if (!name) return;
    try {
      await adminAPI.createTenantUnderlyingFeature(name);
      setNewUnderlyingFeatureName('');
      await loadTenantUnderlyingFeatures();
      setSelectedUnderlyingFeatures(prev => prev.includes(name) ? prev : [...prev, name]);
      showSuccess(`Feature "${name}" added to catalogue.`);
    } catch (err) {
      setError(err.message || 'Failed to add feature to catalogue');
    }
  };

  // Step 3: load existing models from API
  const loadExistingModels = async () => {
    setExistingModelsLoading(true);
    try {
      const data = await adminAPI.getModels();
      setExistingModels(Array.isArray(data) ? data : []);
    } catch {
      setExistingModels([]);
    }
    setExistingModelsLoading(false);
  };

  // Step 3: pick an already-registered model — skip creation entirely
  const selectExistingModel = async (model) => {
    setWizardData(prev => ({ ...prev, modelId: model.id }));
    showSuccess(`Model "${model.name}" selected.`);
    if (isBlackBox) {
      const ok = await createAuditForBlackBox(model.id);
      if (ok) { loadTenantUnderlyingFeatures(); setCurrentStep('5b'); }
    } else {
      setCurrentStep(nextAfterModel);
    }
  };

  // Dataset column helpers
  const updateColumn = (section, index, field, value) => {
    setDatasetForm(prev => {
      const cols = [...prev[section]];
      cols[index] = { ...cols[index], [field]: value };
      return { ...prev, [section]: cols };
    });
  };

  const addColumn = (section) => {
    setDatasetForm(prev => ({
      ...prev,
      [section]: [...prev[section], { name: '', type: '', range: '' }],
    }));
  };

  const removeColumn = (section, index) => {
    setDatasetForm(prev => ({
      ...prev,
      [section]: prev[section].filter((_, i) => i !== index),
    }));
  };

  const buildMetadataFromColumns = (columns) => {
    const headers = {};
    const datatypes = {};
    columns.forEach(col => {
      if (!col.name) return;
      headers[col.name] = col.type || 'str';
      if (col.type || col.range) {
        const dt = {};
        if (col.type) dt.type = col.type;
        if (col.range) {
          try {
            dt.range = JSON.parse(col.range);
          } catch {
            dt.range = col.range.split(',').map(s => s.trim());
          }
        }
        datatypes[col.name] = dt;
      }
    });
    return { headers, datatypes };
  };

  // Helper: create audit after dataset is ready (we now have all IDs)
  const createAuditAfterDataset = async (datasetId) => {
    // Already created (user went Back and returned) — update name/description, don't duplicate.
    if (wizardData.auditId) {
      try {
        await adminAPI.updateAudit(wizardData.auditId, {
          name: auditForm.name,
          description: auditForm.description,
        });
      } catch (e) {
        console.error('Could not update existing audit:', e);
      }
      return true;
    }
    const auditResult = await handleCreateAudit(
      auditForm,
      wizardData.applicationId,
      [wizardData.modelId],
      [datasetId]
    );
    if (auditResult.success) {
      const auditId = auditResult.data.id;
      // pipeline_created is a count, not an ID — use the pipeline endpoint to get the real pipeline ID
      let pipelineId = null;
      try {
        const pipeline = await adminAPI.getAuditPipeline(auditId);
        pipelineId = pipeline.pipeline_id || null;
      } catch (e) {
        console.error('Could not fetch pipeline id:', e);
      }
      setWizardData(prev => ({
        ...prev,
        auditId,
        auditPipelineId: pipelineId,
      }));
      loadFeaturesForMetrics(auditResult.data.id);
      return true;
    } else {
      setError(auditResult.error);
      return false;
    }
  };

  // Helper: create audit for Black Box (no dataset)
  const createAuditForBlackBox = async (modelId) => {
    // Already created (user went Back and returned) — update name/description, don't duplicate.
    if (wizardData.auditId) {
      try {
        await adminAPI.updateAudit(wizardData.auditId, {
          name: auditForm.name,
          description: auditForm.description,
        });
      } catch (e) {
        console.error('Could not update existing audit:', e);
      }
      return true;
    }
    const auditResult = await handleCreateAudit(
      auditForm,
      wizardData.applicationId,
      [modelId ?? wizardData.modelId],
      []
    );
    if (auditResult.success) {
      const auditId = auditResult.data.id;
      setWizardData(prev => ({ ...prev, auditId }));
      return true;
    } else {
      setError(auditResult.error);
      return false;
    }
  };

  // Step 5: Create Dataset (Option A - manual)
  const submitDataset = async () => {
    if (!datasetForm.purpose) {
      setError('Please provide a purpose for the dataset');
      return;
    }
    setIsSubmitting(true);
    setError('');

    const inputMeta = buildMetadataFromColumns(datasetForm.input_columns);
    const outputMeta = buildMetadataFromColumns(datasetForm.output_columns);

    const parseTargetFeatures = (str) => {
      if (!str) return [];
      try {
        return JSON.parse(str);
      } catch {
        return str.split(',').map(s => s.trim()).filter(Boolean);
      }
    };

    const payload = {
      purpose: datasetForm.purpose,
      copyright_agreement: datasetForm.copyright_agreement,
      input_metadata: {
        headers: inputMeta.headers,
        datatypes: inputMeta.datatypes,
        benchmark_dataset: datasetForm.input_benchmark,
        location: datasetForm.input_location,
      },
      output_metadata: {
        headers: outputMeta.headers,
        datatypes: outputMeta.datatypes,
        benchmark_dataset: datasetForm.output_benchmark,
        location: datasetForm.output_location,
      },
      target_features: parseTargetFeatures(datasetForm.target_features),
    };

    // If the dataset was already created (user went Back and returned), update it in
    // place instead of creating a duplicate, then reuse the same id downstream.
    if (wizardData.datasetId) {
      try {
        await adminAPI.updateDataset(wizardData.datasetId, {
          input_metadata: payload.input_metadata,
          output_metadata: payload.output_metadata,
        });
      } catch (e) {
        console.error('Could not update existing dataset:', e);
      }
      loadDatasetColumns(wizardData.datasetId);
      const auditOk2 = await createAuditAfterDataset(wizardData.datasetId);
      setIsSubmitting(false);
      if (auditOk2) { showSuccess('Dataset updated.'); setCurrentStep('5b'); }
      return;
    }

    const result = await handleCreateDataset(payload);
    if (result.success) {
      setWizardData(prev => ({ ...prev, datasetId: result.data.id }));
      showSuccess('Dataset created! Now creating audit...');
      loadDatasetColumns(result.data.id);
      const auditOk = await createAuditAfterDataset(result.data.id);
      setIsSubmitting(false);
      if (auditOk) {
        showSuccess(`Audit "${auditForm.name}" created successfully!`);
        setCurrentStep('5b');
      }
    } else {
      setIsSubmitting(false);
      setError(result.error);
    }
  };

  // Step 5: Import Dataset (Option B)
  const submitImportDataset = async () => {
    if (!importForm.dataset_name) {
      setError('Please provide a dataset name');
      return;
    }
    setIsSubmitting(true);
    setError('');
    const result = await handleImportDataset(importForm);
    if (result.success) {
      setWizardData(prev => ({ ...prev, datasetId: result.data.dataset_id }));
      showSuccess(`Dataset imported! Now creating audit...`);
      loadDatasetColumns(result.data.dataset_id);
      const auditOk = await createAuditAfterDataset(result.data.dataset_id);
      setIsSubmitting(false);
      if (auditOk) {
        showSuccess(`Audit "${auditForm.name}" created successfully!`);
        setCurrentStep('5b');
      }
    } else {
      setIsSubmitting(false);
      setError(result.error);
    }
  };

  // Load dataset columns for Step 5b
  const loadDatasetColumns = async (datasetId) => {
    try {
      const data = await adminAPI.getDatasetColumns(datasetId);
      setDatasetColumns(data);
    } catch (err) {
      console.error('Failed to load dataset columns:', err);
    }
  };

  // Load available metrics for Step 5c
  const loadAvailableMetrics = async () => {
    try {
      const data = await adminAPI.getAvailableMetrics();
      setAvailableMetrics(data);
    } catch (err) {
      console.error('Failed to load available metrics:', err);
    }
  };

  // Step 5b: Submit underlying features
  const submitUnderlyingFeatures = async () => {
    if (selectedUnderlyingFeatures.length === 0) {
      setError('Please select at least one distinguishing factor');
      return;
    }
    setIsSubmitting(true);
    setError('');
    try {
      for (const feature of selectedUnderlyingFeatures) {
        await adminAPI.createUserFeature(feature, wizardData.auditId);
      }
      showSuccess(`${selectedUnderlyingFeatures.length} distinguishing factor(s) registered!`);
      loadFeaturesForMetrics(wizardData.auditId);
      loadAvailableMetrics();
      setCurrentStep('5c');
    } catch (err) {
      setError(err.message || 'Failed to register features');
    }
    setIsSubmitting(false);
  };

  // Step 5c: Submit target features
  const submitTargetFeatures = async () => {
    if (selectedTargetFeatures.length === 0) {
      setError('Please select at least one target metric');
      return;
    }
    setIsSubmitting(true);
    setError('');
    try {
      for (const feature of selectedTargetFeatures) {
        await adminAPI.createUserTargetFeature(feature, wizardData.auditId);
      }
      showSuccess(`${selectedTargetFeatures.length} target metric(s) registered!`);
      loadFeaturesForMetrics(wizardData.auditId);
      if (isBlackBox) {
        setCurrentStep(6);
      } else {
        loadUploadedFiles(wizardData.auditId);
        setCurrentStep('5d');
      }
    } catch (err) {
      setError(err.message || 'Failed to register target features');
    }
    setIsSubmitting(false);
  };

  // Load features for metric creation (Step 8)
  // Combined endpoint returns: { underlying_features: { dataset_features: [...], user_features: [...] }, target_features: { system_features: [...], user_features: [...] } }
  const loadFeaturesForMetrics = async (auditId) => {
    try {
      const response = await adminAPI.getUnderlyingFeatures(auditId);
      const datasetUf = response.underlying_features?.dataset_features || [];
      const userUf = response.underlying_features?.user_features || [];
      const systemTf = response.target_features?.system_features || [];
      const userTf = response.target_features?.user_features || [];
      setUnderlyingFeatures([...datasetUf, ...userUf]);
      setTargetFeatures([...systemTf, ...userTf]);
    } catch (err) {
      console.error('Failed to load features:', err);
    }
  };

  // Step 5e: Load pipeline overview
  const loadPipelineOverview = async (auditId) => {
    setPipelineLoading(true);
    try {
      const data = await adminAPI.getAuditPipeline(auditId);
      setPipelineOverview(data);
    } catch (err) {
      console.error('Failed to load pipeline:', err);
    }
    setPipelineLoading(false);
  };

  // Step 4d: File upload helpers
  const loadUploadedFiles = async (auditId) => {
    try {
      const data = await uploadAPI.listAuditFiles(auditId);
      const files = Array.isArray(data) ? data : data.files || [];
      setUploadedFiles(files);
    } catch {
      // Not critical if this fails
      setUploadedFiles([]);
    }
  };

  const handleFileUpload = async (files) => {
    if (!files || files.length === 0) return;
    setIsUploading(true);
    setError('');
    try {
      const result = await uploadAPI.uploadAuditInput(wizardData.auditId, files);
      const newFiles = (result.uploaded_files || []).map(f =>
        typeof f === 'string' ? { filename: f } : f
      );
      setUploadedFiles(prev => [...prev, ...newFiles]);
      if (result.features_created && result.features_created.length > 0) {
        showSuccess(`${newFiles.length} file(s) uploaded! Features auto-created: ${result.features_created.join(', ')}`);
      } else {
        showSuccess(`${newFiles.length} file(s) uploaded successfully!`);
      }
    } catch (err) {
      setError(err.message || 'Failed to upload file(s)');
    }
    setIsUploading(false);
  };

  const handleDeleteUploadedFile = async (filename) => {
    try {
      await uploadAPI.deleteUploadedDataset(wizardData.auditId, { filename });
      setUploadedFiles(prev => prev.filter(f => (f.filename || f.name || f) !== filename));
      showSuccess(`File "${filename}" deleted.`);
    } catch (err) {
      setError(err.message || 'Failed to delete file');
    }
  };

  // Step 6: Add / Edit Entity
  const submitEntity = async () => {
    if (!entityForm.name) {
      setError('Please enter an entity name');
      return;
    }
    setIsSubmitting(true);
    setError('');
    try {
      if (editingEntityId) {
        const payload = {
          name: entityForm.name,
          ...(entityForm.num_individuals !== '' ? { num_individuals: parseInt(entityForm.num_individuals) } : {}),
        };
        const res = await adminAPI.adminEditEntity(wizardData.auditId, editingEntityId, payload);
        setWizardData(prev => ({
          ...prev,
          createdEntities: prev.createdEntities.map(e => e.id === editingEntityId ? { ...e, ...payload } : e),
        }));
        const alsoUsed = res?.also_used_by_audits || [];
        showSuccess(alsoUsed.length ? `Entity updated — also used by audit(s) ${alsoUsed.join(', ')}.` : `Entity "${entityForm.name}" updated!`);
        cancelEditEntity();
      } else {
        const result = await adminAPI.createEntity(entityForm.name, 0, wizardData.auditId);
        const newEntity = { id: result.entities_id ?? result.id, name: entityForm.name };
        setWizardData(prev => ({
          ...prev,
          createdEntities: [...prev.createdEntities, newEntity],
        }));
        showSuccess(`Entity "${entityForm.name}" created!`);
        setEntityForm({ name: '', num_individuals: '' });
      }
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to save entity');
    }
    setIsSubmitting(false);
  };

  // Step 7: Add Event
  const submitEvent = async () => {
    if (!eventForm.name || !eventForm.description) {
      setError('Please fill in name and description');
      return;
    }
    setIsSubmitting(true);
    setError('');

    // Editing an existing event → instigator PATCH (name/description/cause/reason + numeric fields).
    if (editingEventId) {
      try {
        const payload = {
          name: eventForm.name, description: eventForm.description,
          cause: eventForm.cause, reason: eventForm.reason,
          ...(eventForm.likelihood !== '' ? { likelihood: parseFloat(eventForm.likelihood) } : {}),
          ...(eventForm.magnitude !== '' ? { magnitude: parseFloat(eventForm.magnitude) } : {}),
          ...(eventForm.valence !== '' ? { valence: parseFloat(eventForm.valence) } : {}),
        };
        const res = await adminAPI.adminEditEvent(wizardData.auditId, editingEventId, payload);
        setIsSubmitting(false);
        setWizardData(prev => ({
          ...prev,
          createdEvents: prev.createdEvents.map(e => e.id === editingEventId ? { ...e, ...payload } : e),
        }));
        const alsoUsed = res?.also_used_by_audits || [];
        showSuccess(alsoUsed.length ? `Event updated — also used by audit(s) ${alsoUsed.join(', ')}.` : `Event "${eventForm.name}" updated!`);
        cancelEditEvent();
      } catch (err) {
        setIsSubmitting(false);
        setError(err?.response?.data?.detail || err?.message || 'Failed to update event');
      }
      return;
    }

    const formData = {
      ...eventForm,
      entity_ids: eventForm.entity_ids,
    };

    const result = await handleCreateEvent(formData, wizardData.auditId);
    setIsSubmitting(false);
    if (result.success) {
      const newEvent = {
        id: result.data.event_id ?? result.data.id,
        name: eventForm.name,
        description: eventForm.description,
        cause: eventForm.cause,
        reason: eventForm.reason,
        likelihood: eventForm.likelihood,
        magnitude: eventForm.magnitude,
        valence: eventForm.valence,
      };
      setWizardData(prev => ({
        ...prev,
        createdEvents: [...prev.createdEvents, newEvent],
      }));
      showSuccess(`Event "${eventForm.name}" created!`);
      setEventForm({
        name: '', description: '', cause: '', reason: '',
        likelihood: '0', magnitude: '0', valence: '0',
        category_ids: [], entity_ids: [],
      });
    } else {
      setError(result.error);
    }
  };

  // Step 8: Add Metric
  const submitMetric = async () => {
    if (!metricForm.name || metricForm.event_ids.length === 0) {
      setError('Please fill in name and select at least one event');
      return;
    }
    setIsSubmitting(true);
    setError('');

    let formData = { ...metricForm };
    if (metricForm.type === 'qualitative' && metricForm.scale_points_text) {
      try {
        formData.scale_points = JSON.parse(metricForm.scale_points_text);
      } catch {
        formData.scale_points = metricForm.scale_points_text.split(',').map((label, i) => ({
          label: label.trim(), value: i,
        }));
      }
    }

    // Editing an existing metric → instigator PATCH (name/description/reason + formula OR definition).
    if (editingMetricId) {
      try {
        const payload = {
          name: metricForm.name, description: metricForm.description, reason: metricForm.reason,
          ...(metricForm.type === 'quantitative' ? { formula: metricForm.formula } : { definition: metricForm.definition }),
        };
        const res = await adminAPI.adminEditMetric(wizardData.auditId, editingMetricId, payload);
        setIsSubmitting(false);
        setWizardData(prev => ({
          ...prev,
          createdMetrics: prev.createdMetrics.map(m => m.id === editingMetricId ? { ...m, name: metricForm.name, description: metricForm.description } : m),
        }));
        const alsoUsed = res?.also_used_by_audits || [];
        showSuccess(alsoUsed.length
          ? `Metric updated — also used by audit(s) ${alsoUsed.join(', ')}, changed too.`
          : `Metric "${metricForm.name}" updated!`);
        cancelEditMetric();
      } catch (err) {
        setIsSubmitting(false);
        setError(err?.response?.data?.detail || err?.message || 'Failed to update metric');
      }
      return;
    }

    const result = await handleCreateMetric(formData, wizardData.auditId);
    setIsSubmitting(false);
    if (result.success) {
      const newMetric = { id: result.data.metric_id ?? result.data.id, name: metricForm.name };
      setWizardData(prev => ({
        ...prev,
        createdMetrics: [...prev.createdMetrics, newMetric],
      }));
      showSuccess(`Metric "${metricForm.name}" created!`);
      setMetricForm({
        type: 'quantitative', name: '', description: '', reason: '',
        event_ids: [], threshold: '', formula: '',
        definition: '', scale_points_text: '',
        target_feature_id: '', underlying_feature_ids: [],
        feature_ranges: {},
      });
    } else {
      setError(result.error);
    }
  };

  // Step 9: Map to Pipeline
  const submitPipelineMapping = async () => {
    if (wizardData.pipelineMappings.length === 0) {
      setError('Please add at least one event-metric mapping');
      return;
    }
    setIsSubmitting(true);
    setError('');
    const result = await handleMapEventsToPipeline(
      wizardData.auditPipelineId,
      wizardData.pipelineMappings,
      wizardData.auditId
    );
    setIsSubmitting(false);
    if (result.success) {
      showSuccess('Pipeline mappings created successfully!');
      setCurrentStep(10);
    } else {
      setError(result.error);
    }
  };

  const addPipelineMapping = () => {
    if (!pipelineMappingForm.event_id || !pipelineMappingForm.metric_id) {
      setError('Please select both an event and a metric');
      return;
    }
    setError('');
    setWizardData(prev => ({
      ...prev,
      pipelineMappings: [...prev.pipelineMappings, { ...pipelineMappingForm }],
    }));
    setPipelineMappingForm({ event_id: '', metric_id: '' });
  };

  const removePipelineMapping = (index) => {
    setWizardData(prev => ({
      ...prev,
      pipelineMappings: prev.pipelineMappings.filter((_, i) => i !== index),
    }));
  };

  // Step 10: Invite Auditor
  const submitInviteAuditor = async () => {
    if (!auditorForm.email) {
      setError('Please enter an email address');
      return;
    }
    setIsSubmitting(true);
    setError('');
    const normalizedEmail = auditorForm.email.trim().toLowerCase();
    const result = await handleInviteAuditor(normalizedEmail, wizardData.auditId);
    setIsSubmitting(false);
    if (result.success) {
      setWizardData(prev => ({
        ...prev,
        invitedAuditors: [...prev.invitedAuditors, { email: result.data.user_email, name: result.data.user_name }],
      }));
      showSuccess(`${result.data.user_name} invited — invitation email sent`);
      setAuditorForm({ email: '' });
    } else {
      setError(result.error);
    }
  };

  const toggleUnderlyingFeature = (feature) => {
    setSelectedUnderlyingFeatures(prev =>
      prev.includes(feature) ? prev.filter(f => f !== feature) : [...prev, feature]
    );
  };

  // Helper to get the metric name whether it's a string or {name, function_name} object
  const getMetricName = (metric) => typeof metric === 'string' ? metric : metric.name;

  const toggleTargetFeature = (metricName) => {
    setSelectedTargetFeatures(prev =>
      prev.includes(metricName) ? prev.filter(m => m !== metricName) : [...prev, metricName]
    );
  };

  const toggleCategory = (category) => {
    setExpandedCategories(prev => ({ ...prev, [category]: !prev[category] }));
  };

  const toggleUnderlyingFeatureId = (featureId) => {
    setMetricForm(prev => {
      const ids = prev.underlying_feature_ids.includes(featureId)
        ? prev.underlying_feature_ids.filter(id => id !== featureId)
        : [...prev.underlying_feature_ids, featureId];
      return { ...prev, underlying_feature_ids: ids };
    });
  };

  // Set the raw comma-separated ranges string for a given feature id
  const setFeatureRanges = (featureId, value) => {
    setMetricForm(prev => ({
      ...prev,
      feature_ranges: { ...prev.feature_ranges, [featureId]: value },
    }));
  };

  const inputClass = "w-full px-3 py-2 bg-white/80 border-2 border-purple-200 rounded-lg focus:border-purple-500 outline-none transition-colors text-gray-800";
  const labelClass = "block text-sm font-medium text-gray-700 mb-1";
  const buttonPrimary = "bg-purple-100 hover:bg-purple-200 px-4 py-2 rounded-full text-sm font-semibold  border-2 border-purple-200";
  const buttonSecondary = "bg-purple-100 hover:bg-purple-200 px-4 py-2 rounded-full text-sm font-semibold  border-2 border-purple-200";

  const stepOrder = [1, 2, 3, 4, 5, '5b', '5c', '5d', '5e', 6, 7, 8, 9, 10];
  const blackBoxSkipStepIds = new Set([5, '5d', '5e', 9]);

  const renderStepIndicator = () => (
    <div className="flex items-center justify-center mb-8 overflow-x-auto pb-2">
      {STEPS.map((step, index) => {
        const currentIdx = stepOrder.indexOf(currentStep);
        const stepIdx = stepOrder.indexOf(step.id);
        const isComplete = stepIdx < currentIdx;
        const isCurrent = step.id === currentStep;
        const isSkipped = isBlackBox && blackBoxSkipStepIds.has(step.id);
        return (
          <div key={step.id} className="flex items-center">
            <div
              className={`flex items-center justify-center w-8 h-8 rounded-full text-sm font-semibold shrink-0 ${
                isSkipped
                  ? 'bg-gray-100 text-gray-300'
                  : isComplete
                    ? 'bg-green-500 text-purple'
                    : isCurrent
                      ? 'bg-purple-100 text-purple'
                      : 'bg-gray-200 text-gray-500'
              }`}
            >
              {isSkipped ? '–' : isComplete ? <Check className="w-4 h-4" /> : typeof step.id === 'string' ? step.id : step.id}
            </div>
            <span className={`ml-1 text-xs hidden sm:inline ${
              isSkipped ? 'text-gray-300 line-through' : isCurrent ? 'text-purple-700 font-semibold' : 'text-gray-500'
            }`}>
              {step.title}
            </span>
            {index < STEPS.length - 1 && (
              <div className={`w-6 h-0.5 mx-1 ${isComplete ? 'bg-green-500' : 'bg-gray-200'}`} />
            )}
          </div>
        );
      })}
    </div>
  );

  const renderStepAuditInfo = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-800">Create Audit</h3>
      <p className="text-sm text-gray-600">Start by naming your audit. You will set up the application, model, and dataset in the following steps.</p>
      <div className="grid grid-cols-2 gap-4">
        <div className="col-span-2">
          <label className={labelClass}>Audit Name *</label>
          <input type="text" value={auditForm.name} onChange={(e) => setAuditForm(p => ({ ...p, name: e.target.value }))} className={inputClass} placeholder="e.g. SAM Audit" />
        </div>
        <div className="col-span-2">
          <label className={labelClass}>Description *</label>
          <textarea value={auditForm.description} onChange={(e) => setAuditForm(p => ({ ...p, description: e.target.value }))} className={inputClass} rows={3} placeholder="Describe the purpose of this audit..." />
        </div>
      </div>
      <div className="flex justify-end pt-4">
        <button onClick={submitAuditInfo} disabled={isSubmitting} className={buttonPrimary}>
          Next: Create Application
          <ChevronRight className="w-4 h-4 inline ml-1" />
        </button>
      </div>
    </div>
  );

  const renderStep1 = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-800">Create Application</h3>
      <p className="text-sm text-gray-600">Define the AI application to be audited.</p>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelClass}>Application Name *</label>
          <input type="text" value={applicationForm.name} onChange={(e) => setApplicationForm(p => ({ ...p, name: e.target.value }))} className={inputClass} placeholder="e.g. SAM" />
        </div>
        <div>
          <label className={labelClass}>Organisation *</label>
          <input type="text" value={applicationForm.organisation} onChange={(e) => setApplicationForm(p => ({ ...p, organisation: e.target.value }))} className={inputClass} placeholder="e.g. NHS Trust" />
        </div>
        <div className="col-span-2">
          <label className={labelClass}>Description *</label>
          <textarea value={applicationForm.description} onChange={(e) => setApplicationForm(p => ({ ...p, description: e.target.value }))} className={inputClass} rows={2} placeholder="Describe the application..." />
        </div>
        <div>
          <label className={labelClass}>URL *</label>
          <input type="url" value={applicationForm.url} onChange={(e) => setApplicationForm(p => ({ ...p, url: e.target.value }))} className={inputClass} placeholder="https://example.com/app" />
        </div>
        <div>
          <label className={labelClass}>Access Type</label>
          <select value={applicationForm.access_type} onChange={(e) => setApplicationForm(p => ({ ...p, access_type: e.target.value }))} className={inputClass}>
            <option value="0">Opaque</option>
            <option value="1">Translucent</option>
            <option value="2">Transparent</option>
          </select>
        </div>
        <div className="col-span-2">
          <label className={labelClass}>Business Case</label>
          <textarea type="text" value={applicationForm.business_case} onChange={(e) => setApplicationForm(p => ({ ...p, business_case: e.target.value }))} rows={2} className={inputClass} placeholder="Describe the Business Case of your Application..." />
        </div>
        <div className="col-span-2">
          <label className={labelClass}>Legal Framework</label>
          <textarea type="text" value={applicationForm.legal_framework} onChange={(e) => setApplicationForm(p => ({ ...p, legal_framework: e.target.value }))} rows={2} className={inputClass} placeholder="Describe the Lega Framework that has been applied for your Application..." />
        </div>
      </div>

      <h4 className="text-md font-semibold text-gray-700 mt-2">Testing & Evaluation</h4>
      <div className="grid grid-cols-2 gap-4">
        <div className="col-span-2">
          <label className={labelClass}>Model Details</label>
          <textarea value={applicationForm.te_model_details} onChange={(e) => setApplicationForm(p => ({ ...p, te_model_details: e.target.value }))} className={inputClass} rows={2} placeholder="Describe the model used..." />
        </div>
        <div className="col-span-2">
          <label className={labelClass}>Dataset Details</label>
          <textarea value={applicationForm.te_dataset_details} onChange={(e) => setApplicationForm(p => ({ ...p, te_dataset_details: e.target.value }))} className={inputClass} rows={2} placeholder="Describe the dataset and how outputs are generated..." />
        </div>
        <div>
          <label className={labelClass}>Testing Details</label>
          <input type="text" value={applicationForm.te_testing_details} onChange={(e) => setApplicationForm(p => ({ ...p, te_testing_details: e.target.value }))} className={inputClass} placeholder="e.g. It has been tested before, internally." />
        </div>
        <div>
          <label className={labelClass}>Audit Instigator Details</label>
          <input type="text" value={applicationForm.te_audit_instigator_details} onChange={(e) => setApplicationForm(p => ({ ...p, te_audit_instigator_details: e.target.value }))} className={inputClass} placeholder="Name, role, contact email" />
        </div>
      </div>

      <h4 className="text-md font-semibold text-gray-700 mt-2">Deployment</h4>
      <div className="grid grid-cols-2 gap-4">
        <div className="col-span-2">
          <label className={labelClass}>Version / Status</label>
          <textarea value={applicationForm.deploy_version} onChange={(e) => setApplicationForm(p => ({ ...p, deploy_version: e.target.value }))} className={inputClass} rows={2} placeholder="e.g. Deployed. Used by..." />
        </div>
        <div className="col-span-2">
          <label className={labelClass}>Environment</label>
          <textarea value={applicationForm.deploy_environment} onChange={(e) => setApplicationForm(p => ({ ...p, deploy_environment: e.target.value }))} className={inputClass} rows={2} placeholder="Describe the deployment environment..." />
        </div>
      </div>

      <div className="flex justify-between pt-4">
        <button onClick={() => setCurrentStep(1)} className={buttonSecondary}>
          <ChevronLeft className="w-4 h-4 inline mr-1" /> Back
        </button>
        <button onClick={submitApplication} disabled={isSubmitting} className={buttonPrimary}>
          {isSubmitting ? 'Creating...' : 'Create Application'}
          <ChevronRight className="w-4 h-4 inline ml-1" />
        </button>
      </div>
    </div>
  );

  const renderStep2 = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-800">Select or Register a Model</h3>
      <p className="text-sm text-gray-600">Choose an existing model or register/scaffold a new one.</p>

      {/* Mode selector */}
      <div className="flex gap-3 mb-4">
        <button
          onClick={() => { setModelMode('pick'); loadExistingModels(); }}
          className={`flex items-center gap-2 px-4 py-3 rounded-xl border-2 transition-colors ${
            modelMode === 'pick'
              ? 'border-purple-500 bg-purple-50 text-purple-700'
              : 'border-purple-200 bg-white/80 text-gray-600 hover:bg-purple-50'
          }`}
        >
          <Check className="w-5 h-5" />
          <div className="text-left">
            <div className="font-semibold text-sm">Select Existing Model</div>
            <div className="text-xs opacity-75">Reuse a model already in the system</div>
          </div>
        </button>
        <button
          onClick={() => setModelMode('register')}
          className={`flex items-center gap-2 px-4 py-3 rounded-xl border-2 transition-colors ${
            modelMode === 'register'
              ? 'border-purple-500 bg-purple-50 text-purple-700'
              : 'border-purple-200 bg-white/80 text-gray-600 hover:bg-purple-50'
          }`}
        >
          <Settings className="w-5 h-5" />
          <div className="text-left">
            <div className="font-semibold text-sm">Register New Model</div>
            <div className="text-xs opacity-75">Point to an existing MCP server</div>
          </div>
        </button>
        <button
          onClick={() => setModelMode('scaffold')}
          className={`flex items-center gap-2 px-4 py-3 rounded-xl border-2 transition-colors ${
            modelMode === 'scaffold'
              ? 'border-purple-500 bg-purple-50 text-purple-700'
              : 'border-purple-200 bg-white/80 text-gray-600 hover:bg-purple-50'
          }`}
        >
          <Plus className="w-5 h-5" />
          <div className="text-left">
            <div className="font-semibold text-sm">Scaffold New Model</div>
            <div className="text-xs opacity-75">Generate MCP service files</div>
          </div>
        </button>
      </div>

      {modelMode === 'pick' ? (
        <>
          {existingModelsLoading ? (
            <p className="text-sm text-gray-500 py-4 text-center">Loading models...</p>
          ) : existingModels.length === 0 ? (
            <p className="text-sm text-gray-400 italic">No models found. Register or scaffold one below.</p>
          ) : (
            <div className="space-y-2">
              {existingModels.map(model => (
                <div key={model.id} className="flex items-center justify-between p-3 rounded-xl border-2 border-purple-200 bg-gradient-to-r from-purple-50 to-pink-50">
                  <div className="flex gap-6 text-sm">
                    <span className="font-medium text-gray-800">{model.name}</span>
                    <span className="text-gray-500">{model.task}</span>
                    <span className="text-gray-500">{model.model_type ? 'Generative AI' : 'Predictive AI'}</span>
                    {model.location && <span className="text-gray-400 font-mono text-xs">{model.location}</span>}
                  </div>
                  <button
                    onClick={() => selectExistingModel(model)}
                    disabled={isSubmitting}
                    className="px-3 py-1 rounded-full text-sm font-semibold border-2 border-purple-300 bg-purple-100 hover:bg-purple-200 transition-colors disabled:opacity-50"
                  >
                    Select
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="flex justify-between pt-4">
            <button onClick={() => setCurrentStep(2)} className={buttonSecondary}>
              <ChevronLeft className="w-4 h-4 inline mr-1" /> Back
            </button>
          </div>
        </>
      ) : modelMode === 'register' ? (
        <>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Model Name *</label>
              <input type="text" value={modelForm.name} onChange={(e) => setModelForm(p => ({ ...p, name: e.target.value }))} className={inputClass} placeholder="e.g. SAM" />
            </div>
            <div>
              <label className={labelClass}>Task *</label>
              <input type="text" value={modelForm.task} onChange={(e) => setModelForm(p => ({ ...p, task: e.target.value }))} className={inputClass} placeholder="e.g. classification" />
            </div>
            <div>
              <label className={labelClass}>Model Type</label>
              <select value={modelForm.model_type} onChange={(e) => setModelForm(p => ({ ...p, model_type: e.target.value }))} className={inputClass}>
                <option value="0">Predictive AI</option>
                <option value="1">Generative AI</option>
              </select>
            </div>
            {!isBlackBox && (
              <div>
                <label className={labelClass}>MCP Server URL</label>
                <input type="text" value={modelForm.location} onChange={(e) => setModelForm(p => ({ ...p, location: e.target.value }))} className={inputClass} placeholder="e.g. http://my-model:8010" />
              </div>
            )}
            {!isBlackBox && (
              <div>
                <label className={labelClass}>MCP Tool Name</label>
                <input type="text" value={modelForm.mcp_tool_name} onChange={(e) => setModelForm(p => ({ ...p, mcp_tool_name: e.target.value }))} className={inputClass} placeholder="e.g. predict_attachment" />
              </div>
            )}
            <div className="flex items-center gap-2 pt-2 col-span-2">
              <input
                type="checkbox"
                id="with_api_key"
                checked={modelForm.with_api_key}
                onChange={(e) => setModelForm(p => ({ ...p, with_api_key: e.target.checked }))}
                className="w-4 h-4 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
              />
              <label htmlFor="with_api_key" className="text-sm font-medium text-gray-700">Use LLM with API Key</label>
            </div>
            <div>
              <label className={labelClass}>Acceptable Formats</label>
              <input type="text" value={modelForm.acceptable_formats} onChange={(e) => setModelForm(p => ({ ...p, acceptable_formats: e.target.value }))} className={inputClass} placeholder="e.g. txt, html, wav, mp3" />
            </div>
            <div>
              <label className={labelClass}>Output Context</label>
              <input type="text" value={modelForm.output_context} onChange={(e) => setModelForm(p => ({ ...p, output_context: e.target.value }))} className={inputClass} placeholder="Expected output context" />
            </div>
          </div>
          <div className="flex justify-between pt-4">
            <button onClick={() => setCurrentStep(2)} className={buttonSecondary}>
              <ChevronLeft className="w-4 h-4 inline mr-1" /> Back
            </button>
            <button onClick={submitModel} disabled={isSubmitting} className={buttonPrimary}>
              {isSubmitting ? 'Creating...' : 'Create Model'}
              <ChevronRight className="w-4 h-4 inline ml-1" />
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Service Name *</label>
              <input type="text" value={scaffoldForm.service_name} onChange={(e) => setScaffoldForm(p => ({ ...p, service_name: e.target.value }))} className={inputClass} placeholder="e.g. my-classifier" />
            </div>
            <div>
              <label className={labelClass}>Tool Name *</label>
              <input type="text" value={scaffoldForm.tool_name} onChange={(e) => setScaffoldForm(p => ({ ...p, tool_name: e.target.value }))} className={inputClass} placeholder="e.g. classify_text" />
            </div>
            <div>
              <label className={labelClass}>Port</label>
              <input type="number" value={scaffoldForm.port} onChange={(e) => setScaffoldForm(p => ({ ...p, port: e.target.value }))} className={inputClass} placeholder="8010" />
              <p className="text-xs text-gray-400 mt-1">Reserved: 8002 (SAM), 8003 (LLM), 8004 (ANNIF), 8005 (Eval)</p>
            </div>
            <div>
              <label className={labelClass}>Model Type</label>
              <select value={scaffoldForm.model_type} onChange={(e) => setScaffoldForm(p => ({ ...p, model_type: e.target.value }))} className={inputClass}>
                <option value="0">Predictive AI</option>
                <option value="1">Generative AI</option>
              </select>
            </div>
            <div>
              <label className={labelClass}>Task</label>
              <input type="text" value={scaffoldForm.task} onChange={(e) => setScaffoldForm(p => ({ ...p, task: e.target.value }))} className={inputClass} placeholder="e.g. classification" />
            </div>
            <div>
              <label className={labelClass}>Acceptable Formats</label>
              <input type="text" value={scaffoldForm.acceptable_formats} onChange={(e) => setScaffoldForm(p => ({ ...p, acceptable_formats: e.target.value }))} className={inputClass} placeholder="e.g. txt, csv" />
            </div>
            <div className="col-span-2">
              <label className={labelClass}>Description</label>
              <textarea value={scaffoldForm.description} onChange={(e) => setScaffoldForm(p => ({ ...p, description: e.target.value }))} className={inputClass} rows={2} placeholder="Describe what this model does..." />
            </div>
            <div className="flex items-center gap-2 col-span-2">
              <input
                type="checkbox"
                id="needs_s3"
                checked={scaffoldForm.needs_s3}
                onChange={(e) => setScaffoldForm(p => ({ ...p, needs_s3: e.target.checked }))}
                className="w-4 h-4 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
              />
              <label htmlFor="needs_s3" className="text-sm font-medium text-gray-700">Needs S3 storage access</label>
            </div>
          </div>
          <div className="flex justify-between pt-4">
            <button onClick={() => setCurrentStep(2)} className={buttonSecondary}>
              <ChevronLeft className="w-4 h-4 inline mr-1" /> Back
            </button>
            <button onClick={submitScaffoldModel} disabled={isSubmitting} className={buttonPrimary}>
              {isSubmitting ? 'Scaffolding...' : 'Scaffold Model'}
              <ChevronRight className="w-4 h-4 inline ml-1" />
            </button>
          </div>
        </>
      )}
    </div>
  );

  const renderStep3 = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-800">Create API Key</h3>
      <p className="text-sm text-gray-600">Provide the API key for the model. This is required for the evaluation service.</p>
      {modelForm.location && (
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="use_api_key"
            checked={apiKeyForm.use_api_key}
            onChange={(e) => setApiKeyForm(p => ({ ...p, use_api_key: e.target.checked }))}
            className="w-4 h-4 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
          />
          <label htmlFor="use_api_key" className="text-sm font-medium text-gray-700">Use API Key</label>
          <span className="text-xs text-gray-500">(Model has a local location — API key may not be needed)</span>
        </div>
      )}
      {apiKeyForm.use_api_key && (
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelClass}>Model API Key *</label>
          <input type="text" value={apiKeyForm.model_api_key} onChange={(e) => setApiKeyForm(p => ({ ...p, model_api_key: e.target.value }))} className={inputClass} placeholder="sk-your-api-key-here" />
        </div>
        <div>
          <label className={labelClass}>Costing Policy</label>
          <input type="text" value={apiKeyForm.costing_policy} onChange={(e) => setApiKeyForm(p => ({ ...p, costing_policy: e.target.value }))} className={inputClass} placeholder="pay-per-request" />
        </div>
      </div>
      )}
      <div className="bg-purple-50 p-3 rounded-lg text-sm text-gray-600">
        <p>Model: <span className="font-semibold">{modelForm.name}</span> (ID: {wizardData.modelId})</p>
      </div>
      <div className="flex justify-between pt-4">
        <button onClick={() => setCurrentStep(3)} className={buttonSecondary}>
          <ChevronLeft className="w-4 h-4 inline mr-1" /> Back
        </button>
        <button onClick={submitApiKey} disabled={isSubmitting} className={buttonPrimary}>
          {isSubmitting ? 'Creating...' : 'Create API Key'}
          <ChevronRight className="w-4 h-4 inline ml-1" />
        </button>
      </div>
    </div>
  );

  const renderColumnRows = (section) => (
    <div className="space-y-2">
      <div className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2 text-xs font-medium text-gray-500 px-1">
        <span>Column Name</span>
        <span>Type</span>
        <span>Range / Values</span>
        <span></span>
      </div>
      {datasetForm[section].map((col, i) => (
        <div key={i} className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2 items-center">
          <input
            type="text" value={col.name}
            onChange={(e) => updateColumn(section, i, 'name', e.target.value)}
            className={inputClass} placeholder="e.g. gender"
          />
          <select
            value={col.type}
            onChange={(e) => updateColumn(section, i, 'type', e.target.value)}
            className={inputClass}
          >
            <option value="">Select type</option>
            <option value="str">str</option>
            <option value="int">int</option>
            <option value="float">float</option>
            <option value="bool">bool</option>
            <option value="varchar(20)">varchar(20)</option>
            <option value="varchar(50)">varchar(50)</option>
            <option value="varchar(255)">varchar(255)</option>
            <option value="text">text</option>
          </select>
          <input
            type="text" value={col.range}
            onChange={(e) => updateColumn(section, i, 'range', e.target.value)}
            className={inputClass} placeholder="e.g. male, female or 0, 100"
          />
          <button
            onClick={() => removeColumn(section, i)}
            disabled={datasetForm[section].length <= 1}
            className="text-red-400 hover:text-red-600 disabled:opacity-30 p-1"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ))}
      <button onClick={() => addColumn(section)} className="text-purple-600 hover:text-purple-800 text-sm font-medium flex items-center gap-1 mt-1">
        <Plus className="w-3 h-3" /> Add column
      </button>
    </div>
  );

  const renderStep4 = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-800">Create Dataset</h3>
      <p className="text-sm text-gray-600">Choose how to set up your dataset for evaluation.</p>

      {/* Mode selector */}
      <div className="flex gap-3 mb-4">
        <button
          onClick={() => setDatasetMode('manual')}
          className={`flex items-center gap-2 px-4 py-3 rounded-xl border-2 transition-colors ${
            datasetMode === 'manual'
              ? 'border-purple-500 bg-purple-50 text-purple-700'
              : 'border-purple-200 bg-white/80 text-gray-600 hover:bg-purple-50'
          }`}
        >
          <FileText className="w-5 h-5" />
          <div className="text-left">
            <div className="font-semibold text-sm">Manual Metadata</div>
            <div className="text-xs opacity-75">Define columns and metadata manually</div>
          </div>
        </button>
        <button
          onClick={() => setDatasetMode('import')}
          className={`flex items-center gap-2 px-4 py-3 rounded-xl border-2 transition-colors ${
            datasetMode === 'import'
              ? 'border-purple-500 bg-purple-50 text-purple-700'
              : 'border-purple-200 bg-white/80 text-gray-600 hover:bg-purple-50'
          }`}
        >
          <Download className="w-5 h-5" />
          <div className="text-left">
            <div className="font-semibold text-sm">Import Dataset</div>
            <div className="text-xs opacity-75">HuggingFace, PyTorch, or URL</div>
          </div>
        </button>
      </div>

      {datasetMode === 'manual' ? (
        /* Option A: Manual metadata */
        <div className="space-y-4">
          <div>
            <label className={labelClass}>Purpose *</label>
            <input type="text" value={datasetForm.purpose} onChange={(e) => setDatasetForm(p => ({ ...p, purpose: e.target.value }))} className={inputClass} placeholder="e.g. SAM evaluation dataset" />
          </div>
          <div className="flex items-center gap-2">
            <input type="checkbox" id="copyright_agreement" checked={datasetForm.copyright_agreement} onChange={(e) => setDatasetForm(p => ({ ...p, copyright_agreement: e.target.checked }))} className="w-4 h-4 accent-purple-600" />
            <label htmlFor="copyright_agreement" className="text-sm text-gray-700">Copyright agreement accepted</label>
          </div>

          <h4 className="text-md font-semibold text-gray-700 mt-4">Input Columns</h4>
          {renderColumnRows('input_columns')}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Location</label>
              <input type="text" value={datasetForm.input_location} onChange={(e) => setDatasetForm(p => ({ ...p, input_location: e.target.value }))} className={inputClass} placeholder="storage/audits/..." />
            </div>
            <div className="flex items-center gap-2 pt-6">
              <input type="checkbox" checked={datasetForm.input_benchmark} onChange={(e) => setDatasetForm(p => ({ ...p, input_benchmark: e.target.checked }))} className="w-4 h-4 accent-purple-600" />
              <label className="text-sm text-gray-700">Benchmark dataset</label>
            </div>
          </div>

          <h4 className="text-md font-semibold text-gray-700 mt-4">Output Columns</h4>
          {renderColumnRows('output_columns')}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Location</label>
              <input type="text" value={datasetForm.output_location} onChange={(e) => setDatasetForm(p => ({ ...p, output_location: e.target.value }))} className={inputClass} placeholder="storage/audits/..." />
            </div>
            <div className="flex items-center gap-2 pt-6">
              <input type="checkbox" checked={datasetForm.output_benchmark} onChange={(e) => setDatasetForm(p => ({ ...p, output_benchmark: e.target.checked }))} className="w-4 h-4 accent-purple-600" />
              <label className="text-sm text-gray-700">Benchmark dataset</label>
            </div>
          </div>

          <div>
            <label className={labelClass}>Target Features (comma-separated)</label>
            <input type="text" value={datasetForm.target_features} onChange={(e) => setDatasetForm(p => ({ ...p, target_features: e.target.value }))} className={inputClass} placeholder='Accuracy, Recall, F1' />
          </div>

          <div className="flex justify-between pt-4">
            <button onClick={() => setCurrentStep(4)} className={buttonSecondary}>
              <ChevronLeft className="w-4 h-4 inline mr-1" /> Back
            </button>
            <button onClick={submitDataset} disabled={isSubmitting} className={buttonPrimary}>
              {isSubmitting ? 'Creating...' : 'Create Dataset'}
              <ChevronRight className="w-4 h-4 inline ml-1" />
            </button>
          </div>
        </div>
      ) : (
        /* Option B: Import dataset */
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Source Type *</label>
              <select value={importForm.source_type} onChange={(e) => setImportForm(p => ({ ...p, source_type: e.target.value }))} className={inputClass}>
                <option value="huggingface">HuggingFace</option>
                <option value="pytorch">PyTorch (torchvision)</option>
                <option value="file">File URL (CSV, JSON, Parquet)</option>
              </select>
            </div>
            <div>
              <label className={labelClass}>
                {importForm.source_type === 'file' ? 'File URL *' : 'Dataset Name *'}
              </label>
              <input
                type="text"
                value={importForm.dataset_name}
                onChange={(e) => setImportForm(p => ({ ...p, dataset_name: e.target.value }))}
                className={inputClass}
                placeholder={
                  importForm.source_type === 'huggingface' ? 'e.g. imdb, glue'
                  : importForm.source_type === 'pytorch' ? 'e.g. cifar10, mnist'
                  : 'https://example.com/data.csv'
                }
              />
            </div>
            <div>
              <label className={labelClass}>Split</label>
              <input type="text" value={importForm.split} onChange={(e) => setImportForm(p => ({ ...p, split: e.target.value }))} className={inputClass} placeholder="e.g. test, train" />
            </div>
            <div>
              <label className={labelClass}>Subset</label>
              <input type="text" value={importForm.subset} onChange={(e) => setImportForm(p => ({ ...p, subset: e.target.value }))} className={inputClass} placeholder="Optional subset name" />
            </div>
            <div>
              <label className={labelClass}>Max Samples</label>
              <input type="number" value={importForm.max_samples} onChange={(e) => setImportForm(p => ({ ...p, max_samples: e.target.value }))} className={inputClass} placeholder="e.g. 1000 (leave empty for all)" />
            </div>
            <div>
              <label className={labelClass}>Purpose</label>
              <input type="text" value={importForm.purpose} onChange={(e) => setImportForm(p => ({ ...p, purpose: e.target.value }))} className={inputClass} placeholder="e.g. Sentiment analysis benchmark" />
            </div>
            <div>
              <label className={labelClass}>Label Column</label>
              <input type="text" value={importForm.label_column} onChange={(e) => setImportForm(p => ({ ...p, label_column: e.target.value }))} className={inputClass} placeholder="Auto-detected if empty" />
            </div>
            <div>
              <label className={labelClass}>Text Column</label>
              <input type="text" value={importForm.text_column} onChange={(e) => setImportForm(p => ({ ...p, text_column: e.target.value }))} className={inputClass} placeholder="Auto-detected if empty" />
            </div>
          </div>

          <div className="bg-purple-50 p-3 rounded-lg text-sm text-gray-600">
            <p>You can select distinguishing factors and target metrics interactively in the next steps.</p>
          </div>

          <div className="flex justify-between pt-4">
            <button onClick={() => setCurrentStep(4)} className={buttonSecondary}>
              <ChevronLeft className="w-4 h-4 inline mr-1" /> Back
            </button>
            <button onClick={submitImportDataset} disabled={isSubmitting} className={buttonPrimary}>
              {isSubmitting ? 'Importing...' : 'Import Dataset'}
              <ChevronRight className="w-4 h-4 inline ml-1" />
            </button>
          </div>
        </div>
      )}
    </div>
  );

  const renderStep4b = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-800">Select Distinguishing Factors</h3>
      <p className="text-sm text-gray-600">
        {isBlackBox
          ? 'Pick from the tenant catalogue of distinguishing factors, or add a new one. These attributes can be referenced by metrics during the audit.'
          : 'Choose which columns from the dataset should be used as distinguishing factors for fairness and performance analysis.'}
      </p>

      {isBlackBox ? (
        <>
          <div className="flex gap-2 items-end">
            <div className="flex-1">
              <label className={labelClass}>Add new distinguishing factor to catalogue</label>
              <input
                type="text"
                value={newUnderlyingFeatureName}
                onChange={(e) => setNewUnderlyingFeatureName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && createTenantUnderlyingFeature()}
                className={inputClass}
                placeholder="e.g. age, gender, region"
              />
            </div>
            <button
              onClick={createTenantUnderlyingFeature}
              disabled={!newUnderlyingFeatureName.trim()}
              className={buttonSecondary}
            >
              <Plus className="w-4 h-4 inline mr-1" /> Add
            </button>
          </div>

          {tenantUnderlyingFeatures.length > 0 ? (
            <div className="space-y-2">
              <p className="text-sm font-medium text-gray-700">Available factors:</p>
              <div className="grid grid-cols-2 gap-2">
                {tenantUnderlyingFeatures.map(feature => (
                  <label key={feature.id} className="flex items-center gap-2 p-2 rounded-lg border-2 border-purple-100 hover:bg-purple-50 cursor-pointer transition-colors">
                    <input
                      type="checkbox"
                      checked={selectedUnderlyingFeatures.includes(feature.feature_name)}
                      onChange={() => toggleUnderlyingFeature(feature.feature_name)}
                      className="w-4 h-4 accent-purple-600"
                    />
                    <span className="text-sm text-gray-700">{feature.feature_name}</span>
                  </label>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-500 italic">No distinguishing factors in the catalogue yet. Add one above.</p>
          )}

          {selectedUnderlyingFeatures.length > 0 && (
            <div className="bg-green-50 p-3 rounded-lg">
              <p className="text-sm font-medium text-green-800">Selected factors ({selectedUnderlyingFeatures.length}):</p>
              <div className="flex flex-wrap gap-2 mt-1">
                {selectedUnderlyingFeatures.map(f => (
                  <span key={f} className="px-2 py-1 bg-green-200 text-green-800 rounded text-xs font-medium">{f}</span>
                ))}
              </div>
            </div>
          )}

          <div className="bg-purple-50 p-3 rounded-lg text-sm text-gray-600">
            <p>Audit: <span className="font-semibold">{auditForm.name}</span> (ID: {wizardData.auditId})</p>
          </div>

          <div className="flex justify-between pt-4">
            <button onClick={() => setCurrentStep(3)} className={buttonSecondary}>
              <ChevronLeft className="w-4 h-4 inline mr-1" /> Back
            </button>
            <div className="flex gap-2">
              <button onClick={() => { setError(''); loadAvailableMetrics(); setCurrentStep('5c'); }} className={buttonSecondary}>
                Skip
              </button>
              <button onClick={submitUnderlyingFeatures} disabled={isSubmitting || selectedUnderlyingFeatures.length === 0} className={buttonPrimary}>
                {isSubmitting ? 'Registering...' : 'Register Features'}
                <ChevronRight className="w-4 h-4 inline ml-1" />
              </button>
            </div>
          </div>
        </>
      ) : datasetColumns ? (
        <>
          {datasetColumns.system_columns && datasetColumns.system_columns.length > 0 && (
            <div className="bg-gray-50 p-3 rounded-lg">
              <p className="text-xs font-medium text-gray-500 mb-1">System columns (not selectable):</p>
              <div className="flex flex-wrap gap-2">
                {datasetColumns.system_columns.map(col => (
                  <span key={col} className="px-2 py-1 bg-gray-200 text-gray-500 rounded text-xs">{col}</span>
                ))}
              </div>
            </div>
          )}

          {datasetColumns.selectable_as_features && datasetColumns.selectable_as_features.length > 0 ? (
            <div className="space-y-2">
              <p className="text-sm font-medium text-gray-700">Available columns:</p>
              <div className="grid grid-cols-2 gap-2">
                {datasetColumns.selectable_as_features.map(col => (
                  <label key={col} className="flex items-center gap-2 p-2 rounded-lg border-2 border-purple-100 hover:bg-purple-50 cursor-pointer transition-colors">
                    <input
                      type="checkbox"
                      checked={selectedUnderlyingFeatures.includes(col)}
                      onChange={() => toggleUnderlyingFeature(col)}
                      className="w-4 h-4 accent-purple-600"
                    />
                    <span className="text-sm text-gray-700">{col}</span>
                  </label>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-500 italic">No selectable columns found in this dataset.</p>
          )}

          {selectedUnderlyingFeatures.length > 0 && (
            <div className="bg-green-50 p-3 rounded-lg">
              <p className="text-sm font-medium text-green-800">Selected factors ({selectedUnderlyingFeatures.length}):</p>
              <div className="flex flex-wrap gap-2 mt-1">
                {selectedUnderlyingFeatures.map(f => (
                  <span key={f} className="px-2 py-1 bg-green-200 text-green-800 rounded text-xs font-medium">{f}</span>
                ))}
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="text-center py-6 text-gray-500">
          <p>Loading dataset columns...</p>
        </div>
      )}

      {!isBlackBox && (
        <>
          <div className="bg-purple-50 p-3 rounded-lg text-sm text-gray-600">
            <p>Dataset ID: <span className="font-semibold">{wizardData.datasetId}</span></p>
            <p>Audit: <span className="font-semibold">{auditForm.name}</span> (ID: {wizardData.auditId})</p>
          </div>

          <div className="flex justify-between pt-4">
            <button onClick={() => setCurrentStep(5)} className={buttonSecondary}>
              <ChevronLeft className="w-4 h-4 inline mr-1" /> Back
            </button>
            <div className="flex gap-2">
              <button onClick={() => { setError(''); loadAvailableMetrics(); setCurrentStep('5c'); }} className={buttonSecondary}>
                Skip
              </button>
              <button onClick={submitUnderlyingFeatures} disabled={isSubmitting || selectedUnderlyingFeatures.length === 0} className={buttonPrimary}>
                {isSubmitting ? 'Registering...' : 'Register Features'}
                <ChevronRight className="w-4 h-4 inline ml-1" />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );

  const renderStep4c = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-800">Select Target Metrics</h3>
      <p className="text-sm text-gray-600">
        Choose which evaluation metrics (target features) the pipeline should compute. You can also add a custom metric — it will be registered without an automatic computation function.
      </p>

      <div className="flex gap-2 items-end">
        <div className="flex-1">
          <label className={labelClass}>Add custom metric</label>
          <input
            type="text"
            value={newTargetFeatureName}
            onChange={(e) => setNewTargetFeatureName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addCustomTargetFeature()}
            className={inputClass}
            placeholder="e.g. domain-specific score, manual review rating"
          />
        </div>
        <button
          onClick={addCustomTargetFeature}
          disabled={!newTargetFeatureName.trim()}
          className={buttonSecondary}
        >
          <Plus className="w-4 h-4 inline mr-1" /> Add
        </button>
      </div>

      {customTargetFeatures.length > 0 && (
        <div className="border-2 border-purple-100 rounded-lg overflow-hidden">
          <div className="p-3 bg-purple-50/50">
            <span className="text-sm font-semibold text-gray-700">Custom metrics</span>
          </div>
          <div className="p-3 grid grid-cols-3 gap-2">
            {customTargetFeatures.map(name => (
              <label key={name} className="flex items-center gap-2 p-1.5 rounded hover:bg-purple-50 cursor-pointer text-sm">
                <input
                  type="checkbox"
                  checked={selectedTargetFeatures.includes(name)}
                  onChange={() => toggleTargetFeature(name)}
                  className="w-4 h-4 accent-purple-600"
                />
                <div>
                  <span className="text-gray-700">{name}</span>
                  <span className="block text-xs text-gray-400">no registry function</span>
                </div>
              </label>
            ))}
          </div>
        </div>
      )}

      {availableMetrics ? (
        <>
          {availableMetrics.by_category && Object.keys(availableMetrics.by_category).length > 0 ? (
            <div className="space-y-2">
              {Object.entries(availableMetrics.by_category).map(([category, metrics]) => {
                const metricNames = metrics.map(m => getMetricName(m));
                const selectedCount = metricNames.filter(n => selectedTargetFeatures.includes(n)).length;
                return (
                  <div key={category} className="border-2 border-purple-100 rounded-lg overflow-hidden">
                    <button
                      onClick={() => toggleCategory(category)}
                      className="w-full flex items-center justify-between p-3 bg-purple-50/50 hover:bg-purple-50 transition-colors"
                    >
                      <span className="text-sm font-semibold text-gray-700 capitalize">{category}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500">
                          {selectedCount}/{metrics.length}
                        </span>
                        {expandedCategories[category]
                          ? <ChevronUp className="w-4 h-4 text-gray-400" />
                          : <ChevronDown className="w-4 h-4 text-gray-400" />
                        }
                      </div>
                    </button>
                    {expandedCategories[category] && (
                      <div className="p-3 grid grid-cols-3 gap-2">
                        {metrics.map(metric => {
                          const name = getMetricName(metric);
                          const fnName = typeof metric === 'object' ? metric.function_name : null;
                          return (
                            <label key={name} className="flex items-center gap-2 p-1.5 rounded hover:bg-purple-50 cursor-pointer text-sm">
                              <input
                                type="checkbox"
                                checked={selectedTargetFeatures.includes(name)}
                                onChange={() => toggleTargetFeature(name)}
                                className="w-4 h-4 accent-purple-600"
                              />
                              <div>
                                <span className="text-gray-700">{name}</span>
                                {fnName && <span className="block text-xs text-gray-400">{fnName}</span>}
                              </div>
                            </label>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-gray-500 italic">No metrics available from the registry.</p>
          )}

          {selectedTargetFeatures.length > 0 && (
            <div className="bg-green-50 p-3 rounded-lg">
              <p className="text-sm font-medium text-green-800">Selected metrics ({selectedTargetFeatures.length}):</p>
              <div className="flex flex-wrap gap-2 mt-1">
                {selectedTargetFeatures.map(m => (
                  <span key={m} className="px-2 py-1 bg-green-200 text-green-800 rounded text-xs font-medium">{m}</span>
                ))}
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="text-center py-6 text-gray-500">
          <p>Loading available metrics...</p>
        </div>
      )}

      <div className="flex justify-between pt-4">
        <button onClick={() => setCurrentStep('5b')} className={buttonSecondary}>
          <ChevronLeft className="w-4 h-4 inline mr-1" /> Back
        </button>
        <div className="flex gap-2">
          <button
            onClick={() => {
              setError('');
              if (isBlackBox) {
                setCurrentStep(6);
              } else {
                loadUploadedFiles(wizardData.auditId);
                setCurrentStep('5d');
              }
            }}
            className={buttonSecondary}
          >
            Skip
          </button>
          <button onClick={submitTargetFeatures} disabled={isSubmitting || selectedTargetFeatures.length === 0} className={buttonPrimary}>
            {isSubmitting ? 'Registering...' : 'Register Metrics'}
            <ChevronRight className="w-4 h-4 inline ml-1" />
          </button>
        </div>
      </div>
    </div>
  );

  const renderStep4d = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-800">Upload Dataset Files</h3>
      <p className="text-sm text-gray-600">
        Upload your data files (CSV, JSON, images, audio, etc.) to the audit storage.
        If you include a <span className="font-semibold">metadata.csv</span>, distinguishing factors will be extracted automatically.
      </p>

      {/* File upload area */}
      <div
        className="border-2 border-dashed border-purple-300 rounded-xl p-8 text-center hover:border-purple-500 hover:bg-purple-50/50 transition-colors cursor-pointer"
        onClick={() => document.getElementById('file-upload-input').click()}
        onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
        onDrop={(e) => {
          e.preventDefault();
          e.stopPropagation();
          handleFileUpload(e.dataTransfer.files);
        }}
      >
        <Upload className="w-8 h-8 text-purple-400 mx-auto mb-2" />
        <p className="text-sm text-gray-600 mb-1">
          {isUploading ? 'Uploading...' : 'Click to select files or drag and drop'}
        </p>
        <p className="text-xs text-gray-400">Supported: CSV, JSON, XLSX, TXT, Parquet, PDF, WAV, images</p>
        <input
          id="file-upload-input"
          type="file"
          multiple
          className="hidden"
          onChange={(e) => handleFileUpload(e.target.files)}
          disabled={isUploading}
        />
      </div>

      {/* Uploaded files list */}
      {uploadedFiles.length > 0 && (
        <div className="bg-green-50 p-3 rounded-lg">
          <p className="text-sm font-semibold text-green-800 mb-2">Uploaded Files ({uploadedFiles.length}):</p>
          <div className="space-y-1">
            {uploadedFiles.map((file, i) => {
              const fname = file.filename || file.name || file;
              const fsize = file.file_size;
              return (
                <div key={i} className="flex items-center justify-between text-sm text-green-700 py-1">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-green-500" />
                    <span>{fname}</span>
                    {fsize && <span className="text-xs text-green-500">({(fsize / 1024).toFixed(1)} KB)</span>}
                  </div>
                  <button
                    onClick={() => handleDeleteUploadedFile(fname)}
                    className="text-red-400 hover:text-red-600 p-1"
                    title="Remove file"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="bg-purple-50 p-3 rounded-lg text-sm text-gray-600">
        <p>Audit: <span className="font-semibold">{auditForm.name}</span> (ID: {wizardData.auditId})</p>
        <p className="text-xs mt-1">Files are stored in <code className="bg-gray-100 px-1 rounded">storage/audits/audit_{wizardData.auditId}/input/</code></p>
      </div>

      <div className="flex justify-between pt-4">
        <button onClick={() => setCurrentStep('5c')} className={buttonSecondary}>
          <ChevronLeft className="w-4 h-4 inline mr-1" /> Back
        </button>
        <button onClick={() => { setError(''); loadPipelineOverview(wizardData.auditId); setCurrentStep('5e'); }} className={buttonPrimary}>
          {uploadedFiles.length > 0 ? 'Next' : 'Skip'}
          <ChevronRight className="w-4 h-4 inline ml-1" />
        </button>
      </div>
    </div>
  );

  const renderStep5e = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-800">Pipeline Wiring</h3>
      <p className="text-sm text-gray-600">Confirm which model-dataset pairs are active in the audit pipeline. You can add or remove pairs before proceeding.</p>

      {pipelineLoading ? (
        <div className="text-sm text-gray-500 py-4 text-center">Loading pipeline...</div>
      ) : pipelineOverview ? (
        <div className="space-y-3">
          <div className="bg-purple-50 p-3 rounded-lg text-sm text-gray-600 flex gap-4">
            <span>Audit ID: <strong>{pipelineOverview.audit_id}</strong></span>
            <span>Pipeline ID: <strong>{pipelineOverview.pipeline_id}</strong></span>
            <span>Models: <strong>{pipelineOverview.total_models}</strong></span>
            <span>Datasets: <strong>{pipelineOverview.total_datasets}</strong></span>
          </div>

          {pipelineOverview.pairs?.length === 0 ? (
            <p className="text-sm text-yellow-700 bg-yellow-50 p-3 rounded-lg">No model-dataset pairs wired yet. Add at least one pair below.</p>
          ) : (
            <div className="space-y-2">
              {pipelineOverview.pairs?.map(pair => (
                <div key={pair.mapping_id} className="flex items-center justify-between p-3 rounded-xl border-2 border-purple-200 bg-gradient-to-r from-purple-50 to-pink-50 text-sm">
                  <div className="flex gap-6">
                    <span className="font-medium text-gray-800">{pair.model_name}</span>
                    <span className="text-gray-500">{pair.dataset_purpose}</span>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${pair.dataset_has_input ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {pair.dataset_has_input ? 'Has Input' : 'No Input'}
                    </span>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${pair.dataset_has_output ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500'}`}>
                      {pair.dataset_has_output ? 'Has Output' : 'No Output'}
                    </span>
                  </div>
                  <button
                    onClick={async () => {
                      try {
                        const updated = await adminAPI.removePipelinePair(pipelineOverview.audit_id, pair.mapping_id);
                        setPipelineOverview(updated);
                      } catch (err) {
                        setError(err.message || 'Failed to remove pair');
                      }
                    }}
                    className="text-red-400 hover:text-red-600 p-1 rounded-full hover:bg-red-50"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <p className="text-sm text-gray-500">Pipeline data not loaded.</p>
      )}

      <div className="flex justify-between pt-4">
        <button onClick={() => setCurrentStep('5d')} className={buttonSecondary}>
          <ChevronLeft className="w-4 h-4 inline mr-1" /> Back
        </button>
        <button onClick={() => { setError(''); setCurrentStep(6); }} className={buttonPrimary}>
          Next <ChevronRight className="w-4 h-4 inline ml-1" />
        </button>
      </div>
    </div>
  );

  const renderStep6 = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-800">Create Entities</h3>
      <p className="text-sm text-gray-600">Define the entities (e.g. stakeholder groups) that events may affect. You can add multiple entities.</p>

      {wizardData.createdEntities.length > 0 && (
        <div className="bg-green-50 p-3 rounded-lg">
          <p className="text-sm font-semibold text-green-800 mb-2">{isEdit ? 'Entities — click Edit to modify:' : 'Created Entities:'}</p>
          <div className="space-y-1">
            {wizardData.createdEntities.map((ent, i) => (
              <div key={i} className="flex items-center justify-between gap-2">
                <span className="text-sm text-green-700">- {ent.name} (ID: {ent.id})</span>
                {isEdit && (
                  <button onClick={() => startEditEntity(ent)} className={`text-xs font-semibold px-2.5 py-1 rounded-full border-2 ${editingEntityId === ent.id ? 'bg-purple-600 border-purple-600 text-white' : 'border-purple-200 text-purple-700 hover:bg-purple-50'}`}>
                    {editingEntityId === ent.id ? 'Editing' : 'Edit'}
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelClass}>Entity Name *</label>
          <input type="text" value={entityForm.name} onChange={(e) => setEntityForm(p => ({ ...p, name: e.target.value }))} className={inputClass} placeholder="e.g. Patients" />
        </div>
        <div>
          <label className={labelClass}>Number of Individuals</label>
          <input type="number" value={entityForm.num_individuals} onChange={(e) => setEntityForm(p => ({ ...p, num_individuals: e.target.value }))} className={inputClass} placeholder="e.g. 120" />
        </div>
      </div>
      <div className="bg-purple-50 p-3 rounded-lg text-sm text-gray-600">
        <p>Audit: <span className="font-semibold">{auditForm.name}</span> (ID: {wizardData.auditId})</p>
      </div>
      <div className="flex justify-between pt-4">
        {!isEdit ? (
          <button onClick={() => setCurrentStep(isBlackBox ? '5c' : '5e')} className={buttonSecondary}>
            <ChevronLeft className="w-4 h-4 inline mr-1" /> Back
          </button>
        ) : <span />}
        <div className="flex gap-2">
          {editingEntityId && (
            <button onClick={cancelEditEntity} className={buttonSecondary}>Cancel</button>
          )}
          <button onClick={submitEntity} disabled={isSubmitting} className={buttonSecondary}>
            <Plus className="w-4 h-4 inline mr-1" />
            {isSubmitting ? 'Saving...' : editingEntityId ? 'Save Entity' : 'Add Entity'}
          </button>
          {!isEdit && (
            <button onClick={() => { setError(''); setCurrentStep(7); }} className={buttonPrimary}>
              Next <ChevronRight className="w-4 h-4 inline ml-1" />
            </button>
          )}
        </div>
      </div>
    </div>
  );

  const toggleEntityId = (entityId) => {
    setEventForm(p => {
      const ids = p.entity_ids.includes(entityId)
        ? p.entity_ids.filter(id => id !== entityId)
        : [...p.entity_ids, entityId];
      return { ...p, entity_ids: ids };
    });
  };

  const renderStep7 = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-800">Create Events</h3>
      <p className="text-sm text-gray-600">Define the audit criteria. You can add multiple events.</p>

      {wizardData.createdEvents.length > 0 && (
        <div className="bg-green-50 p-3 rounded-lg">
          <p className="text-sm font-semibold text-green-800 mb-2">{isEdit ? 'Events — click Edit to modify:' : 'Created Events:'}</p>
          <div className="space-y-1">
            {wizardData.createdEvents.map((evt, i) => (
              <div key={i} className="flex items-center justify-between gap-2">
                <span className="text-sm text-green-700">- {evt.name} (ID: {evt.id})</span>
                {isEdit && (
                  <button onClick={() => startEditEvent(evt)} className={`text-xs font-semibold px-2.5 py-1 rounded-full border-2 ${editingEventId === evt.id ? 'bg-purple-600 border-purple-600 text-white' : 'border-purple-200 text-purple-700 hover:bg-purple-50'}`}>
                    {editingEventId === evt.id ? 'Editing' : 'Edit'}
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelClass}>Event Name *</label>
          <input type="text" value={eventForm.name} onChange={(e) => setEventForm(p => ({ ...p, name: e.target.value }))} className={inputClass} placeholder="e.g. Prediction Correctness" />
        </div>
        <div>
          <label className={labelClass}>Categories</label>
          {categories.length > 0 ? (
            <div className="grid grid-cols-2 gap-1 max-h-40 overflow-y-auto p-2 rounded-lg border-2 border-purple-200 bg-white/80">
              {categories.map(cat => {
                const id = String(cat.id);
                const checked = eventForm.category_ids.includes(id);
                return (
                  <label key={cat.id} className="flex items-center gap-2 p-1 rounded hover:bg-purple-50 cursor-pointer text-sm">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => {
                        setEventForm(p => ({
                          ...p,
                          category_ids: checked
                            ? p.category_ids.filter(x => x !== id)
                            : [...p.category_ids, id],
                        }));
                      }}
                      className="w-4 h-4 accent-purple-600"
                    />
                    <span className="text-gray-700">{cat.event_name || cat.name} (ID: {cat.id})</span>
                  </label>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-gray-400 italic">No categories available</p>
          )}
        </div>
        <div className="col-span-2">
          <label className={labelClass}>Description *</label>
          <textarea value={eventForm.description} onChange={(e) => setEventForm(p => ({ ...p, description: e.target.value }))} className={inputClass} rows={2} />
        </div>
        <div>
          <label className={labelClass}>Cause</label>
          <input type="text" value={eventForm.cause} onChange={(e) => setEventForm(p => ({ ...p, cause: e.target.value }))} className={inputClass} />
        </div>
        <div>
          <label className={labelClass}>Reason</label>
          <input type="text" value={eventForm.reason} onChange={(e) => setEventForm(p => ({ ...p, reason: e.target.value }))} className={inputClass} />
        </div>
        <div>
          <label className={labelClass}>Likelihood</label>
          <input type="number" step="0.1" value={eventForm.likelihood} onChange={(e) => setEventForm(p => ({ ...p, likelihood: e.target.value }))} className={inputClass} />
        </div>
        <div>
          <label className={labelClass}>Magnitude</label>
          <input type="number" step="0.1" value={eventForm.magnitude} onChange={(e) => setEventForm(p => ({ ...p, magnitude: e.target.value }))} className={inputClass} />
        </div>
        <div>
          <label className={labelClass}>Valence</label>
          <input type="number" step="0.1" value={eventForm.valence} onChange={(e) => setEventForm(p => ({ ...p, valence: e.target.value }))} className={inputClass} />
        </div>
        <div>
          <label className={labelClass}>Entities</label>
          {wizardData.createdEntities.length > 0 ? (
            <div className="space-y-1">
              {wizardData.createdEntities.map(ent => (
                <label key={ent.id} className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={eventForm.entity_ids.includes(ent.id)}
                    onChange={() => toggleEntityId(ent.id)}
                    className="w-4 h-4 accent-purple-600"
                  />
                  {ent.name} (ID: {ent.id})
                </label>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400 italic">No entities created yet</p>
          )}
        </div>
      </div>
      <div className="flex justify-between pt-4">
        {!isEdit ? (
          <button onClick={() => setCurrentStep(6)} className={buttonSecondary}>
            <ChevronLeft className="w-4 h-4 inline mr-1" /> Back
          </button>
        ) : <span />}
        <div className="flex gap-2">
          {editingEventId && (
            <button onClick={cancelEditEvent} className={buttonSecondary}>Cancel</button>
          )}
          <button onClick={submitEvent} disabled={isSubmitting} className={buttonSecondary}>
            <Plus className="w-4 h-4 inline mr-1" />
            {isSubmitting ? 'Saving...' : editingEventId ? 'Save Event' : 'Add Event'}
          </button>
          {!isEdit && wizardData.createdEvents.length > 0 && (
            <button onClick={() => { setError(''); loadFeaturesForMetrics(wizardData.auditId); setCurrentStep(8); }} className={buttonPrimary}>
              Next <ChevronRight className="w-4 h-4 inline ml-1" />
            </button>
          )}
        </div>
      </div>
    </div>
  );

  const renderStep8 = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-800">Create Metrics</h3>
      <p className="text-sm text-gray-600">Define metrics for evaluating events. You can add multiple metrics.</p>

      {wizardData.createdMetrics.length > 0 && (
        <div className="bg-green-50 p-3 rounded-lg">
          <p className="text-sm font-semibold text-green-800 mb-2">{isEdit ? 'Metrics — click Edit to modify:' : 'Created Metrics:'}</p>
          <div className="space-y-1">
            {wizardData.createdMetrics.map((m, i) => (
              <div key={i} className="flex items-center justify-between gap-2">
                <span className="text-sm text-green-700">- {m.name} (ID: {m.id})</span>
                {isEdit && (
                  <button
                    onClick={() => startEditMetric(m.id)}
                    className={`text-xs font-semibold px-2.5 py-1 rounded-full border-2 ${
                      editingMetricId === m.id
                        ? 'bg-purple-600 border-purple-600 text-white'
                        : 'border-purple-200 text-purple-700 hover:bg-purple-50'
                    }`}
                  >
                    {editingMetricId === m.id ? 'Editing' : 'Edit'}
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelClass}>Metric Type</label>
          <select value={metricForm.type} onChange={(e) => setMetricForm(p => ({ ...p, type: e.target.value }))} className={inputClass}>
            <option value="quantitative">Quantitative</option>
            <option value="qualitative">Qualitative</option>
          </select>
        </div>
        <div className="col-span-2">
          <div className="flex items-center justify-between mb-2">
            <label className={labelClass}>Events * (select one or more)</label>
            {wizardData.createdEvents.length > 0 && (
              <span className="text-sm text-gray-600 bg-purple-100 px-3 py-1 rounded-full">
                {metricForm.event_ids.length} selected
              </span>
            )}
          </div>
          {wizardData.createdEvents.length > 0 ? (
            <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
              {wizardData.createdEvents.map(evt => {
                const isSelected = metricForm.event_ids.includes(String(evt.id));
                const isExpanded = expandedMetricEvents[evt.id];
                return (
                  <div
                    key={evt.id}
                    className={`border-2 rounded-2xl p-4 transition-all ${
                      isSelected
                        ? 'border-purple-300 bg-gradient-to-r from-purple-50 to-pink-50'
                        : 'border-gray-200 bg-white hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <label className="flex items-center gap-3 flex-1 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleMetricEventId(evt.id)}
                          className="w-4 h-4 text-purple-600 border-2 border-purple-200 rounded focus:ring-purple-500"
                        />
                        <span className="font-medium">{evt.name} (ID: {evt.id})</span>
                      </label>
                      <button
                        type="button"
                        onClick={() => toggleMetricEventExpand(evt.id)}
                        className="p-1 hover:bg-gray-100 rounded-full transition-colors"
                      >
                        {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
                      </button>
                    </div>

                    {isExpanded && (
                      <div className="ml-7 space-y-1 text-sm text-gray-700">
                        {evt.description && <div><strong>Description:</strong> {evt.description}</div>}
                        {evt.cause && <div><strong>Cause:</strong> {evt.cause}</div>}
                        {evt.reason && <div><strong>Why event was added:</strong> {evt.reason}</div>}
                        {evt.likelihood != null && evt.likelihood !== '' && <div><strong>Likelihood:</strong> {evt.likelihood}</div>}
                        {evt.magnitude != null && evt.magnitude !== '' && <div><strong>Magnitude:</strong> {evt.magnitude}</div>}
                        {evt.valence != null && evt.valence !== '' && <div><strong>Valence:</strong> {evt.valence}</div>}
                        {isSelected && (
                          <div className="mt-3 pt-2 border-t border-purple-200 flex items-center gap-2 text-purple-700 text-xs">
                            <span className="w-2 h-2 bg-purple-400 rounded-full"></span>
                            <span>This event will be associated with the metric</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-gray-400 italic">No events created yet</p>
          )}
        </div>
        <div>
          <label className={labelClass}>Name *</label>
          <input type="text" value={metricForm.name} onChange={(e) => setMetricForm(p => ({ ...p, name: e.target.value }))} className={inputClass} placeholder="e.g. Accuracy" />
        </div>
        <div>
          <label className={labelClass}>Threshold</label>
          <input type="text" value={metricForm.threshold} onChange={(e) => setMetricForm(p => ({ ...p, threshold: e.target.value }))} className={inputClass} placeholder={metricForm.type === 'quantitative' ? 'e.g. 70' : 'e.g. Of Worth'} />
        </div>
        <div className="col-span-2">
          <label className={labelClass}>Description</label>
          <textarea value={metricForm.description} onChange={(e) => setMetricForm(p => ({ ...p, description: e.target.value }))} className={inputClass} rows={2} />
        </div>
        <div>
          <label className={labelClass}>Reason</label>
          <input type="text" value={metricForm.reason} onChange={(e) => setMetricForm(p => ({ ...p, reason: e.target.value }))} className={inputClass} />
        </div>
        {metricForm.type === 'quantitative' ? (
          <>
            <div>
              <label className={labelClass}>Formula</label>
              <input type="text" value={metricForm.formula} onChange={(e) => setMetricForm(p => ({ ...p, formula: e.target.value }))} className={inputClass} placeholder="e.g. (correct) / (total)" />
            </div>
            <div>
              <label className={labelClass}>Target Feature</label>
              <select value={metricForm.target_feature_id} onChange={(e) => setMetricForm(p => ({ ...p, target_feature_id: e.target.value }))} className={inputClass}>
                <option value="">Select a target feature</option>
                {targetFeatures.map(tf => (
                  <option key={tf.id} value={tf.id}>{tf.name || tf.target_feature || tf.feature_name} (ID: {tf.id})</option>
                ))}
              </select>
              {metricForm.target_feature_id && (
                <input
                  type="text"
                  value={metricForm.feature_ranges[metricForm.target_feature_id] || ''}
                  onChange={(e) => setFeatureRanges(metricForm.target_feature_id, e.target.value)}
                  className={`${inputClass} mt-2`}
                  placeholder="Ranges (optional, comma-separated, e.g. 0-100, 200-300)"
                />
              )}
            </div>
            <div className="col-span-2">
              <label className={labelClass}>Distinguishing Factors</label>
              {underlyingFeatures.length > 0 ? (
                <div className="grid grid-cols-3 gap-2 mt-1">
                  {underlyingFeatures.map(uf => {
                    const checked = metricForm.underlying_feature_ids.includes(uf.id);
                    return (
                      <div key={uf.id} className="p-1.5 rounded hover:bg-purple-50">
                        <label className="flex items-center gap-2 cursor-pointer text-sm">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleUnderlyingFeatureId(uf.id)}
                            className="w-4 h-4 accent-purple-600"
                          />
                          <span className="text-gray-700">{uf.name || uf.feature_name}</span>
                        </label>
                        {checked && (
                          <input
                            type="text"
                            value={metricForm.feature_ranges[uf.id] || ''}
                            onChange={(e) => setFeatureRanges(uf.id, e.target.value)}
                            className={`${inputClass} mt-1 text-xs py-1`}
                            placeholder="Ranges (optional, e.g. 0-100)"
                          />
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-sm text-gray-400 italic mt-1">No distinguishing factors available</p>
              )}
            </div>
          </>
        ) : (
          <>
            <div>
              <label className={labelClass}>Definition</label>
              <input type="text" value={metricForm.definition} onChange={(e) => setMetricForm(p => ({ ...p, definition: e.target.value }))} className={inputClass} />
            </div>
            <div className="col-span-2">
              <label className={labelClass}>Scale Points (JSON or comma-separated labels)</label>
              <textarea value={metricForm.scale_points_text} onChange={(e) => setMetricForm(p => ({ ...p, scale_points_text: e.target.value }))} className={inputClass} rows={2} placeholder='[{"label":"Low","value":0},{"label":"High","value":1}] or Low, Medium, High' />
            </div>
          </>
        )}
      </div>
      <div className="flex justify-between pt-4">
        {!isEdit ? (
          <button onClick={() => setCurrentStep(7)} className={buttonSecondary}>
            <ChevronLeft className="w-4 h-4 inline mr-1" /> Back
          </button>
        ) : <span />}
        <div className="flex gap-2">
          {editingMetricId && (
            <button onClick={cancelEditMetric} className={buttonSecondary}>
              Cancel
            </button>
          )}
          <button onClick={submitMetric} disabled={isSubmitting} className={buttonSecondary}>
            <Plus className="w-4 h-4 inline mr-1" />
            {isSubmitting ? 'Saving...' : editingMetricId ? 'Save Metric' : 'Add Metric'}
          </button>
          {!isEdit && wizardData.createdMetrics.length > 0 && (
            <button onClick={() => { setError(''); setCurrentStep(isBlackBox ? 10 : 9); }} className={buttonPrimary}>
              Next <ChevronRight className="w-4 h-4 inline ml-1" />
            </button>
          )}
        </div>
      </div>
    </div>
  );

  const renderStep9 = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-800">Map Events to Pipeline</h3>
      <p className="text-sm text-gray-600">Select event-metric pairs to map to the audit pipeline.</p>

      {wizardData.pipelineMappings.length > 0 && (
        <div className="bg-purple-50 p-3 rounded-lg">
          <p className="text-sm font-semibold text-purple-800 mb-2">Mappings to create:</p>
          {wizardData.pipelineMappings.map((m, i) => {
            const evtName = wizardData.createdEvents.find(e => String(e.id) === String(m.event_id))?.name || m.event_id;
            const metName = wizardData.createdMetrics.find(mt => String(mt.id) === String(m.metric_id))?.name || m.metric_id;
            return (
              <div key={i} className="flex items-center justify-between text-sm text-purple-700 py-1">
                <span>{evtName} → {metName}</span>
                <button onClick={() => removePipelineMapping(i)} className="text-red-500 hover:text-red-700">
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            );
          })}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelClass}>Event</label>
          <select value={pipelineMappingForm.event_id} onChange={(e) => setPipelineMappingForm(p => ({ ...p, event_id: e.target.value }))} className={inputClass}>
            <option value="">Select an event</option>
            {wizardData.createdEvents.map(evt => (
              <option key={evt.id} value={evt.id}>{evt.name} (ID: {evt.id})</option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelClass}>Metric</label>
          <select value={pipelineMappingForm.metric_id} onChange={(e) => setPipelineMappingForm(p => ({ ...p, metric_id: e.target.value }))} className={inputClass}>
            <option value="">Select a metric</option>
            {wizardData.createdMetrics.map(m => (
              <option key={m.id} value={m.id}>{m.name} (ID: {m.id})</option>
            ))}
          </select>
        </div>
      </div>
      <button onClick={addPipelineMapping} className={buttonSecondary}>
        <Plus className="w-4 h-4 inline mr-1" /> Add Mapping
      </button>

      <div className="flex justify-between pt-4">
        <button onClick={() => setCurrentStep(8)} className={buttonSecondary}>
          <ChevronLeft className="w-4 h-4 inline mr-1" /> Back
        </button>
        <button onClick={submitPipelineMapping} disabled={isSubmitting || wizardData.pipelineMappings.length === 0} className={buttonPrimary}>
          {isSubmitting ? 'Saving...' : 'Save Mappings'}
          <ChevronRight className="w-4 h-4 inline ml-1" />
        </button>
      </div>
    </div>
  );

  const renderStep10 = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-800">Invite Auditors</h3>
      <p className="text-sm text-gray-600">Enter the email address of a registered user to invite them as an auditor. They will receive an invitation email.</p>

      {wizardData.invitedAuditors.length > 0 && (
        <div className="bg-green-50 p-3 rounded-lg">
          <p className="text-sm font-semibold text-green-800 mb-2">Invited Auditors:</p>
          {wizardData.invitedAuditors.map((a, i) => (
            <p key={i} className="text-sm text-green-700">- {a.name ? `${a.name} (${a.email})` : a.email}</p>
          ))}
        </div>
      )}

      <div>
        <label className={labelClass}>Email Address</label>
        <input
          type="email"
          value={auditorForm.email}
          onChange={(e) => setAuditorForm(p => ({ ...p, email: e.target.value }))}
          onKeyDown={(e) => e.key === 'Enter' && submitInviteAuditor()}
          className={inputClass}
          placeholder="auditor@example.com"
        />
      </div>

      <div className="flex justify-between pt-4">
        <button onClick={() => setCurrentStep(isBlackBox ? 8 : 9)} className={buttonSecondary}>
          <ChevronLeft className="w-4 h-4 inline mr-1" /> Back
        </button>
        <div className="flex gap-2">
          <button onClick={submitInviteAuditor} disabled={isSubmitting || !auditorForm.email} className={buttonSecondary}>
            <Plus className="w-4 h-4 inline mr-1" />
            {isSubmitting ? 'Inviting...' : 'Invite Auditor'}
          </button>
          <button onClick={() => navigate(tenantPath('/admin'))} className={buttonPrimary}>
            Finish Setup <Check className="w-4 h-4 inline ml-1" />
          </button>
        </div>
      </div>
    </div>
  );

  const renderCurrentStep = () => {
    switch (currentStep) {
      case 1: return (
        <AuditInfoPage
          auditForm={auditForm}
          setAuditForm={setAuditForm}
          submitAuditInfo={submitAuditInfo}
          isSubmitting={isSubmitting}
          isEdit={isEdit}
        />
      );
      case 2: return (
        <ApplicationPage
          applicationForm={applicationForm}
          setApplicationForm={setApplicationForm}
          submitApplication={submitApplication}
          isSubmitting={isSubmitting}
          onBack={() => setCurrentStep(1)}
          isEdit={isEdit}
        />
      );
      case 3: return renderStep2();
      case 4: return renderStep3();
      case 5: return renderStep4();
      case '5b': return renderStep4b();
      case '5c': return renderStep4c();
      case '5d': return renderStep4d();
      case '5e': return renderStep5e();
      case 6: return renderStep6();
      case 7: return renderStep7();
      case 8: return renderStep8();
      case 9: return renderStep9();
      case 10: return renderStep10();
      default: return renderStepAuditInfo();
    }
  };

  return (
    <div className="bg-purple-to-br from-purple-50 to-pink-50 p-4">
      <Navigation currentPage="profile" onNavigate={handleNavigation} />

      <div className="w-full mx-auto">
        <div className="flex items-center mb-6">
          <Settings className="w-5 h-5 mr-2 text-gray-700" />
          <h2 className="text-xl font-semibold text-gray-800">{isEdit ? 'Edit Audit' : 'Audit Setup Wizard'}</h2>
        </div>

        <div className="flex flex-col lg:flex-row gap-6 items-start">
          {/* Left rail: progress */}
          <aside className="w-full lg:w-72 shrink-0 bg-white rounded-3xl border-2 border-purple-100 p-4 shadow-sm lg:sticky lg:top-4">
            <ProgressNav
              steps={STEPS}
              currentStep={currentStep}
              stepOrder={stepOrder}
              skippedIds={isBlackBox ? blackBoxSkipStepIds : new Set()}
              onSelect={setCurrentStep}
              allowAll={isEdit}
            />
          </aside>

          {/* Content card */}
          <div className="flex-1 min-w-0 bg-white rounded-3xl border-2 border-purple-100 p-6 shadow-sm">
            {error && (
              <div className="mb-4 bg-red-50 border border-red-200 text-red-700 p-3 rounded-lg flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span className="text-sm">{error}</span>
                <button onClick={() => setError('')} className="ml-auto text-red-500 hover:text-red-700 text-sm">Dismiss</button>
              </div>
            )}

            {isEdit && editLoading ? (
              <p className="text-sm text-gray-500 py-12 text-center">Loading audit for editing…</p>
            ) : (
              renderCurrentStep()
            )}

            <div className="mt-8 text-right">
              <span className="text-purple-600 font-bold text-sm">PHAWM</span>
            </div>
          </div>
        </div>
      </div>

      {successMessage && (
        <div className="fixed top-4 right-4 bg-green-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 animate-fade-in">
          <div className="flex items-center gap-2">
            <Check className="w-5 h-5" />
            <span className="font-semibold">{successMessage}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminPanel;
