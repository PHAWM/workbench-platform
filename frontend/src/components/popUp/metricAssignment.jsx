import React, { useState, useEffect } from 'react';
import { ChevronUp, ChevronDown, User, ArrowLeft } from 'lucide-react';
import QuantitativeMetricForm from '../metric/QuantitativeMetricForm';
import QualitativeMetricForm from '../metric/QualitativeMetricForm';
import MetricTypeModal from './metricTypeSelection';
import { metricsAPI } from '../../api/apiService';
import {
  buildQuantitativeMetricValues,
  buildQualitativeMetricValues,
  detectAndCreateNewFeatures,
} from '../../utils/formUtils';
import { buildMetricApiPayload } from '../../utils/auditUtils';

const MetricAssignmentModal = ({
  eventData,
  metrics,
  onClose,
  onComplete,
  onBack,
  auditId,
  onMetricCreated,
  // NEW: Props to preserve selections
  initialSelectedMetrics = [],
  onSelectionChange = null, // Callback to notify parent of selection changes
  availableUnderlyingFeatures = [],
  availableTargetFeatures = [],
  toast = null, // Optional toast for notifications
  updateVisibility,
}) => {
  // Helper for notifications - uses toast if available, falls back to alert
  const notify = {
    success: (message) => toast ? toast.success(message) : alert(message),
    error: (message) => toast ? toast.error(message) : alert(message),
    warning: (message) => toast ? toast.warning(message) : alert(message),
    info: (message) => toast ? toast.info(message) : alert(message)
  };
  // Initialize with previously selected metrics
  const [selectedMetrics, setSelectedMetrics] = useState(initialSelectedMetrics);
  const [expandedMetrics, setExpandedMetrics] = useState({});
  
  // States for nested metric creation
  const [showCreateMetric, setShowCreateMetric] = useState(false);
  const [showMetricTypeModal, setShowMetricTypeModal] = useState(false);
  const [currentMetricForm, setCurrentMetricForm] = useState(null);
  const [savedEventData, setSavedEventData] = useState(null);

  const [availableMetrics, setAvailableMetrics] = useState(metrics);

  // NEW: Notify parent component when selections change
  useEffect(() => {
    if (onSelectionChange) {
      onSelectionChange(selectedMetrics);
    }
  }, [selectedMetrics, onSelectionChange]);
  
  const handleMetricToggle = (metricId) => {
    setSelectedMetrics(prev => {
      const newSelection = prev.includes(metricId) 
        ? prev.filter(id => id !== metricId)
        : [...prev, metricId];
      return newSelection;
    });
  };

  const handleMetricExpand = (metricId) => {
    setExpandedMetrics(prev => ({
      ...prev,
      [metricId]: !prev[metricId]
    }));
  };

  const handleComplete = () => {
    const selectedMetricObjects = selectedMetrics.map(metricId =>
      availableMetrics.find(m => m.id === metricId)
    ).filter(Boolean);

    const eventWithMetrics = {
      ...eventData,
      name: eventData.name || eventData.eventName,
      eventName: eventData.eventName || eventData.name,

      selectedMetricIds: selectedMetrics,
      // Pair each selected metric with its values_id (captured when the metric
      // was POSTed). Existing metrics from the catalogue won't have one and
      // fall back to null — same shape the backend expects.
      selectedMetricPairs: selectedMetricObjects.map(m => ({
        metric_id: m.id,
        values_id: m.values_id ?? null,
      })),
      metrics: selectedMetricObjects.map(m => ({ ...m, useInAudit: false })),

      id: `event-${Date.now()}`,
      isUserCreated: true
    };

    onComplete(eventWithMetrics);
  };

  // NEW: Enhanced back handler that preserves selections
  const handleBackToEventForm = () => {
    // Don't clear selections - let parent handle the state
    if (onBack) {
      onBack(selectedMetrics); // Pass current selections back
    }
  };

  // NEW: Enhanced close handler that preserves selections
  const handleClose = () => {
    // Don't clear selections - let parent handle the state
    if (onClose) {
      onClose(selectedMetrics); // Pass current selections back
    }
  };

  // Handlers for creating new metric
  const handleCreateNewMetric = () => {
    setSavedEventData(eventData);
    setShowCreateMetric(true);
    setShowMetricTypeModal(true);
  };

  const handleMetricTypeSelection = (type) => {
    setShowMetricTypeModal(false);
    setCurrentMetricForm(type);
  };

  const handleMetricFormComplete = async (metricData) => {
    try {
      console.log('[metricAssignment.handleMetricFormComplete] metricData IN:', {
        type: metricData?.type,
        threshold: metricData?.threshold,
        underlyingFeatures: metricData?.underlyingFeatures,
        targetFeatures: metricData?.targetFeatures,
        scalePointsArray: metricData?.scalePointsArray,
        featureRanges: metricData?.featureRanges,
        all_keys: metricData ? Object.keys(metricData) : null,
      });

      // 1. Create any new features in the catalogue first so we have real IDs.
      // Mirrors handleEventAssignmentComplete in auditHandlers.jsx.
      const { featureNameToIdMap } = await detectAndCreateNewFeatures(
        metricData,
        availableUnderlyingFeatures,
        availableTargetFeatures,
        auditId,
      );

      // 2. Build metric_values via the spec-compliant builders.
      const metric_values = metricData.type === 'quantitative'
        ? buildQuantitativeMetricValues(
            metricData,
            availableUnderlyingFeatures,
            availableTargetFeatures,
            featureNameToIdMap,
          )
        : buildQualitativeMetricValues(
            metricData,
            availableUnderlyingFeatures,
            availableTargetFeatures,
            featureNameToIdMap,
          );

      // 3. POST the metric standalone — no event_mappings here. The event
      // we're inside doesn't exist server-side yet (eventData has a
      // client-only id), so we can't link the metric to it now. The parent
      // posts the event later with `metrics: [{metric_id, values_id: null}]`
      // and that's what creates the event<->metric mapping.
      const apiPayload = buildMetricApiPayload(
        { ...metricData, metric_values, events: [] },
        auditId,
        metricData.type,
      );

      console.log('[metricAssignment.handleMetricFormComplete] apiPayload OUT:', JSON.stringify(apiPayload, null, 2));

      let createdMetric;
      if (metricData.type === 'qualitative') {
        createdMetric = await metricsAPI.createQualitativeMetric(apiPayload);
      } else {
        createdMetric = await metricsAPI.createQuantitativeMetric(apiPayload);
      }

      // The metric POST returns `created_values: [{id, ...}]`. We need to
      // capture that id so it can be sent as `values_id` when the event is
      // posted — otherwise the event<->metric mapping is left dangling.
      const valuesId = createdMetric?.created_values?.[0]?.id ?? null;

      const newMetric = {
        id: createdMetric.id,
        values_id: valuesId,
        name: metricData.name,
        description: metricData.description,
        definition: metricData.definition,
        creator: 'Current User',
        features: metricData.targetFeatures ? metricData.targetFeatures.join(', ') : 'User Generated',
        threshold: metricData.threshold || 'Custom Threshold',
        reason: metricData.reason,
        labels: 'Custom, User Created',
        isUserCreated: true,
        metricType: metricData.type,
        metric_type: metricData.type,
        formula: metricData.definition
      };

      setAvailableMetrics(prev => [...prev, newMetric]);
      setSelectedMetrics(prev => [...prev, newMetric.id]);
      
      if (onMetricCreated) {
        onMetricCreated(newMetric);
      }
      
      setCurrentMetricForm(null);
      setShowCreateMetric(false);
      setSavedEventData(null);
      updateVisibility(true);

      notify.success(`Metric "${newMetric.name}" created successfully and added to selection!`);

    } catch (error) {
      console.error('Error creating metric:', error);

      let errorMessage = 'Failed to create metric';
      if (error.response?.data?.detail) {
        if (Array.isArray(error.response.data.detail)) {
          const validationErrors = error.response.data.detail.map(err =>
            `${err.loc.join('.')}: ${err.msg}`
          ).join(', ');
          errorMessage = `Validation error: ${validationErrors}`;
        } else {
          errorMessage = error.response.data.detail;
        }
      } else if (error.message) {
        errorMessage = error.message;
      }
      updateVisibility(true);

      notify.error(`Failed to create metric: ${errorMessage}`);
    }
  };

  const handleMetricFormCancel = () => {
    setCurrentMetricForm(null);
    setShowCreateMetric(false);
    setSavedEventData(null);
  };

  const handleBackToMetricAssignment = () => {
    setCurrentMetricForm(null);
    setShowCreateMetric(false);
  };

  const MetricCard = ({ metric }) => {
    const isSelected = selectedMetrics.includes(metric.id);
    const isExpanded = expandedMetrics[metric.id];

    return (
      <div className={`border-2 rounded-2xl p-4 transition-all ${
        isSelected 
          ? 'border-purple-300 bg-gradient-to-r from-purple-50 to-pink-50' 
          : 'border-gray-200 bg-white hover:border-gray-300'
      }`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3 flex-1">
            <input
              type="checkbox"
              checked={isSelected}
              onChange={() => handleMetricToggle(metric.id)}
              className="w-4 h-4 text-purple-600 border-2 border-purple-200 rounded focus:ring-purple-500"
            />
            <div className="flex items-center gap-2">
              {metric.isUserCreated && (
                <div className="w-6 h-6 bg-purple-200 rounded-full flex items-center justify-center">
                  <User className="w-3 h-3 text-purple-600" />
                </div>
              )}
              <span className="font-medium">{metric.name}</span>
              <span className="text-base text-gray-500 bg-gray-100 px-2 py-1 rounded">
                {metric.metric_type || metric.metricType}
              </span>
            </div>
          </div>
          <button 
            onClick={() => handleMetricExpand(metric.id)}
            className="p-1 hover:bg-gray-100 rounded-full transition-colors"
          >
            {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
          </button>
        </div>

        {!isExpanded && (
          <div className="text-base text-gray-700 ml-7">
            <strong>Description:</strong> {metric.description}
          </div>
        )}

        {isExpanded && (
          <div className="ml-7 space-y-2 text-base text-gray-700">
            <div><strong>Description:</strong> {metric.description}</div>
            {/* <div><strong>Definition:</strong> {metric.definition || metric.formula}</div> */}
            <div><strong>Metric Creator:</strong> {metric.creator}</div>
            <div><strong>Features:</strong> {metric.features}</div>
            <div><strong>Metric Threshold:</strong> {metric.threshold}</div>
            <div><strong>Why Metric was added:</strong> {metric.reason}</div>
            <div><strong>Scale Labels:</strong> {metric.labels}</div>
            
            {isSelected && (
              <div className="mt-4 pt-3 border-t border-purple-200">
                <div className="flex items-center gap-2 text-purple-700 text-base">
                  <span className="w-2 h-2 bg-purple-400 rounded-full"></span>
                  <span>This metric will be included with the event</span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  // If we're in metric creation mode, show the appropriate form
  if (showCreateMetric) {
    if (currentMetricForm === 'qualitative') {
      return (
        <QualitativeMetricForm
          onCancel={handleMetricFormCancel}
          onComplete={handleMetricFormComplete}
          showBackToAssignment={true}
          onBackToAssignment={handleBackToMetricAssignment}
          availableUnderlyingFeatures={availableUnderlyingFeatures}
          availableTargetFeatures={availableTargetFeatures}
        />
      );
    }

    if (currentMetricForm === 'quantitative') {
      return (
        <QuantitativeMetricForm
          onCancel={handleMetricFormCancel}
          onComplete={handleMetricFormComplete}
          showBackToAssignment={true}
          onBackToAssignment={handleBackToMetricAssignment}
          availableUnderlyingFeatures={availableUnderlyingFeatures}
          availableTargetFeatures={availableTargetFeatures}
        />
      );
    }
  }

  return (
    <>
      <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg w-full">
        {/* Purpose Box */}
        <div className="mb-6 bg-b7efff rounded-2xl border-2 border-purple-300 p-6 shadow-md">
          <p className="text-gray-700">
            This is the Assign Metrics page. Here you can select existing metrics to associate with your event, or create new custom metrics. Choose or create one or more metric that will measure whether the event is occurring and to what degree. Once you have chosen or created the metric(s), you can save that by clicking the Save Audit Criteria button or Return to Create Event without saving. 
          </p>
        </div>

        {/* Header */}
        <div className="flex items-center gap-3 mb-6 pb-4 border-b border-purple-200">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Assign Metrics to Event</h1>
            <p className="text-base text-gray-600">
              Select existing metrics for: <strong>{eventData.eventName || eventData.name}</strong>
            </p>
            {initialSelectedMetrics.length > 0 && (
              <p className="text-base text-blue-600 mt-1">
                ✓ Restored {initialSelectedMetrics.length} previous selection{initialSelectedMetrics.length !== 1 ? 's' : ''}
              </p>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="space-y-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-medium text-gray-700">Available Metrics</h3>
            <span className="text-base text-gray-600 bg-purple-100 px-3 py-1 rounded-full">
              {selectedMetrics.length} selected
            </span>
          </div>

          {/* Metrics List */}
          <div className="space-y-4">
            {availableMetrics.map(metric => (
              <MetricCard key={metric.id} metric={metric} />
            ))}
          </div>

          {/* Create New Metric Button */}
          <div className="pt-4">
            <button
              onClick={handleCreateNewMetric}
              className="w-full border-2 border-dashed border-purple-300 rounded-2xl p-4 text-purple-600 hover:border-purple-400 hover:bg-purple-50 transition-colors"
            >
              + Create New Metric
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-between items-center mt-8 pt-6 border-t border-purple-200">
          {onBack ? (
            <button
              onClick={handleBackToEventForm}
              className="flex items-center gap-2 px-4 py-2 text-gray-600 border-2 border-purple-200 rounded-full hover:bg-purple-200 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Return to Create Event without saving
            </button>
          ) : (
            <button
              onClick={handleClose}
              className="flex items-center gap-2 px-4 py-2 text-gray-600 border-2 border-purple-200 rounded-full hover:bg-purple-200 transition-colors"
            >
              Return to Audit Criteria without Saving
            </button>
          )}
          <button
            onClick={handleComplete}
            disabled={selectedMetrics.length === 0}
            className={`px-6 py-2 rounded-full text-base font-semibold transition-colors ${
              selectedMetrics.length > 0
                ? 'bg-purple-100 hover:bg-purple-200 border-2 border-purple-200'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed border-2 border-gray-300'
            }`}
          >
            Save Audit Criteria
          </button>
        </div>
      </div>

      {/* Metric Type Selection Modal */}
      <MetricTypeModal
        isOpen={showMetricTypeModal}
        onClose={() => {
          setShowMetricTypeModal(false);
          setShowCreateMetric(false);
          setSavedEventData(null);
        }}
        onSelectType={handleMetricTypeSelection}
      />
    </>
  );
};

export default MetricAssignmentModal;