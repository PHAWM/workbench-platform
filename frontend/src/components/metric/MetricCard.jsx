import React, { useState } from 'react';
import { ChevronUp, User, Settings, ChevronDown } from 'lucide-react';
import ThresholdModal from '../popUp/threshold';
import { Tooltip, InfoTooltip } from '../ui/toolTip';

const MetricCard = ({
  metric,
  eventId,
  onMetricToggle,
  onThresholdUpdate,
  onEditMetric,
  isReadOnly,
  displayMode = "detailed", // "simplified" or "detailed"
  availableUnderlyingFeatures = [], // List of available Distinguishing Factors
  availableTargetFeatures = [], // List of available target
  showThresholdError = false // Show validation error for missing threshold
}) => {
  const [showThresholdModal, setShowThresholdModal] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  const handleToggleChange = () => {
    if (onMetricToggle) {
      onMetricToggle(eventId, metric.id);
    }
  };

  const handleThresholdClick = () => {
    setShowThresholdModal(true);
  };

  const handleThresholdSave = (thresholdData) => {
    if (onThresholdUpdate) {
      onThresholdUpdate(eventId, metric.id, thresholdData);
    }
    setShowThresholdModal(false);
  };

  const getMetricTypeColor = () => {
    switch (metric.metricType?.toLowerCase() || metric.metric_type?.toLowerCase()) {

      case 'quantitative':
        return 'bg-blue-100 border-blue-800';
      case 'qualitative':
        return 'bg-green-100 border-green-800';
      default:
        return 'bg-gray-50 border-gray-800';
    }
  };


  // Helper function to format features display
  const formatFeatures = (features, featureList = [], target= false) => {

    if (!target){
      if (Array.isArray(features)) {
        return features.map(f => {
          if (typeof f === 'object' && f.feature_id) {
            const feature = featureList.find(af => af.id === f.feature_id);
            const featureName = feature ? (feature.feature_name || feature.name || `Feature ${f.feature_id}`) : `Feature ${f.feature_id}`;
            return featureName.charAt(0).toUpperCase() + featureName.slice(1);
          }
          return typeof f === 'string' ? f : String(f);
        });
      }
    } else{
      if (Array.isArray(features)) {
        return features.map(f => {
          if (typeof f === 'object' && f.target_feature_id) {
            const feature = featureList.find(af => af.id === f.target_feature_id);
            const featureName = feature ? (feature.target_feature || feature.name || `Target ${f.target_feature_id}`) : `Target ${f.target_feature_id}`;
            return featureName;
          }
          return typeof f === 'string' ? f : String(f);
        });
      }
    }
  };

  // Helper function to format scale points display
  const formatScalePoints = (scaleData) => {
    if (!scaleData) return 'Not set';
    
    if (typeof scaleData === 'object') {
      if (scaleData.scale_points) {
        const labels = Object.keys(scaleData.scale_points);
        return labels.join(', '); // "poor, average, good, excellent"
      }
      return JSON.stringify(scaleData);
    }
    
    return scaleData.toString();
  };

  // Get the display name for the metric
  const getMetricName = () => {
    return metric.name || metric.description || 'Unnamed Metric';
  };

  // Check if this metric needs threshold validation warning
  // Threshold is considered not set if it's null, undefined, empty string, or 'Not set' (case insensitive)
  const isThresholdNotSet = metric.threshold === null ||
    metric.threshold === undefined ||
    metric.threshold === '' ||
    (typeof metric.threshold === 'string' && metric.threshold.toLowerCase() === 'not set');
  const needsThresholdWarning = showThresholdError && metric.useInAudit && isThresholdNotSet;

  return (
    <>
      <div className={`border-2 rounded-lg p-3 transition-all ${
        needsThresholdWarning
          ? 'border-red-400 bg-red-50'
          : 'border-purple-200 bg-white-100'
      }`}>
        
  {/* Main row with checkbox, name, type indicator, and expand button */}
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3 flex-1">
        <div className="flex items-center gap-2 flex-1">
          {/* Metric type indicator */}
          {/* <span className="text-xs" title={metric.metricType || metric.metric_type || 'Unknown Type'}>
            {getMetricTypeIcon()}
          </span> */}
          <span className="text-lg">{getMetricName()}</span>
          {/* Show metric type badge */}
          {/* Steel this style for the performance analysis */}
          {(metric.metricType || metric.metric_type) && (
            <span className={`text-sm px-2 py-1 rounded-full ${getMetricTypeColor()}`}>
              {(metric.metricType || metric.metric_type).charAt(0).toUpperCase() +
              (metric.metricType || metric.metric_type).slice(1)}
            </span>
          )}
          {(metric.metricType || metric.metric_type)?.toLowerCase() === 'qualitative' && (
           <InfoTooltip content="Metric based on subjective assessment, categories or descriptive data." side="bottom" classNam="px-4"></InfoTooltip> 
          )}
          {(metric.metricType || metric.metric_type)?.toLowerCase() === 'quantitative' && (
           <InfoTooltip content="Metric based on numerical data, measurements or statistical analysis." side="bottom" classNam="px-4"></InfoTooltip> 
          )}
          {/* Inline threshold warning badge - visible when collapsed */}
          {needsThresholdWarning && !isExpanded && (
            <span className="text-xs px-2 py-1 rounded-full bg-red-100 text-red-700 border border-red-300 font-medium">
              Threshold required
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 px-3">
          {metric.isUserCreated && (
            <div className="bg-purple-600 border-2 px-2 border-purple-200 rounded-full flex items-center justify-center">
              <User className="w-8 h-8 text-purple-500" />
            </div>
          )}
          <span className="text-base font-semibold">Use in audit?</span>
          <input 
            type="checkbox" 
            checked={metric.useInAudit || false}
            onChange={handleToggleChange}
            disabled={isReadOnly}
            className="w-4 h-4 py-3 text-purple-600 border-purple-300 rounded focus:ring-purple-500" 
          />
        </div>
      </div>
      <button 
        onClick={() => setIsExpanded(!isExpanded)}
        className="p-1 hover:bg-gray-100 rounded transition-colors">
        {isExpanded ? <ChevronUp className="w-6 h-6" /> : <ChevronDown className="w-6 h-6" />}
      </button>
    </div>

    {/* Second row with buttons - aligned to the right */}
    {!isExpanded && (metric.isUserCreated || true) && (
      <div className="flex justify-end gap-2 mt-4">
        {metric.isUserCreated && (
          <button
            onClick={() => onEditMetric && onEditMetric(metric, eventId)}
            disabled={isReadOnly}
                  className="bg-purple-100 hover:bg-purple-200 px-3 py-1 rounded-full text-base font-semibold border-2 border-purple-200 transition-colors flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-purple-100"
          >
            Edit Metric
          </button>
        )}
        <button
          onClick={handleThresholdClick}
          disabled={isReadOnly}
          className="bg-purple-100 hover:bg-purple-200 px-3 py-1 rounded-full text-base font-semibold border-2 border-purple-200 transition-colors flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-purple-100"
        >
          Set Threshold
        </button>
      </div>
    )}

        {/* Expanded details */}
        {isExpanded && (
          <div className="mt-3 pt-3 border-t border-gray-200">
            <div className="space-y-2 text-base text-gray-600 mb-3">
              <div><strong>Description:</strong> {metric.description || 'No description provided'}</div>
              
              {/* Show features for qualitative metrics */}
              {(metric.underlyingFeatures || metric.features) && ((metric.metricType || metric.metric_type)?.toLowerCase() === 'qualitative') && (
                <div>
                  <span className="font-semibold text-base mr-1 align-middle">Features:</span>
                  <InfoTooltip content="The aspect of the AI Application output used for the metric." side="top" classNam="px-4"></InfoTooltip> 
                  {(() => {
                    const formatted = formatFeatures(metric.underlyingFeatures, availableUnderlyingFeatures);
                    return Array.isArray(formatted) ? formatted.join(', ') : formatted;
                  })()}
                </div>
              )}

              {/* Show scale points for qualitative metrics */}
              {(metric.metricType || metric.metric_type)?.toLowerCase() === 'qualitative' && metric.scale_points && (
                <div><span className="font-semibold text-base mr-1 align-middle">Scale Points:</span> {formatScalePoints(metric.scale_points)}</div>
              )}
              
              {/* Show target for quantitative metrics */}
              {(metric.metricType || metric.metric_type)?.toLowerCase() === 'quantitative' && metric.targetFeatures && (
                <div><span className="font-semibold text-base mr-1 align-middle">Targets:</span> {(() => {
                  const formatted = formatFeatures(metric.targetFeatures, availableTargetFeatures, true);
                  return Array.isArray(formatted) ? formatted.join(', ') : formatted;
                })()}</div>
              )}

              {/* Show Distinguishing Factors for quantitative metrics */}
              {(metric.metricType || metric.metric_type)?.toLowerCase() === 'quantitative' && metric.underlyingFeatures && (
                <div>
                  <span className="font-semibold text-base mr-1 align-middle">Distinguishing Factors: </span>
                  <InfoTooltip content="The aspect of the AI Application output used for the metric." side="top" classNam="px-4"></InfoTooltip> 
                  {(() => {
                    const formatted = formatFeatures(metric.underlyingFeatures, availableUnderlyingFeatures);
                    return Array.isArray(formatted) ? formatted.join(', ') : formatted  ? metric.underlyingFeatures===null : "All";
                  })()}
                </div>
              )}
              
              <div>
                <strong>Threshold:</strong> <InfoTooltip content="The value of the metric performance that is still acceptable." side="top" classNam="px-4"></InfoTooltip> {metric.threshold || 'Not set'}
                {needsThresholdWarning && (
                  <span className="text-red-600 ml-2 font-medium">
                    - Please set a threshold before proceeding to Performance Analysis
                  </span>
                )}
              </div>
              
              {/* Show reason if available */}
              {metric.reason && (
                <div><strong>Reason:</strong> {metric.reason}</div>
              )}
            </div>
            
            <div className="flex gap-2 justify-end">
              <div className="flex gap-2">
                {metric.isUserCreated && (
                  <button
                    onClick={() => onEditMetric && onEditMetric(metric, eventId)}
                    disabled={isReadOnly}
                    className="bg-purple-100 hover:bg-purple-200 px-3 py-1 rounded-full text-base font-semibold border-2 border-purple-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-purple-100"
                  >
                    Edit Metric
                  </button>
                )}
                <button
                  onClick={handleThresholdClick}
                  disabled={isReadOnly}
                  className="bg-purple-100 hover:bg-purple-200 px-3 py-1 rounded-full text-base font-semibold border-2 border-purple-200 transition-colors flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-purple-100">
                  Set Threshold
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Threshold Modal */}
      <ThresholdModal
        isOpen={showThresholdModal}
        onClose={() => setShowThresholdModal(false)}
        metric={metric}
        onSave={handleThresholdSave}
      />
    </>
  );
};

export default MetricCard;