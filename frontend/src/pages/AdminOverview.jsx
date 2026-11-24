import { useState, useEffect, useRef, Fragment } from 'react';
import { Navigation } from '../components/navigation/Navigation';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../components/auth/AuthContext';
import { tenantPath, resolveTenantId } from '../utils/tenant';
import { adminAPI, AUDIT_STATUS, getAccessTypeLabel } from '../api/apiService';
import { Settings, Plus, Trash2, Eye, AlertCircle, Loader2, ChevronDown, ChevronUp, ChevronRight, UserPlus, X, FileText, Download, Search, Pencil } from 'lucide-react';

// Code → human label maps for audit result fields
const STATUS_LABELS = { 0: 'Not started', 1: 'In Progress', 2: 'Finished' };
const RECOMMENDATION_LABELS = { 0: 'Not Evaluated', 1: 'Inconclusive', 2: 'Fail', 3: 'Pass' };
const MEET_REQUIREMENT_LABELS = { 0: 'Maybe', 1: 'No', 2: 'Yes' };
const codeLabel = (map, val) => (val == null ? '—' : (map[val] ?? 'Unknown'));
// Plain enum label for CSV export (empty string when absent)
const plainLabel = (map, val) => (val == null ? '' : (map[val] ?? 'Unknown'));
const formatDuration = (secs) => {
  if (secs == null) return '—';
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
};
// Duration in minutes (2 dp) for CSV export
const durationMinutes = (secs) => (secs == null ? '' : (secs / 60).toFixed(2));
// The threshold actually applied: the customised one when set, otherwise the base
const effectiveThreshold = (c) =>
  (c?.is_threshold_customised && c?.custom_threshold != null ? c.custom_threshold : c?.metric_threshold);
// The effective value of an event factor: the customised override when set, else the base
const effectiveFactor = (event, key) => {
  const custom = event?.[`custom_${key}`];
  return custom != null ? custom : event?.[key];
};

const AdminOverview = () => {
  const navigate = useNavigate();
  useAuth();

  const [audits, setAudits] = useState([]);
  const [models, setModels] = useState([]);
  const [datasets, setDatasets] = useState([]);
  const [mcpStatuses, setMcpStatuses] = useState({}); // { [modelId]: 'online'|'offline'|'loading' }
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState(null); // { type: 'audit'|'model'|'dataset', id: ... }
  const [expandedSection, setExpandedSection] = useState('audits');
  const [inviteModal, setInviteModal] = useState(null); // { auditId, auditName }
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteStatus, setInviteStatus] = useState(null); // null | 'loading' | 'success' | { error: string }
  const inviteInputRef = useRef(null);
  const [resultsModal, setResultsModal] = useState(null); // { auditId, auditName }
  const [resultsData, setResultsData] = useState([]);
  const [resultsStatus, setResultsStatus] = useState(null); // null | 'loading' | { error: string }
  const [resultsFilters, setResultsFilters] = useState({ search: '', status: '', recommendation: '', requirement: '' });
  const [expandedCriteria, setExpandedCriteria] = useState({}); // { [`${user_audit_id}-${ci}`]: true }

  const toggleCriterion = (key) =>
    setExpandedCriteria(prev => ({ ...prev, [key]: !prev[key] }));

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError('');
    try {
      const [auditsResponse, modelsResponse, datasetsResponse] = await Promise.all([
        adminAPI.getAudits(),
        adminAPI.getModels(),
        adminAPI.getDatasets().catch(() => []),
      ]);
      const auditsList = auditsResponse.audits || auditsResponse || [];
      setAudits(Array.isArray(auditsList) ? auditsList : []);
      const modelsList = Array.isArray(modelsResponse) ? modelsResponse : modelsResponse.models || [];
      setModels(modelsList);
      const datasetsList = Array.isArray(datasetsResponse) ? datasetsResponse : datasetsResponse.datasets || datasetsResponse.results || [];
      setDatasets(datasetsList);

      // Fetch MCP status for each model that has a location
      const statuses = {};
      await Promise.all(
        modelsList.map(async (model) => {
          if (!model.location) { statuses[model.id] = null; return; }
          statuses[model.id] = 'loading';
          try {
            const s = await adminAPI.getMcpStatus(model.id);
            statuses[model.id] = s.status;
          } catch {
            statuses[model.id] = 'offline';
          }
        })
      );
      setMcpStatuses(statuses);
    } catch (err) {
      setError(err.message || 'Failed to load data');
    }
    setLoading(false);
  };

  const handleDeleteAudit = async (auditId) => {
    try {
      await adminAPI.deleteAudit(auditId);
      setAudits(prev => prev.filter(a => a.id !== auditId));
      setDeleteConfirm(null);
    } catch (err) {
      setError(err.message || 'Failed to delete audit');
      setDeleteConfirm(null);
    }
  };

  const handleDeleteModel = async (modelId) => {
    try {
      await adminAPI.deleteModel(modelId);
      setModels(prev => prev.filter(m => m.id !== modelId));
      setDeleteConfirm(null);
    } catch (err) {
      setError(err.message || 'Failed to delete model');
      setDeleteConfirm(null);
    }
  };

  const handleDeleteDataset = async (datasetId) => {
    try {
      await adminAPI.deleteDataset(datasetId);
      setDatasets(prev => prev.filter(d => d.id !== datasetId));
      setDeleteConfirm(null);
    } catch (err) {
      setError(err.message || 'Failed to delete dataset');
      setDeleteConfirm(null);
    }
  };

  const openInviteModal = (audit) => {
    setInviteModal({ auditId: audit.id, auditName: audit.name });
    setInviteEmail('');
    setInviteStatus(null);
    // Focus the input after the modal renders
    setTimeout(() => inviteInputRef.current?.focus(), 50);
  };

  const closeInviteModal = () => {
    setInviteModal(null);
    setInviteEmail('');
    setInviteStatus(null);
  };

  const handleInviteSubmit = async (e) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    setInviteStatus('loading');
    try {
      await adminAPI.inviteAuditor(inviteModal.auditId, inviteEmail.trim());
      setInviteStatus('success');
      setInviteEmail('');
    } catch (err) {
      setInviteStatus({ error: err.message || 'Failed to send invitation' });
    }
  };

  const openResultsModal = async (audit) => {
    setResultsModal({ auditId: audit.id, auditName: audit.name });
    setResultsData([]);
    setResultsFilters({ search: '', status: '', recommendation: '', requirement: '' });
    setExpandedCriteria({});
    setResultsStatus('loading');
    try {
      const data = await adminAPI.getAuditResults(audit.id);
      const list = Array.isArray(data) ? data : (data ? [data] : []);
      setResultsData(list);
      setResultsStatus(null);
    } catch (err) {
      setResultsStatus({ error: err.message || 'Failed to load audit results' });
    }
  };

  const closeResultsModal = () => {
    setResultsModal(null);
    setResultsData([]);
    setResultsStatus(null);
  };

  // Apply the active result filters: narrows auditors (search/status/recommendation)
  // and their criteria (requirement). Returns a new audits array.
  const applyResultsFilters = (auditsList) => {
    const { search, status, recommendation, requirement } = resultsFilters;
    const term = search.trim().toLowerCase();
    return (auditsList || []).map(audit => {
      const auditors = (audit.auditors || []).filter(auditor => {
        if (term) {
          const haystack = `${auditor.full_name || ''} ${auditor.email || ''}`.toLowerCase();
          if (!haystack.includes(term)) return false;
        }
        if (status !== '' && String(auditor.audit_recommendation?.status) !== status) return false;
        if (recommendation !== '' && String(auditor.audit_recommendation?.recommendation) !== recommendation) return false;
        return true;
      });
      const withCriteria = requirement === ''
        ? auditors
        : auditors
            .map(auditor => ({
              ...auditor,
              audit_criteria: (auditor.audit_criteria || []).filter(
                c => String(c.outcome_meet_requirement) === requirement
              ),
            }))
            // Drop auditors left with no matching criteria under this filter
            .filter(auditor => auditor.audit_criteria.length > 0);
      return { ...audit, auditors: withCriteria };
    });
  };

  // Flatten audit results into one row per (auditor, criterion) for CSV export
  const flattenAuditResultRows = (auditsList) => {
    const rows = [];
    (auditsList || []).forEach(audit => {
      (audit.auditors || []).forEach(auditor => {
        const base = {
          audit_id: audit.audit_id,
          audit_name: audit.audit_name,
          user_audit_id: auditor.user_audit_id,
          email: auditor.email,
          full_name: auditor.full_name,
          role: auditor.role,
          submitted_at: auditor.submitted_at,
          duration_minutes: durationMinutes(auditor.duration_seconds),
          overall_status: plainLabel(STATUS_LABELS, auditor.audit_recommendation?.status),
          overall_recommendation: plainLabel(RECOMMENDATION_LABELS, auditor.audit_recommendation?.recommendation),
          overall_notes: auditor.audit_recommendation?.notes,
        };
        const criteria = auditor.audit_criteria || [];
        if (criteria.length === 0) {
          rows.push({ ...base });
        } else {
          criteria.forEach(c => {
            rows.push({
              ...base,
              event_id: c.event?.id,
              event_name: c.event?.name,
              event_description: c.event?.description,
              event_cause: c.event?.cause,
              event_reason: c.event?.reason,
              event_categories: (c.event?.categories || []).map(cat => cat.name).join('; '),
              event_customised: c.event?.is_customised ? 'Yes' : 'No',
              likelihood: effectiveFactor(c.event, 'likelihood'),
              magnitude: effectiveFactor(c.event, 'magnitude'),
              valence: effectiveFactor(c.event, 'valence'),
              metric_id: c.metric?.id,
              metric_name: c.metric?.name,
              metric_type: c.metric?.metric_type,
              metric_description: c.metric?.description,
              metric_reason: c.metric?.reason,
              metric_formula: c.metric?.formula,
              metric_definition: c.metric?.definition,
              recommendation: plainLabel(RECOMMENDATION_LABELS, c.recommendation),
              status: plainLabel(STATUS_LABELS, c.status),
              audit_status_notes: c.audit_status_notes,
              metric_result_output: c.metric_result_output != null ? JSON.stringify(c.metric_result_output) : '',
              metric_threshold: c.metric_threshold,
              custom_threshold: c.custom_threshold,
              threshold_used: effectiveThreshold(c),
              outcome_meet_requirement: plainLabel(MEET_REQUIREMENT_LABELS, c.outcome_meet_requirement),
              outcome_output: c.outcome_output != null ? JSON.stringify(c.outcome_output) : '',
              outcome_notes: c.outcome_notes,
            });
          });
        }
      });
    });
    return rows;
  };

  const exportResultsCsv = () => {
    const rows = flattenAuditResultRows(applyResultsFilters(resultsData));
    if (rows.length === 0) return;
    const headers = [
      'audit_id', 'audit_name', 'user_audit_id', 'email', 'full_name', 'role',
      'submitted_at', 'duration_minutes', 'event_id', 'event_name',
      'event_description', 'event_cause', 'event_reason', 'event_categories', 'event_customised',
      'likelihood', 'magnitude', 'valence', 'metric_id',
      'metric_name', 'metric_type', 'metric_description', 'metric_reason',
      'metric_formula', 'metric_definition', 'recommendation', 'status', 'audit_status_notes',
      'metric_result_output', 'metric_threshold', 'custom_threshold', 'threshold_used',
      'outcome_meet_requirement', 'outcome_output', 'outcome_notes',
      'overall_status', 'overall_recommendation', 'overall_notes',
    ];
    const escape = (val) => {
      if (val == null) return '';
      const str = String(val);
      return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str;
    };
    const csv = [
      headers.join(','),
      ...rows.map(r => headers.map(h => escape(r[h])).join(',')),
    ].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const tenantId = resolveTenantId() || 'tenant';
    link.download = `${tenantId}-audit-${resultsModal.auditId}-results.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleNavigation = (pageId) => {
    if (pageId === 'dashboard') navigate(tenantPath('/dashboard'));
    if (pageId === 'profile') navigate(tenantPath('/profile'));
  };

  const getStatusLabel = (status) => AUDIT_STATUS[status] || 'Unknown';

  const getStatusColor = (statusText) => {
    if (statusText === 'Submitted' || statusText === 'Finished') return 'bg-green-100 text-green-800';
    if (statusText === 'In Progress') return 'bg-yellow-100 text-yellow-800';
    return 'bg-gray-100 text-gray-600';
  };

  const buttonPrimary = "flex items-center gap-2 bg-purple-100 hover:bg-purple-200 px-4 py-3 rounded-full text-base font-semibold transition-colors border-2 border-purple-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-purple-100";
  const buttonSecondary = "bg-purple-100 hover:bg-purple-200 px-4 py-2 rounded-full text-sm font-semibold border-2 border-purple-200 transition-colors";

  if (loading) {
    return (
      <div className="min-h-screen bg-purple-to-br from-purple-50 to-pink-50 p-4">
        <Navigation currentPage="admin" onNavigate={handleNavigation} />
        <div className="flex items-center justify-center mt-20">
          <Loader2 className="w-8 h-8 animate-spin text-purple-600" />
          <span className="ml-3 text-gray-600">Loading admin overview...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-purple-to-br from-purple-50 to-pink-50 p-4">
      <Navigation currentPage="admin" onNavigate={handleNavigation} />

      {/* Purpose Box */}
      <div className="mb-6 bg-b7efff rounded-2xl border-2 border-purple-300 p-6 shadow-md">
        <p className="text-gray-700">
          This is the Admin Overview. Here you can see all audits, models, and applications you manage.
          Use the <strong>Create New Audit</strong> button to set up a new audit using the step-by-step wizard.
        </p>
      </div>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 p-3 rounded-lg flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span className="text-sm">{error}</span>
          <button onClick={() => setError('')} className="ml-auto text-red-500 hover:text-red-700 text-sm">Dismiss</button>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center">
          <Settings className="w-5 h-5 mr-2 text-gray-700" />
          <h2 className="text-xl font-semibold text-gray-800">Admin Overview</h2>
        </div>
        <button onClick={() => navigate(tenantPath('/admin/create'))} className={buttonPrimary}>
          <Plus className="w-4 h-4" />
          
          Create New Audit
        </button>
      </div>

      {/* Audits Section */}
      <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg mb-6">
        <div
          className="flex items-center justify-between cursor-pointer"
          onClick={() => setExpandedSection(expandedSection === 'audits' ? '' : 'audits')}
        >
          <h3 className="text-lg font-semibold text-gray-800">
            Audits ({audits.length})
          </h3>
          {expandedSection === 'audits' ? (
            <ChevronUp className="w-5 h-5 text-gray-500" />
          ) : (
            <ChevronDown className="w-5 h-5 text-gray-500" />
          )}
        </div>

        {expandedSection === 'audits' && (
          <div className="space-y-4 mt-4">
            {audits.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <p>No audits found. Create your first audit to get started.</p>
              </div>
            ) : (
              audits.map((audit) => (
                <div
                  key={audit.id}
                  className="flex items-center justify-between p-5 rounded-2xl border-2 border-purple-200 bg-gradient-to-r from-purple-50 to-pink-50 shadow-lg"
                >
                  <div className="flex-1">
                    <div className="font-medium text-gray-800">{audit.name}</div>
                    <div className="text-sm text-gray-500 mt-1">
                      {audit.audit_instigator && `${audit.audit_instigator} · `}
                      {audit.application_organisation || 'No organisation'}
                    </div>
                  </div>

                  <div className="flex-1">
                    <div className="text-sm font-medium text-gray-700">Application</div>
                    <div className="text-sm text-gray-500">{audit.application_name || 'N/A'}</div>
                  </div>

                  <div className="flex-1">
                    <div className="text-sm font-medium text-gray-700">Access Type</div>
                    <div className="text-sm text-gray-500">{getAccessTypeLabel(audit.access_type)}</div>
                  </div>

                  <div className="flex-1">
                    <div className="text-sm font-medium text-gray-700">Status</div>
                    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${getStatusColor(audit.status_text)}`}>
                      {audit.status_text || getStatusLabel(audit.status)}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => navigate(tenantPath(`/ai-application/${audit.id}`))}
                      className={buttonSecondary}
                      title="View audit"
                    >
                      <Eye className="w-4 h-4 inline mr-1" />
                      View
                    </button>

                    <button
                      onClick={() => openInviteModal(audit)}
                      className={buttonSecondary}
                      title="Invite auditor"
                    >
                      <UserPlus className="w-4 h-4 inline mr-1" />
                      Invite
                    </button>

                    <button
                      onClick={() => openResultsModal(audit)}
                      className={buttonSecondary}
                      title="View auditor results"
                    >
                      <FileText className="w-4 h-4 inline mr-1" />
                      Results
                    </button>

                    <button
                      onClick={() => navigate(tenantPath(`/admin/edit/${audit.id}`))}
                      className={buttonSecondary}
                      title="Edit this audit's setup"
                    >
                      <Pencil className="w-4 h-4 inline mr-1" />
                      Edit
                    </button>

                    {deleteConfirm?.type === 'audit' && deleteConfirm?.id === audit.id ? (
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-red-600 font-medium">Delete?</span>
                        <button
                          onClick={() => handleDeleteAudit(audit.id)}
                          className="text-red-600 hover:text-red-800 text-xs font-semibold px-2 py-1 border border-red-300 rounded-full"
                        >
                          Yes
                        </button>
                        <button
                          onClick={() => setDeleteConfirm(null)}
                          className="text-gray-500 hover:text-gray-700 text-xs font-semibold px-2 py-1 border border-gray-300 rounded-full"
                        >
                          No
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setDeleteConfirm({ type: 'audit', id: audit.id })}
                        className="text-red-400 hover:text-red-600 p-2 rounded-full hover:bg-red-50 transition-colors"
                        title="Delete audit"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Models Section */}
      <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg mb-6">
        <div
          className="flex items-center justify-between cursor-pointer"
          onClick={() => setExpandedSection(expandedSection === 'models' ? '' : 'models')}
        >
          <h3 className="text-lg font-semibold text-gray-800">
            Models ({models.length})
          </h3>
          {expandedSection === 'models' ? (
            <ChevronUp className="w-5 h-5 text-gray-500" />
          ) : (
            <ChevronDown className="w-5 h-5 text-gray-500" />
          )}
        </div>

        {expandedSection === 'models' && (
          <div className="space-y-3 mt-4">
            {models.length === 0 ? (
              <div className="text-center py-6 text-gray-500">
                <p>No models found. Models are created as part of the audit setup wizard.</p>
              </div>
            ) : (
              models.map((model) => (
                <div
                  key={model.id}
                  className="flex items-center justify-between p-4 rounded-2xl border-2 border-purple-200 bg-gradient-to-r from-purple-50 to-pink-50"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-800">{model.name}</span>
                      {mcpStatuses[model.id] === 'online' && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                          <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
                          MCP Online
                        </span>
                      )}
                      {mcpStatuses[model.id] === 'offline' && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
                          <span className="w-1.5 h-1.5 rounded-full bg-red-500 inline-block" />
                          MCP Offline
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-gray-500">
                      {model.model_type === 1 || model.model_type === true ? 'Generative AI' : 'Predictive AI'}
                      {model.task && ` · ${model.task}`}
                      {model.mcp_tool_name && ` · ${model.mcp_tool_name}`}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {deleteConfirm?.type === 'model' && deleteConfirm?.id === model.id ? (
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-red-600 font-medium">Delete?</span>
                        <button
                          onClick={() => handleDeleteModel(model.id)}
                          className="text-red-600 hover:text-red-800 text-xs font-semibold px-2 py-1 border border-red-300 rounded-full"
                        >
                          Yes
                        </button>
                        <button
                          onClick={() => setDeleteConfirm(null)}
                          className="text-gray-500 hover:text-gray-700 text-xs font-semibold px-2 py-1 border border-gray-300 rounded-full"
                        >
                          No
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setDeleteConfirm({ type: 'model', id: model.id })}
                        className="text-red-400 hover:text-red-600 p-2 rounded-full hover:bg-red-50 transition-colors"
                        title="Delete model"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Datasets Section */}
      <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg mb-6">
        <div
          className="flex items-center justify-between cursor-pointer"
          onClick={() => setExpandedSection(expandedSection === 'datasets' ? '' : 'datasets')}
        >
          <h3 className="text-lg font-semibold text-gray-800">
            Datasets ({datasets.length})
          </h3>
          {expandedSection === 'datasets' ? (
            <ChevronUp className="w-5 h-5 text-gray-500" />
          ) : (
            <ChevronDown className="w-5 h-5 text-gray-500" />
          )}
        </div>

        {expandedSection === 'datasets' && (
          <div className="space-y-3 mt-4">
            {datasets.length === 0 ? (
              <div className="text-center py-6 text-gray-500">
                <p>No datasets found. Datasets are created as part of the audit setup wizard.</p>
              </div>
            ) : (
              datasets.map((dataset) => (
                <div
                  key={dataset.id}
                  className="flex items-center justify-between p-4 rounded-2xl border-2 border-purple-200 bg-gradient-to-r from-purple-50 to-pink-50"
                >
                  <div className="flex-1">
                    <div className="font-medium text-gray-800">{dataset.purpose || dataset.name || `Dataset ${dataset.id}`}</div>
                    <div className="text-sm text-gray-500">
                      ID: {dataset.id}
                      {dataset.location && ` · ${dataset.location}`}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {deleteConfirm?.type === 'dataset' && deleteConfirm?.id === dataset.id ? (
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-red-600 font-medium">Delete?</span>
                        <button
                          onClick={() => handleDeleteDataset(dataset.id)}
                          className="text-red-600 hover:text-red-800 text-xs font-semibold px-2 py-1 border border-red-300 rounded-full"
                        >
                          Yes
                        </button>
                        <button
                          onClick={() => setDeleteConfirm(null)}
                          className="text-gray-500 hover:text-gray-700 text-xs font-semibold px-2 py-1 border border-gray-300 rounded-full"
                        >
                          No
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setDeleteConfirm({ type: 'dataset', id: dataset.id })}
                        className="text-red-400 hover:text-red-600 p-2 rounded-full hover:bg-red-50 transition-colors"
                        title="Delete dataset"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Applications Section (derived from audits) */}
      {(() => {
        const uniqueApps = [];
        const seen = new Set();
        audits.forEach(a => {
          if (a.application_name && !seen.has(a.application_name)) {
            seen.add(a.application_name);
            uniqueApps.push({
              name: a.application_name,
              organisation: a.application_organisation,
              accessType: a.access_type,
            });
          }
        });
        return (
          <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg mb-6">
            <div
              className="flex items-center justify-between cursor-pointer"
              onClick={() => setExpandedSection(expandedSection === 'apps' ? '' : 'apps')}
            >
              <h3 className="text-lg font-semibold text-gray-800">
                Applications ({uniqueApps.length})
              </h3>
              {expandedSection === 'apps' ? (
                <ChevronUp className="w-5 h-5 text-gray-500" />
              ) : (
                <ChevronDown className="w-5 h-5 text-gray-500" />
              )}
            </div>

            {expandedSection === 'apps' && (
              <div className="space-y-3 mt-4">
                {uniqueApps.length === 0 ? (
                  <div className="text-center py-6 text-gray-500">
                    <p>No applications found. Applications are created as part of the audit setup wizard.</p>
                  </div>
                ) : (
                  uniqueApps.map((app, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between p-4 rounded-2xl border-2 border-purple-200 bg-gradient-to-r from-purple-50 to-pink-50"
                    >
                      <div className="flex-1">
                        <div className="font-medium text-gray-800">{app.name}</div>
                        <div className="text-sm text-gray-500">{app.organisation || 'No organisation'}</div>
                      </div>
                      <div className="text-sm text-gray-500">
                        {getAccessTypeLabel(app.accessType)}
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        );
      })()}

      <div className="mt-8 text-right">
        <span className="text-purple-600 font-bold text-sm">PHAWM</span>
      </div>

      {/* Invite Auditor Modal */}
      {inviteModal && (
        <div
          className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
          onClick={(e) => { if (e.target === e.currentTarget) closeInviteModal(); }}
        >
          <div className="bg-purple rounded-3xl border-2 border-purple-200 p-8 shadow-xl w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-gray-800">
                Invite Auditor
              </h2>
              <button
                onClick={closeInviteModal}
                className="text-gray-400 hover:text-gray-600 p-1 rounded-full hover:bg-purple-100 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-sm text-gray-600 mb-6">
              Send an invitation email to an auditor for <strong>{inviteModal.auditName}</strong>.
              If the user doesn't have an account yet, they'll receive a link to set one up.
            </p>

            {inviteStatus === 'success' ? (
              <div className="text-center py-4">
                <div className="text-green-600 text-4xl mb-3">✓</div>
                <p className="font-semibold text-gray-800 mb-1">Invitation sent!</p>
                <p className="text-sm text-gray-500 mb-6">The auditor will receive an email shortly.</p>
                <div className="flex gap-3 justify-center">
                  <button
                    onClick={() => { setInviteStatus(null); setInviteEmail(''); setTimeout(() => inviteInputRef.current?.focus(), 50); }}
                    className={buttonSecondary}
                  >
                    Invite another
                  </button>
                  <button onClick={closeInviteModal} className={buttonSecondary}>
                    Done
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleInviteSubmit}>
                <div className="mb-4">
                  <input
                    ref={inviteInputRef}
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => { setInviteEmail(e.target.value); setInviteStatus(null); }}
                    placeholder="auditor@example.com"
                    required
                    disabled={inviteStatus === 'loading'}
                    className="w-full bg-purple text-center px-4 py-3 border-2 border-purple-200 rounded-full focus:border-purple-400 focus:outline-none transition-colors disabled:opacity-50"
                  />
                </div>

                {inviteStatus?.error && (
                  <div className="mb-4 flex items-center gap-2 text-red-600 text-sm bg-red-50 border border-red-200 px-4 py-2 rounded-full">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    {inviteStatus.error}
                  </div>
                )}

                <div className="flex gap-3 justify-center">
                  <button
                    type="button"
                    onClick={closeInviteModal}
                    className={buttonSecondary}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={inviteStatus === 'loading' || !inviteEmail.trim()}
                    className="flex items-center gap-2 bg-purple-100 hover:bg-purple-200 px-6 py-2 rounded-full text-base font-semibold transition-colors border-2 border-purple-200 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {inviteStatus === 'loading' ? (
                      <><Loader2 className="w-4 h-4 animate-spin" /> Sending...</>
                    ) : (
                      <><UserPlus className="w-4 h-4" /> Send Invite</>
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Auditor Results Modal */}
      {resultsModal && (
        <div
          className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
          onClick={(e) => { if (e.target === e.currentTarget) closeResultsModal(); }}
        >
          <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-xl w-full max-w-6xl mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
              <h2 className="text-lg font-semibold text-gray-800">
                Auditor Results — {resultsModal.auditName}
              </h2>
              <div className="flex items-center gap-2">
                <button
                  onClick={exportResultsCsv}
                  disabled={resultsData.length === 0}
                  className={`${buttonSecondary} disabled:opacity-50 disabled:cursor-not-allowed`}
                  title="Export results as CSV"
                >
                  <Download className="w-4 h-4 inline mr-1" />
                  Export CSV
                </button>
                <button
                  onClick={closeResultsModal}
                  className="text-gray-400 hover:text-gray-600 p-1 rounded-full hover:bg-purple-100 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {resultsStatus === 'loading' && (
              <div className="flex items-center justify-center py-12 text-gray-600">
                <Loader2 className="w-6 h-6 animate-spin text-purple-600" />
                <span className="ml-3">Loading auditor results...</span>
              </div>
            )}

            {resultsStatus?.error && (
              <div className="my-4 flex items-center gap-2 text-red-600 text-sm bg-red-50 border border-red-200 px-4 py-3 rounded-lg">
                <AlertCircle className="w-4 h-4 shrink-0" />
                {resultsStatus.error}
              </div>
            )}

            {resultsStatus === null && (() => {
              const hasAnyAuditor = resultsData.some(a => (a.auditors || []).length > 0);
              const filtered = applyResultsFilters(resultsData);
              const hasMatches = filtered.some(a => (a.auditors || []).length > 0);
              const filtersActive = resultsFilters.search || resultsFilters.status || resultsFilters.recommendation || resultsFilters.requirement;
              return (
              <>
                {hasAnyAuditor && (
                  <div className="flex flex-wrap items-center gap-2 mb-4 bg-purple-50/60 border border-purple-100 rounded-xl p-3">
                    <div className="relative flex-1 min-w-[180px]">
                      <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                      <input
                        type="text"
                        value={resultsFilters.search}
                        onChange={(e) => setResultsFilters(f => ({ ...f, search: e.target.value }))}
                        placeholder="Search auditor name or email"
                        className="w-full text-sm pl-9 pr-3 py-2 bg-white border border-purple-200 rounded-lg focus:border-purple-400 focus:outline-none"
                      />
                    </div>
                    <select
                      value={resultsFilters.status}
                      onChange={(e) => setResultsFilters(f => ({ ...f, status: e.target.value }))}
                      className="text-sm px-3 py-2 bg-white border border-purple-200 rounded-lg focus:border-purple-400 focus:outline-none"
                    >
                      <option value="">All statuses</option>
                      {Object.entries(STATUS_LABELS).map(([v, label]) => (
                        <option key={v} value={v}>{label}</option>
                      ))}
                    </select>
                    <select
                      value={resultsFilters.recommendation}
                      onChange={(e) => setResultsFilters(f => ({ ...f, recommendation: e.target.value }))}
                      className="text-sm px-3 py-2 bg-white border border-purple-200 rounded-lg focus:border-purple-400 focus:outline-none"
                    >
                      <option value="">All recommendations</option>
                      {Object.entries(RECOMMENDATION_LABELS).map(([v, label]) => (
                        <option key={v} value={v}>{label}</option>
                      ))}
                    </select>
                    <select
                      value={resultsFilters.requirement}
                      onChange={(e) => setResultsFilters(f => ({ ...f, requirement: e.target.value }))}
                      className="text-sm px-3 py-2 bg-white border border-purple-200 rounded-lg focus:border-purple-400 focus:outline-none"
                    >
                      <option value="">All requirements</option>
                      {Object.entries(MEET_REQUIREMENT_LABELS).map(([v, label]) => (
                        <option key={v} value={v}>{label}</option>
                      ))}
                    </select>
                    {filtersActive && (
                      <button
                        onClick={() => setResultsFilters({ search: '', status: '', recommendation: '', requirement: '' })}
                        className="text-sm px-3 py-2 text-purple-700 hover:text-purple-900 hover:bg-purple-100 rounded-lg transition-colors flex items-center gap-1"
                      >
                        <X className="w-4 h-4" /> Clear
                      </button>
                    )}
                  </div>
                )}

                {!hasAnyAuditor ? (
                  <div className="text-center py-12 text-gray-500">
                    <p>No auditor results found for this audit yet.</p>
                  </div>
                ) : !hasMatches ? (
                  <div className="text-center py-12 text-gray-500">
                    <p>No auditors match the current filters.</p>
                  </div>
                ) : (
                  filtered.map((audit) => (
                    <div key={audit.audit_id} className="mb-4">
                      {(audit.auditors || []).map((auditor) => (
                        <div key={auditor.user_audit_id} className="bg-white/70 border-2 border-purple-100 rounded-2xl p-4 mb-3">
                          <div className="flex items-center justify-between flex-wrap gap-x-4 gap-y-1 mb-3">
                            <div className="flex items-baseline gap-2">
                              <span className="text-sm font-semibold text-gray-800">{auditor.full_name || auditor.email}</span>
                              <span className="text-xs text-gray-500">{auditor.email} · {auditor.role}</span>
                            </div>
                            <div className="flex items-center gap-x-4 gap-y-1 flex-wrap text-xs text-gray-600">
                              <span>Status: {codeLabel(STATUS_LABELS, auditor.audit_recommendation?.status)}</span>
                              <span>Overall: {codeLabel(RECOMMENDATION_LABELS, auditor.audit_recommendation?.recommendation)}</span>
                              <span>Submitted: {auditor.submitted_at ? new Date(auditor.submitted_at).toLocaleString() : '—'}</span>
                              <span>Duration: {formatDuration(auditor.duration_seconds)}</span>
                            </div>
                          </div>

                          {(auditor.audit_criteria || []).length > 0 ? (
                            <div className="overflow-x-auto">
                              <table className="w-full text-xs border-collapse">
                                <thead>
                                  <tr className="bg-purple-50 text-left text-gray-700">
                                    <th className="p-2 font-semibold w-6"></th>
                                    <th className="p-2 font-semibold">Event</th>
                                    <th className="p-2 font-semibold">Metric</th>
                                    <th className="p-2 font-semibold">Status</th>
                                    <th className="p-2 font-semibold">Recommendation</th>
                                    <th className="p-2 font-semibold">Result</th>
                                    <th className="p-2 font-semibold">Threshold</th>
                                    <th className="p-2 font-semibold">Requirement</th>
                                    <th className="p-2 font-semibold">Outcome</th>
                                    <th className="p-2 font-semibold">Notes</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {auditor.audit_criteria.map((c, ci) => {
                                    const rowKey = `${auditor.user_audit_id}-${ci}`;
                                    const isExpanded = !!expandedCriteria[rowKey];
                                    return (
                                    <Fragment key={rowKey}>
                                    <tr
                                      className="border-b border-purple-100 align-top text-gray-700 cursor-pointer hover:bg-purple-50/50"
                                      onClick={() => toggleCriterion(rowKey)}
                                    >
                                      <td className="p-2 text-gray-400">
                                        {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                                      </td>
                                      <td className="p-2">
                                        <span>{c.event?.name ?? '—'}</span>
                                        {c.event?.is_customised && (
                                          <span className="ml-1 inline-block px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-amber-100 text-amber-700">customised</span>
                                        )}
                                        {c.event && (
                                          <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1 text-[10px] text-gray-500">
                                            {[['L', 'likelihood'], ['M', 'magnitude'], ['V', 'valence']].map(([abbr, key]) => {
                                              const custom = c.event[`custom_${key}`];
                                              const isCustom = custom != null;
                                              return (
                                                <span key={key} title={key}>
                                                  {abbr}:{' '}
                                                  {isCustom ? (
                                                    <>
                                                      <span className="font-semibold text-amber-700">{custom}</span>
                                                      {c.event[key] != null && (
                                                        <span className="ml-0.5 text-gray-400 line-through">{c.event[key]*100}</span>
                                                      )}
                                                    </>
                                                  ) : (
                                                    <span>{c.event[key] ?? '—'}</span>
                                                  )}
                                                </span>
                                              );
                                            })}
                                          </div>
                                        )}
                                      </td>
                                      <td className="p-2">
                                        <span>{c.metric?.name ?? '—'}</span>
                                        {c.metric?.metric_type && (
                                          <span className="block text-[10px] text-gray-400 capitalize">{c.metric.metric_type}</span>
                                        )}
                                      </td>
                                      <td className="p-2">{codeLabel(STATUS_LABELS, c.status)}</td>
                                      <td className="p-2">{codeLabel(RECOMMENDATION_LABELS, c.recommendation)}</td>
                                      <td className="p-2 font-mono">{c.metric_result_output != null ? JSON.stringify(c.metric_result_output) : '—'}</td>
                                      <td className="p-2">
                                        {c.is_threshold_customised && c.custom_threshold != null ? (
                                          <span>
                                            <span className="font-medium">{c.custom_threshold}</span>
                                            {c.metric_threshold != null && (
                                              <span className="ml-1 text-gray-400 line-through">{c.metric_threshold}</span>
                                            )}
                                          </span>
                                        ) : (
                                          c.metric_threshold ?? '—'
                                        )}
                                      </td>
                                      <td className="p-2">{codeLabel(MEET_REQUIREMENT_LABELS, c.outcome_meet_requirement)}</td>
                                      <td className="p-2 font-mono">{c.outcome_output != null ? JSON.stringify(c.outcome_output) : '—'}</td>
                                      <td className="p-2">{c.outcome_notes || c.audit_status_notes || '—'}</td>
                                    </tr>
                                    {isExpanded && (
                                      <tr className="border-b border-purple-100 bg-purple-50/30">
                                        <td></td>
                                        <td colSpan={9} className="p-3">
                                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                            <div>
                                              <p className="text-xs font-semibold text-gray-700 mb-1">Event details</p>
                                              <dl className="text-[11px] text-gray-600 space-y-0.5">
                                                {c.event?.description && (<div><dt className="inline font-semibold">Description: </dt><dd className="inline">{c.event.description}</dd></div>)}
                                                {c.event?.cause && (<div><dt className="inline font-semibold">Cause: </dt><dd className="inline">{c.event.cause}</dd></div>)}
                                                {c.event?.reason && (<div><dt className="inline font-semibold">Reason: </dt><dd className="inline">{c.event.reason}</dd></div>)}
                                                {(c.event?.categories || []).length > 0 && (
                                                  <div className="flex flex-wrap items-center gap-1 pt-0.5">
                                                    <dt className="font-semibold">Categories: </dt>
                                                    {c.event.categories.map((cat) => (
                                                      <span
                                                        key={cat.id}
                                                        title={cat.taxonomy_group_name || cat.description || ''}
                                                        className="inline-block px-1.5 py-0.5 rounded-full bg-purple-100 text-purple-700 text-[10px] font-medium"
                                                      >
                                                        {cat.name}
                                                      </span>
                                                    ))}
                                                  </div>
                                                )}
                                                {!c.event?.description && !c.event?.cause && !c.event?.reason && !(c.event?.categories || []).length && (<span className="italic text-gray-400">No additional details</span>)}
                                              </dl>
                                            </div>
                                            <div>
                                              <p className="text-xs font-semibold text-gray-700 mb-1">Metric details</p>
                                              <dl className="text-[11px] text-gray-600 space-y-0.5">
                                                {c.metric?.description && (<div><dt className="inline font-semibold">Description: </dt><dd className="inline">{c.metric.description}</dd></div>)}
                                                {c.metric?.reason && (<div><dt className="inline font-semibold">Reason: </dt><dd className="inline">{c.metric.reason}</dd></div>)}
                                                {c.metric?.formula && (<div><dt className="inline font-semibold">Formula: </dt><dd className="inline font-mono">{c.metric.formula}</dd></div>)}
                                                {c.metric?.definition && (<div><dt className="inline font-semibold">Definition: </dt><dd className="inline">{c.metric.definition}</dd></div>)}
                                                {!c.metric?.description && !c.metric?.reason && !c.metric?.formula && !c.metric?.definition && (<span className="italic text-gray-400">No additional details</span>)}
                                              </dl>
                                            </div>
                                          </div>
                                        </td>
                                      </tr>
                                    )}
                                    </Fragment>
                                    );
                                  })}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <p className="text-xs text-gray-400 italic">No criteria submitted yet.</p>
                          )}

                          <p className="text-xs text-gray-600 mt-3">
                            <span className="font-semibold">Overall recommendation:</span>{' '}
                            {codeLabel(RECOMMENDATION_LABELS, auditor.audit_recommendation?.recommendation)}
                          </p>
                          <p className="text-xs text-gray-600 mt-1">
                            <span className="font-semibold">Overall notes:</span>{' '}
                            {auditor.audit_recommendation?.notes || 'No notes provided'}
                          </p>
                        </div>
                      ))}

                      {((audit.unused?.events?.length || 0) + (audit.unused?.metrics?.length || 0)) > 0 && (
                        <div className="bg-gray-50 border-2 border-dashed border-gray-200 rounded-2xl p-4 mb-3">
                          <p className="text-sm font-semibold text-gray-700 mb-2">
                            Unused (not assessed by any auditor)
                          </p>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div>
                              <p className="text-xs font-semibold text-gray-500 mb-1">Events ({audit.unused?.events?.length || 0})</p>
                              {(audit.unused?.events || []).length > 0 ? (
                                <ul className="space-y-1">
                                  {audit.unused.events.map((e) => (
                                    <li key={e.id} className="text-xs text-gray-600">
                                      <span className="font-medium">{e.name}</span>
                                      {e.description && <span className="text-gray-400"> — {e.description}</span>}
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <p className="text-xs text-gray-400 italic">None</p>
                              )}
                            </div>
                            <div>
                              <p className="text-xs font-semibold text-gray-500 mb-1">Metrics ({audit.unused?.metrics?.length || 0})</p>
                              {(audit.unused?.metrics || []).length > 0 ? (
                                <ul className="space-y-1">
                                  {audit.unused.metrics.map((m) => (
                                    <li key={m.id} className="text-xs text-gray-600">
                                      <span className="font-medium">{m.name}</span>
                                      {m.metric_type && <span className="text-gray-400 capitalize"> · {m.metric_type}</span>}
                                      {m.description && <span className="text-gray-400"> — {m.description}</span>}
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <p className="text-xs text-gray-400 italic">None</p>
                              )}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </>
              );
            })()}
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminOverview;
