import React, { useState } from 'react';
import { ChevronUp, ChevronDown, User, Plus, Info } from 'lucide-react';
import MetricCard from '../metric/MetricCard';
import { Tooltip, InfoTooltip } from '../ui/toolTip';
import AssignMetricToEventModal from '../popUp/AssignMetricToEventModal';

export const EventCard = ({
  event,
  isExpanded,
  onToggle,
  onMetricToggle,
  onThresholdUpdate,
  onEditEvent,
  onEditMetric,
  onAssignMetricToEvent, // Callback when a metric is assigned to an event
  isReadOnly,
  availableUnderlyingFeatures = [],
  availableTargetFeatures = [],
  indexItem,
  showThresholdErrors = false, // Show validation errors for missing thresholds
  availableMetrics = [], // All available metrics for assignment
  auditId = null, // Audit ID for API calls
  toast = null, // Toast for notifications
}) => {
  const [showAssignModal, setShowAssignModal] = useState(false);

  // Handle the case where metrics might be undefined
  let metrics = event.metrics || [];
  const hasMetrics = metrics.length > 0;

  // Normalize availableMetrics to always be an array
  const metricsArray = Array.isArray(availableMetrics)
    ? availableMetrics
    : (availableMetrics?.metrics || availableMetrics?.data || []);

  // Check if any metric in this event needs threshold warning
  const hasMetricsWithMissingThreshold = showThresholdErrors && metrics.some(metric => {
    if (!metric.useInAudit) return false;
    const threshold = metric.threshold;
    return threshold === null ||
      threshold === undefined ||
      threshold === '' ||
      (typeof threshold === 'string' && threshold.toLowerCase() === 'not set');
  });

  const handleAssignComplete = (assignmentData) => {
    setShowAssignModal(false);
    if (onAssignMetricToEvent) {
      onAssignMetricToEvent(assignmentData);
    }
  };

  return (
      <div className={`
        w-full p-6 rounded-2xl border-2 from-purple-50 to-pink-50 mb-4 transition-all
        ${hasMetricsWithMissingThreshold
          ? 'border-red-400 bg-red-100'
          : `border-purple-100 ${(indexItem + 1) % 2 === 0 ? 'bg-purple-400' : 'bg-purple-300'}`}
      `}>
      <div className="grid grid-cols-2 gap-6 pb-3">
        <div className="flex items-center">
          <span className="font-semibold text-xl mr-2 align-middle">Event
          </span>
            <InfoTooltip content="What can or does happen when you use the AI Application." classNam="px-4">
            </InfoTooltip>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center">
          <span className="font-semibold text-xl mr-2 align-middle">Metrics </span>
            <InfoTooltip content="How can we measure an event  if it is happening." classNam="px-4">
              </InfoTooltip>
              </div>
          {metricsArray.length > 0 && auditId && !isReadOnly && (
            <button
              onClick={() => setShowAssignModal(true)}
              className="flex items-center gap-1 bg-purple-100 hover:bg-purple-200 px-3 py-1 rounded-full text-base font-semibold border-2 border-purple-200 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Assign Metric
            </button>
          )}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-6 items-start">
        {/* Left Half - Event Details */}
        <div className='border-2 border-purple-200 rounded-lg p-3 transition-all bg-purple-200'>
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-lg">{event.name}</span>
                {event.isUserCreated && (
                  <div className="bg-purple-600 border-2 px-2 border-purple-200 rounded-full flex items-center justify-center">
                    <User className="w-8 h-8 text-purple-500" />
                  </div>
                )}
              </div>
              <button onClick={onToggle}>
                {isExpanded ? <ChevronUp className="w-7 h-7" /> : <ChevronDown className="w-7 h-7" />}
              </button>
            </div>

            {/* Always show description */}
            <div className="text-base text-gray-700 mb-4">
              <strong>Description:</strong> {event.description}
            </div>
          </div>

           {/* Edit button - shown (outside the expanded section) */}
           {!isExpanded && (
          <button 
            onClick={() => onEditEvent && onEditEvent(event)}
            disabled={isReadOnly}
            className="bg-purple-100 hover:bg-purple-200 px-4 py-2 rounded-full text-base font-semibold transition-colors border-2 border-purple-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-purple-100 mb-4"
          >
            Edit {event.isUserCreated ? "Event" : "Event Values"}
          </button>
           )}

          {/* Expanded details */}
          {isExpanded && (
            <>
              <div className="space-y-2 text-base text-gray-700 mb-4">
                <div><span className="font-semibold text-base mr-1 align-middle">Event Category:</span><InfoTooltip content="Which thematic group(s) could you sort this event into?" side="top" classNam="px-4"></InfoTooltip> {event.category}</div>
                <div><span className="font-semibold text-base mr-1 align-middle">Event Creator:</span> {event.creator}</div>
                <div><span className="font-semibold text-base mr-1 align-middle">Valence:</span><InfoTooltip content="Is the event positive or negative?" side="top" classNam="px-4"></InfoTooltip> {event.valence}</div>
                <div><span className="font-semibold text-base mr-1 align-middle">Magnitude of Impact:</span><InfoTooltip content="How big the impact of the event would be if it happens." side="top" classNam="px-4"></InfoTooltip> {event.magnitude}%</div>
                <div><span className="font-semibold text-base mr-1 align-middle">Likelihood:</span><InfoTooltip content="How likely is it that the event might happen." side="top" classNam="px-4"></InfoTooltip> {event.likelihood}%</div>
                <div><span className="font-semibold text-base mr-1 align-middle">Cause:</span><InfoTooltip content="What could lead to this event happening ?" side="top" classNam="px-4"></InfoTooltip> {event.cause}</div>
                <div><span className="font-semibold text-base mr-1 align-middle">Associated Entities:</span><InfoTooltip content="Who is being impacted by the event ?" side="top" classNam="px-4"></InfoTooltip> {event.entities}</div>
                <div><span className="font-semibold text-base mr-1 align-middle">Why Event was added:</span> {event.reason}</div>
              </div>

              
              <button 
                onClick={() => onEditEvent && onEditEvent(event)}
                disabled={isReadOnly}
                className="bg-purple-100 hover:bg-purple-200 px-4 py-2 rounded-full text-base font-semibold transition-colors border-2 border-purple-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-purple-100"
              >
                Edit {event.isUserCreated ? "Event" : "Event Values"}
              </button>
              
            </>
          )}
        </div>

        {/* Right Half - Associated Metrics */}
        <div className='rounded-lg transition-all'>
          
          {!hasMetrics ? (
            <div className="text-center py-8 text-gray-500">
              <p className="text-base">No metrics associated with this event</p>
              <p className="text-xs text-gray-400 mt-1">
                Create metrics and associate them with events to enable audit analysis
              </p>
            </div>
          ) : (
            <div className="space-y-2 overflow-y-auto">
              {metrics.map((metric) => (
                <MetricCard
                  key={`${event.id}-${metric.id}`}
                  metric={metric}
                  eventId={event.id}
                  onMetricToggle={onMetricToggle}
                  onThresholdUpdate={onThresholdUpdate}
                  onEditMetric={onEditMetric}
                  isReadOnly={isReadOnly}
                  availableUnderlyingFeatures={availableUnderlyingFeatures}
                  availableTargetFeatures={availableTargetFeatures}
                  showThresholdError={showThresholdErrors}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Assign Metric to Event Modal */}
      <AssignMetricToEventModal
        isOpen={showAssignModal}
        onClose={() => setShowAssignModal(false)}
        event={event}
        availableMetrics={availableMetrics}
        auditId={auditId}
        onAssignComplete={handleAssignComplete}
        toast={toast}
      />
    </div>
  );
};

export default EventCard;