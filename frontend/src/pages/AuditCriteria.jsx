import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Plus, ArrowLeft, ArrowRight } from 'lucide-react';

// Components
import { Navigation } from '../components/navigation/Navigation';
import { EventCard } from '../components/event/EventCard';
import { CreateEventForm } from '../components/event/EventCreate'
import { EditEventForm } from '../components/event/EventEdit';
import QualitativeMetricForm from '../components/metric/QualitativeMetricForm';
import QuantitativeMetricForm from '../components/metric/QuantitativeMetricForm';
import MetricTypeModal from '../components/popUp/metricTypeSelection';
import EventAssignmentModal from '../components/popUp/eventAssignment';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import ErrorMessage from '../components/ui/ErrorMessage';
import EditMetricForm from '../components/metric/MetricEdit';

// Custom hooks and utilities
import { useAuditData } from '../hooks/useAuditData';
import { createAuditHandlers } from '../handlers/auditHandlers';
import { hasAnySelectedMetrics, isAuditReadOnly, getSelectedMetricsWithoutThreshold } from '../utils/auditUtils';
import { useApi } from '../context/apiContext';
import { useToast } from '../hooks/useToast';
import { useOnboarding } from '../context/onboardingContext';
import { createAuditCriteriaHandlers } from '../handlers/auditCriteriaHandlers';

const AuditCriteriaDashboard = () => {
  const { auditId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { checkAndStartOnboarding } = useOnboarding();

  // Use custom hook for data management
  const auditData = useAuditData(auditId);

  // Get audit status and access type from context
  const { auditStatus, accessType, loadAudit } = useApi();
  const isReadOnly = isAuditReadOnly(auditStatus);
  const [isVisible, setIsVisible] = useState(true);

  // Trigger onboarding when entering this page from dashboard
  useEffect(() => {
    checkAndStartOnboarding('audit-criteria');
  }, [checkAndStartOnboarding]);

  // UI state
  const [expandedEvents, setExpandedEvents] = useState({ });


  const [currentPage, setCurrentPage] = useState('audit-criteria');
  const [showThresholdErrors, setShowThresholdErrors] = useState(false);
  
  // Modal states
  const [modals, setModals] = useState({
    showCreateEventForm: false,
    showMetricTypeModal: false,
    showEventAssignment: false,
    currentMetricForm: null,
    editingEvent: null,
    editingMetric: null
  });

  // Preserved data states
  const [preserved, setPreserved] = useState({
    eventSelections: [],
    metricSelections: [],
    currentMetricFormData: null,
    savedMetricData: null
  });

  sessionStorage.setItem('auditId', auditId);

  // Fetch audit status and access type from context
  useEffect(() => {
    if (auditId) {
      loadAudit(auditId);
    }
  }, [auditId, loadAudit]);

  // Utility functions
  const updateModals = (updates) => setModals(prev => ({ ...prev, ...updates }));
  const updatePreserved = (updates) => setPreserved(prev => ({ ...prev, ...updates }));
  const resetForms = () => {
    updateModals({
      showCreateEventForm: false,
      showMetricTypeModal: false,
      showEventAssignment: false,
      currentMetricForm: null,
      editingEvent: null,
      editingMetric: null
    });
    updatePreserved({
      eventSelections: [],
      metricSelections: [],
      currentMetricFormData: null,
      savedMetricData: null
    });
  };

  const updateVisibility = (visible) => setIsVisible(visible);

  // Create handlers using the handler factory
  const handlers = createAuditHandlers(
    auditId,
    auditData.updateState,
    updateModals,
    updatePreserved,
    auditData.reloadData,
    auditData.entities, // Pass available entities
    auditData.eventCategories, // Pass available event categories
    updateVisibility,
    toast // Pass toast for notifications
  );

  // Navigation check
  if (!auditId) navigate('/dashboard');
  const hasSelectedMetrics = hasAnySelectedMetrics(auditData.events);

  // Determine help context based on current modal/form state
  const getHelpContext = () => {
    if (modals.showCreateEventForm || modals.editingEvent) {
      return { activeForm: 'createEvent' };
    }
    if (modals.currentMetricForm === 'qualitative') {
      return { activeForm: 'qualitative' };
    }
    if (modals.currentMetricForm === 'quantitative') {
      return { activeForm: 'quantitative' };
    }
    return {};
  };

  // Create page-specific handlers using the handler factory
  const criteriaHandlers = createAuditCriteriaHandlers({
    setExpandedEvents,
    setIsVisible,
    updateModals,
    resetForms,
    setShowThresholdErrors,
    handlers,
    navigate,
    auditData,
    currentPage
  });

  // Destructure handlers for use in component
  const {
    handleEventToggle,
    handleCreateNewEvent,
    handleCreateMetric,
    handleEditEvent,
    handleEditMetric,
    handleNavigationWithValidation,
    handleNavigateToPerformance: handleNavigateToPerformanceBase
  } = criteriaHandlers;

  // Wrapper for navigation with validation that passes the utility function
  const handleNavWithValidation = async (pageId) => {
    await handleNavigationWithValidation(pageId, getSelectedMetricsWithoutThreshold);
  };

  // Wrapper for the bottom button navigation to performance
  const handleNavigateToPerformance = async () => {
    await handleNavigateToPerformanceBase(getSelectedMetricsWithoutThreshold);
  };
  
  // Loading state
  if (auditData.loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-50 to-pink-50 p-4">
        <Navigation
          hasSelectedMetrics={auditData.hasSelectedMetrics || hasSelectedMetrics}
          hasEvaluated={auditData.hasEvaluated || false}
          currentPage={currentPage}
          hasEnteredAudit={true}
          isReadOnly={isReadOnly}
          onNavigate={handleNavWithValidation}
          helpContext={getHelpContext()}
        />
        <LoadingSpinner message="Loading audit criteria..." />
      </div>
    );

  }
  

  // Main render
  return (
    <div className="min-h-screen bg-purple-to-br from-purple-50 to-pink-50 p-4">
      <Navigation
        hasSelectedMetrics={auditData.hasSelectedMetrics || hasSelectedMetrics}
        hasEvaluated={auditData.hasEvaluated || false}
        hasEnteredAudit={true}
        currentPage={currentPage}
        onNavigate={handleNavWithValidation}
        helpContext={getHelpContext()}
      />

      {/* Purpose Box - Added as per wireframe */}
      {isVisible && <div className="mb-6 bg-b7efff rounded-2xl border-2 border-purple-300 p-6 shadow-md" data-onboarding="purpose-box">
        <div className="flex items-start">
          <div>
              <p className="text-gray-700">
              This is the Audit Criteria page. The purpose of this page is to choose the audit criteria for your audit. There might be some existing audit criteria provided by the audit instigators, which you may choose to use in your audit. For these, you can adjust the Event Values - valence, likelihood and magnitude - of the event and the threshold of the metric. You can also create your own audit criteria by creating your own event and/ or metric. For these, you can Edit all fields. Once you have chosen which audit criteria to use in the audit by clicking the corresponding checkbox(es), you can move forward to the Performance Analysis page.</p>
          </div>
        </div>
      </div>}

      {auditData.error && (
        <ErrorMessage 
          message={auditData.error} 
          onRetry={auditData.loadAuditData}
          onDismiss={() => auditData.updateState({ error: null })}
        />
      )}

      <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg w-full">
        {/* Conditional form rendering */}
        {modals.showCreateEventForm ? (
          <CreateEventForm
            onCancel={() => {updateModals({ showCreateEventForm: false }); updateVisibility(true);}}
            onComplete={handlers.handleEventFormComplete}
            eventCategories={auditData.eventCategories}
            entities={auditData.entities}
            auditId={auditId}
            availableMetrics={auditData.availableMetrics}
            availableTargetFeatures={auditData.availableTargetFeatures}
            availableUnderlyingFeatures={auditData.availableUnderlyingFeatures}
            updateVisibility={updateVisibility}
          />
        ) : modals.editingEvent ? (
          <EditEventForm
            event={modals.editingEvent}
            onCancel={() => {updateModals({ editingEvent: null }); updateVisibility(true);}}
            onSave={handlers.handleEventEditSave}
            eventCategories={auditData.eventCategories}
            entities={auditData.entities}
            editValues={modals.editingEvent.isUserCreated}
            isReadOnly={isReadOnly}
          />
        ) : modals.editingMetric ? (
          <EditMetricForm
            metric={modals.editingMetric}
            onCancel={() => {updateModals({ editingMetric: null }); updateVisibility(true);}}
            onSave={(data) => handlers.handleMetricEditSave(data, auditData.events, auditData.availableUnderlyingFeatures, auditData.availableTargetFeatures)}
            availableTargetFeatures={auditData.availableTargetFeatures}
            availableUnderlyingFeatures={auditData.availableUnderlyingFeatures}
            isReadOnly={isReadOnly}
          />
        ) : modals.currentMetricForm === 'qualitative' ? (
          <QualitativeMetricForm
            onCancel={() => {updateModals({ currentMetricForm: null }); updateVisibility(true);}}
            onComplete={handlers.handleMetricFormComplete}
            preservedData={preserved.currentMetricFormData}
            availableTargetFeatures={auditData.availableTargetFeatures}
            availableUnderlyingFeatures={auditData.availableUnderlyingFeatures}
          />
        ) : modals.currentMetricForm === 'quantitative' ? (
          <QuantitativeMetricForm
            onCancel={() => {updateModals({ currentMetricForm: null }); updateVisibility(true);}}
            onComplete={handlers.handleMetricFormComplete}
            preservedData={preserved.currentMetricFormData}
            availableTargetFeatures={auditData.availableTargetFeatures}
            availableUnderlyingFeatures={auditData.availableUnderlyingFeatures}
          />
        ) : modals.showEventAssignment && preserved.savedMetricData ? (
          <EventAssignmentModal
            metricData={preserved.savedMetricData}
            onClose={() => {updateModals({ showEventAssignment: false }); updateVisibility(true);}}
            onBack={(currentSelections = []) => {
              updatePreserved({ eventSelections: currentSelections });
              updateModals({
                showEventAssignment: false,
                currentMetricForm: preserved.currentMetricFormData?.type
              });
            }}
            onComplete={(metricWithEvents) => handlers.handleEventAssignmentComplete(
              metricWithEvents,
              preserved.currentMetricFormData,
              auditData.availableUnderlyingFeatures,
              auditData.availableTargetFeatures
            )}
            eventCategories={auditData.eventCategories}
            entities={auditData.entities}
            availableMetrics={auditData.availableMetrics}
            eventsExisting={auditData.events}
            auditId={auditId}
            initialSelectedEvents={preserved.eventSelections}
            onSelectionChange={(selectedEventIds) => updatePreserved({ eventSelections: selectedEventIds })}
            availableUnderlyingFeatures={auditData.availableUnderlyingFeatures}
            availableTargetFeatures={auditData.availableTargetFeatures}
            toast={toast}
          />
        ) : (
          <>
            {/* Events list */}
            <div className="space-y-4 mb-6">
              {/* Action buttons */}
              <div className="flex gap-4 justify-between" data-onboarding="create-buttons">
                <button
                  onClick={handleCreateNewEvent}
                  disabled={isReadOnly}
                  className="flex items-center gap-2 bg-purple-100 hover:bg-purple-200 px-4 py-3 rounded-full text-base font-semibold transition-colors border-2 border-purple-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-purple-100">
                  <Plus className="w-4 h-4" />Create New Event
                </button>
                <button
                  onClick={handleCreateMetric}
                  disabled={isReadOnly}
                  className="flex items-center gap-2 bg-purple-100 hover:bg-purple-200 px-4 py-3 rounded-full text-base font-semibold transition-colors border-2 border-purple-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-purple-100">
                  <Plus className="w-4 h-4" />Create New Metric
                </button>
              </div>
              {auditData.events.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <p>No events found. Please create events and metrics.</p>
                </div>
              ) : (
                <div>
                  {/* Sort events: user-created first, then others */}
                  {[...auditData.events]
                    .sort((a, b) => {
                      // User-created events come first
                      if (a.isUserCreated && !b.isUserCreated) return -1;
                      if (!a.isUserCreated && b.isUserCreated) return 1;
                      return 0;
                    })
                    .map((event, index) => (
                    <div
                      key={event.id}
                      data-onboarding={index === 0 ? "first-event" : undefined}
                    >
                      <EventCard
                        event={event}
                        isExpanded={expandedEvents[event.id] || false}
                        onToggle={() => handleEventToggle(event.id)}
                        onMetricToggle={(eventId, metricId) => handlers.handleMetricToggle(eventId, metricId, auditData.events)}
                        onThresholdUpdate={(eventId, metricId, data) => handlers.handleThresholdUpdate(eventId, metricId, data, auditData.events)}
                        onEditEvent={handleEditEvent}
                        onEditMetric={handleEditMetric}
                        onAssignMetricToEvent={() => auditData.reloadData()}
                        isReadOnly={isReadOnly}
                        availableUnderlyingFeatures={auditData.availableUnderlyingFeatures}
                        availableTargetFeatures={auditData.availableTargetFeatures}
                        indexItem={index}
                        showThresholdErrors={showThresholdErrors}
                        availableMetrics={auditData.availableMetrics}
                        auditId={auditId}
                        toast={toast}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="flex gap-4 justify-between" data-onboarding="navigation-buttons">
              <button
                onClick={() => handlers.handleBackwardNavigation('audit-criteria', navigate)}
                className="flex items-center gap-2 hover:bg-purple-200 px-4 py-3 rounded-full text-base font-semibold transition-colors border-2 border-purple-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-purple-100">
                <ArrowLeft/>Back to AI Application Overview
              </button>
              <button
                onClick={handleNavigateToPerformance}
                className="flex items-center gap-2 hover:bg-purple-200 px-4 py-3 rounded-full text-base font-semibold transition-colors border-2 border-purple-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-purple-100">
                Next to Performance Analysis <ArrowRight/>
              </button>
            </div>

            <div className="text-right mt-6 text-purple-400 font-bold text-lg opacity-50">PHAWM</div>
          </>
        )}
      </div>

      {/* Modals */}
      <MetricTypeModal
        isOpen={modals.showMetricTypeModal}
        onClose={() => {updateModals({ showMetricTypeModal: false }); updateVisibility(true);}}
        onSelectType={(type) => updateModals({ showMetricTypeModal: false, currentMetricForm: type })}
      />

    </div>
  );
};

export default AuditCriteriaDashboard;