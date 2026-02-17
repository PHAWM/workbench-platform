import React, { useState } from 'react';
import { X, Link } from 'lucide-react';
import { metricsAPI } from '../../api/apiService';

const AssignMetricToEventModal = ({
  isOpen,
  onClose,
  event,
  availableMetrics = [],
  auditId,
  onAssignComplete,
  toast = null
}) => {
  const [selectedMetricId, setSelectedMetricId] = useState(null);
  const [threshold, setThreshold] = useState('0.5');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Helper for notifications
  const notify = {
    success: (message) => toast ? toast.success(message) : console.log(message),
    error: (message) => toast ? toast.error(message) : console.error(message),
  };

  // Normalize availableMetrics to always be an array
  const metricsArray = Array.isArray(availableMetrics)
    ? availableMetrics
    : (availableMetrics?.metrics || availableMetrics?.data || []);

  // Filter out metrics that are already assigned to this event
  const metricsNotAssigned = metricsArray.filter(metric => {
    const isAlreadyAssigned = event?.metrics?.some(m => m.id === metric.id || m.id === metric.metric_id);
    return !isAlreadyAssigned;
  });

  const handleAssign = async () => {
    if (!selectedMetricId || !event?.id || !auditId) {
      notify.error('Please select a metric to assign');
      return;
    }

    setIsSubmitting(true);
    try {
      await metricsAPI.assignMetricToEvent(auditId, event.id, selectedMetricId, threshold);
      const selectedMetric = metricsArray.find(m => m.id === selectedMetricId || m.metric_id === selectedMetricId);
      notify.success(`Metric "${selectedMetric?.name || selectedMetric?.metric_name || selectedMetric?.description || 'Selected metric'}" assigned to event successfully`);
      if (onAssignComplete) {
        onAssignComplete({ eventId: event.id, metricId: selectedMetricId, threshold });
      }
    } catch (error) {
      console.error('Error assigning metric to event:', error);
      notify.error(`Failed to assign metric: ${error.message || 'Unknown error'}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    setSelectedMetricId(null);
    setThreshold('0.5');
    onClose();
  };

  if (!isOpen || !event) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-half max-h-[80vh] overflow-hidden">
        {/* Header */}
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-purple-100 rounded-full flex items-center justify-center">
                <Link className="w-5 h-5 text-purple-600" />
              </div>
              <div>
                <h2 className="text-lg font-bold">Assign Metric to Event</h2>
                <p className="text-base text-gray-600">
                  Assign a metric to <strong>{event.name || event.description}</strong>
                </p>
              </div>
            </div>
            <button
              onClick={handleClose}
              className="p-2 hover:bg-gray-100 rounded-full transition-colors"
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4 overflow-y-auto max-h-[50vh]">
          {metricsNotAssigned.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <p className="text-base">All available metrics are already assigned to this event</p>
              <p className="text-base text-gray-400 mt-1">
                Create a new metric to assign it to this event
              </p>
            </div>
          ) : (
            <>
              <div>
                <label className="block text-base font-medium text-gray-700 mb-2">
                  Select Metric
                </label>
                <div className="space-y-2">
                  {metricsNotAssigned.map(metric => (
                    <label
                      key={metric.id}
                      className={`flex items-start gap-3 p-3 border-2 rounded-lg cursor-pointer transition-all ${
                        selectedMetricId === metric.id
                          ? 'border-purple-400 bg-purple-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <input
                        type="radio"
                        name="metric"
                        value={metric.id}
                        checked={selectedMetricId === metric.id}
                        onChange={() => setSelectedMetricId(metric.id)}
                        className="mt-1 w-4 h-4 text-purple-600 border-gray-300 focus:ring-purple-500"
                      />
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-base">{metric.name || metric.description}</span>
                          {(metric.metricType || metric.metric_type) && (
                            <span className={`text-base px-2 py-0.5 rounded-full ${
                              (metric.metricType || metric.metric_type)?.toLowerCase() === 'quantitative'
                                ? 'bg-blue-100 text-blue-800'
                                : 'bg-green-100 text-green-800'
                            }`}>
                              {metric.metricType || metric.metric_type}
                            </span>
                          )}
                        </div>
                        {metric.description && metric.name && (
                          <div className="text-base text-gray-500 mt-1">{metric.description}</div>
                        )}
                        {(metric.formula || metric.definition) && (
                          <div className="text-base text-gray-400 mt-1">
                            {(metric.metricType || metric.metric_type)?.toLowerCase() === 'quantitative' ? 'Formula: ' : 'Definition: '}
                            {metric.formula || metric.definition}
                          </div>
                        )}
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-base font-medium text-gray-700 mb-2">
                  Threshold
                </label>
                <input
                  type="text"
                  value={threshold}
                  onChange={(e) => setThreshold(e.target.value)}
                  placeholder="e.g., 0.5"
                  className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-purple-400 focus:outline-none"
                />
                <p className="text-base text-gray-500 mt-1">
                  Threshold value for this metric-event association
                </p>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-between gap-3 p-6 border-t bg-gray-50">
          <button
            onClick={handleClose}
            className="flex items-center gap-2 px-4 py-2 text-gray-600 border-2 border-purple-200 rounded-full hover:bg-purple-200 transition-colors"
          >
            Return to Audit Criteria
          </button>
          <button
            onClick={handleAssign}
            disabled={!selectedMetricId || isSubmitting || metricsNotAssigned.length === 0}
            className={`px-6 py-2 rounded-full text-base font-semibold transition-colors ${
              selectedMetricId && !isSubmitting && metricsNotAssigned.length > 0
                ? 'bg-purple-100 hover:bg-purple-200 border-2 border-purple-200'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed border-2 border-gray-300'
            }`}
          >
            {isSubmitting ? 'Assigning...' : 'Assign Metric'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default AssignMetricToEventModal;
