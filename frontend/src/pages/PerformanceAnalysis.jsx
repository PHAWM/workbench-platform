import React, { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, LabelList, ResponsiveContainer, ReferenceLine } from 'recharts';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import { Navigation } from '../components/navigation/Navigation';
import { useParams, useNavigate } from 'react-router-dom';
import { createAuditHandlers } from '../handlers/auditHandlers';
import { useAuditData } from '../hooks/useAuditData';
import { checkEventMetricStatus, isAuditReadOnly, formatThreshold } from '../utils/auditUtils';
import { useApi } from '../context/apiContext';
import { useToast } from '../hooks/useToast';
import { useSessionStorage } from '../hooks/useSessionStorage';
import OutputEvaluationScreen from './OutputEvaluationScreen';
import { useOnboarding } from '../context/onboardingContext';
import { MetricVisualization, detectOutputType } from '../components/visualizations';

import {
  performanceAPI,
  evaluationAPI,
  getAccessTypeLabel
} from '../api/apiService';
import {
  validateNotes,
  validateRecommendation,
  getRecommendationNumber,
  getMetricTypeColor
} from '../handlers/performanceAnalysisHandlers';


const PerformanceAnalysis = () => {
  const [currentPage] = useState('performance');
  const [showOutputEvaluation, setShowOutputEvaluation] = useState(false);
  const [isVisible, setIsVisible] = useState(true);
  const { auditId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { checkAndStartOnboarding } = useOnboarding();

  // Trigger onboarding when entering this page from dashboard
  useEffect(() => {
    checkAndStartOnboarding('performance');
  }, [checkAndStartOnboarding]);

  // Output Evaluation data state - persisted in sessionStorage for page refresh survival
  const [outputEvaluationData, setOutputEvaluationData] = useSessionStorage(`evaluation_data_${auditId}`, {});
  const [hasOutputEvaluation, setHasOutputEvaluation] = useSessionStorage(`evaluation_flags_${auditId}`, {});

  const [isSaving, setIsSaving] = useState(false);

  
  const PURPOSE_BOX_MESSAGES = {
    default: "This is the Performance Analysis page. The purpose of this page is to assess the performance of the AI application against the audit criteria. For this, you assess each audit criteria individually by using either the sidebar or the perform analysis buttons to navigate. Once you have made recommendations for all audit criteria, you can move forward to the Audit Recommendation page."
    ,
    
    greyWhiteBox: "This is Performance Analysis page for an individual audit criteria. The purpose of this page is to assess how well the AI application performs against the audit criteria. If the audit instigator has provided data, there will be a visual respresentation of the performance of the AI application against your threshold. The button \"Perform Output Evaluation\" on the top right allows you to perform further analysis on your own data, should you want. Once you have analysed your performance, you fill in the feedback and justification box and make your recommendation. You can save the analysis by clicking the Save Analysis button or return to the Performance analysis screen of the audit criteria without saving by clicking the Return to Performance Analysis without saving button."
    ,
   
    blackBox: "This is Performance Analysis page for an individual audit criteria. The purpose of this page is to assess how well the AI application performs against the audit criteria. If the audit instigator has provided data, there will be a visual respresentation of the performance of the AI application against your threshold. Once you have analysed your performance, you fill in the feedback and justification box and make your recommendation. You can save the analysis by clicking the Save Analysis button or return to the Performance analysis screen of the audit criteria without saving by clicking the Return to Performance Analysis without saving button."
    
    };

  // helper function
  const getPurposeBoxMessage = () => {
    if (activeTab === 'overview' || !selectedMetricForAnalysis) {
      return PURPOSE_BOX_MESSAGES.default;
    }
    // (accessTypeLabel === "Grey Box" || accessTypeLabel === "White Box") && selectedMetricForAnalysis &&
    if ((accessTypeLabel === 'Grey Box' || accessTypeLabel === 'White Box')&& selectedMetricForAnalysis ) {
      return PURPOSE_BOX_MESSAGES.greyWhiteBox;
    }
    else {
       return PURPOSE_BOX_MESSAGES.blackBox;
    }
    
    return PURPOSE_BOX_MESSAGES.default;
  };



  // Get audit status and access type from context
  const {
    auditStatus,
    accessType,
    loadAudit,
    currentAudit,
    setEvaluationCache,
    updateEvaluationCache,
    getEvaluationCache
  } = useApi();
  const isReadOnly = isAuditReadOnly(auditStatus);

  // New state for vertical tabs
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedMetricForAnalysis, setSelectedMetricForAnalysis] = useState(null);

  // API data
  const [auditData, setAuditData] = useState({ auditName: "Audit", events: [] });
  const auditDataAPI = useAuditData(auditId);
  const [loading, setLoading] = useState(true);

  // Detail analysis states
  const [chartData, setChartData] = useState([]);
  const [notes, setNotes] = useState('');
  const [recommendation, setRecommendation] = useState(null);
  const [outputError, setOutputError] = useState(false);

  // Validation states for save analysis
  const [validationErrors, setValidationErrors] = useState({
    notes: '',
    recommendation: ''
  });
  const [touched, setTouched] = useState({
    notes: false,
    recommendation: false
  });

  const handlers = createAuditHandlers(
    auditId,
    auditDataAPI.updateState,
    () => {}, // updateModals - not used in performance analysis
    () => {}, // updatePreserved - not used in performance analysis
    auditDataAPI.reloadData,
    auditDataAPI.entities, // Pass available entities
    auditDataAPI.eventCategories, // Pass available event categories
    null, // updateVisibility
    toast // toast for notifications
  );
  // Output Evaluation Handlers
  const handleOutputEvaluationStart = () => {
    if (selectedMetricForAnalysis) {
      // Use audit_criteria_id as the key if available, otherwise use id
      const key = selectedMetricForAnalysis.audit_criteria_id || selectedMetricForAnalysis.id;
      setHasOutputEvaluation(prev => ({
        ...prev,
        [key]: true
      }));
    }
  };

  const handleOutputEvaluationComplete = (results) => {
    if (selectedMetricForAnalysis) {
      // Use audit_criteria_id as the key if available, otherwise use id
      const key = selectedMetricForAnalysis.audit_criteria_id || selectedMetricForAnalysis.id;
      setOutputEvaluationData(prev => ({
        ...prev,
        [key]: results
      }));
      setHasOutputEvaluation(prev => ({
        ...prev,
        [key]: true
      }));
      // Update the cache with the new evaluation data
      updateEvaluationCache(auditId, key, results);
    }
    // REMOVED: setShowOutputEvaluation(false); - Don't close automatically
  };

  // Helper function to get current metric's outcome data
  const getCurrentOutcomeData = () => {
    if (!selectedMetricForAnalysis) return null;

    // Try both audit_criteria_id and id to find the data
    const key = selectedMetricForAnalysis.audit_criteria_id || selectedMetricForAnalysis.id;

    return outputEvaluationData[key] ||
           outputEvaluationData[selectedMetricForAnalysis.id] ||
           outputEvaluationData[selectedMetricForAnalysis.metric_id];
  };

  const hasCurrentOutputEvaluation = selectedMetricForAnalysis ? (() => {
    const key = selectedMetricForAnalysis.audit_criteria_id || selectedMetricForAnalysis.id;
    return hasOutputEvaluation[key] ||
           hasOutputEvaluation[selectedMetricForAnalysis.id] ||
           hasOutputEvaluation[selectedMetricForAnalysis.metric_id];
  })() : false;

  // Using getRecommendationNumber from performanceAnalysisHandlers

  const hasEvaluated = checkEventMetricStatus(auditData);

  // Fetch audit status and access type from context
  useEffect(() => {
    if (auditId) {
      loadAudit(auditId);
    }
  }, [auditId, loadAudit]);

  // Persist hasSelectedMetrics=true when on Performance Analysis page
  // This ensures the nav item stays enabled when navigating back
  useEffect(() => {
    if (auditId) {
      try {
        const stored = localStorage.getItem(`audit_state_${auditId}`);
        const currentState = stored ? JSON.parse(stored) : {};
        const newState = {
          ...currentState,
          hasSelectedMetrics: true
        };
        localStorage.setItem(`audit_state_${auditId}`, JSON.stringify(newState));

        // Dispatch custom event to notify Navigation component
        window.dispatchEvent(new CustomEvent('auditStateChange', {
          detail: { auditId, state: newState }
        }));
      } catch (error) {
        console.error('Failed to persist hasSelectedMetrics:', error);
      }
    }
  }, [auditId]);

  // Fetch outcome evaluation results - check cache first, then API
  useEffect(() => {
    const fetchOutputEvaluationResults = async () => {
      // Check if we have cached data for this audit
      const cachedData = getEvaluationCache(auditId);
      if (cachedData && cachedData.data && Object.keys(cachedData.data).length > 0) {
        // Use cached data
        setOutputEvaluationData(cachedData.data);
        setHasOutputEvaluation(cachedData.flags);
        return;
      }

      // No cache, fetch from API - using the new endpoint structure
      try {
        // Use performanceAPI.getEvaluationSummary which returns the full summary including output_evaluation
        const response = await performanceAPI.getEvaluationSummary(auditId);

        if (response && response.output_evaluation && response.output_evaluation.length > 0) {
          // Transform output_evaluation array to component format
          // Group by audit_criteria_id and count requirements
          // Requirements mapping: 0 = NotEvaluated, 1 = No, 2 = Maybe, 3 = Yes
          const transformedData = {};
          const flags = {};

          // Get unique audit_criteria_ids from output_evaluation
          const criteriaIds = [...new Set(response.output_evaluation.map(item => item.audit_criteria_id))];

          criteriaIds.forEach(criteriaId => {
            // Filter items for this criteria
            const criteriaItems = response.output_evaluation.filter(item => item.audit_criteria_id === criteriaId);

            // Count requirements: 0 = NotEvaluated, 1 = No, 2 = Maybe, 3 = Yes
            const counts = {
              notEvaluated: criteriaItems.filter(item => item.requirements === 0 || item.requirements === null || item.requirements === undefined).length,
              no: criteriaItems.filter(item => item.requirements === 1).length,
              maybe: criteriaItems.filter(item => item.requirements === 2).length,
              yes: criteriaItems.filter(item => item.requirements === 3).length
            };

            // Store the summary data for this criteria
            transformedData[criteriaId] = {
              summary: counts,
              details: criteriaItems,
              files: criteriaItems // Keep the raw items for potential display
            };

            // Mark that this criteria has evaluation
            flags[criteriaId] = true;
          });

          setOutputEvaluationData(transformedData);
          setHasOutputEvaluation(flags);
          // Store in cache
          setEvaluationCache(auditId, transformedData, flags);
        } else if (response && response.total_output_evaluated === 0) {
          // No output evaluations exist yet - this is normal
          // console.log('No output evaluations found for this audit');
        }
      } catch (error) {
        console.warn('Failed to fetch outcome evaluation results (might not exist yet):', error);
        // Don't show error to user - this is expected if no evaluations exist yet
      }
    };

    if (auditId) {
      fetchOutputEvaluationResults();
    }
  }, [auditId, getEvaluationCache, setEvaluationCache]);

  // Fetch data from API
  useEffect(() => {
    const fetchData = async () => {
      try {
        // Step 1: Get the evaluation summary synchronously (has all metadata + existing outputs)
        const summaryData = await performanceAPI.getEvaluationSummary(auditId);

        // Check if there are any audit criteria - if not, redirect to audit-criteria
        if (!summaryData.audit_criteria || summaryData.audit_criteria.length === 0) {
          navigate(`/audit-criteria/${auditId}`);
          return;
        }

        // Helper function to transform audit_criteria to events structure
        const transformToEvents = (criteriaList) => {
          const eventsMap = {};
          criteriaList.forEach((item) => {
            if (!eventsMap[item.event_name]) {
              eventsMap[item.event_name] = {
                id: Object.keys(eventsMap).length + 1,
                name: item.event_name,
                metrics: []
              };
            }
            eventsMap[item.event_name].metrics.push({
              id: item.audit_criteria_id,
              audit_criteria_id: item.audit_criteria_id,
              name: item.metric_name,
              eventName: item.event_name,
              output: item.output,
              target_features: item.target_features,
              event_id: item.event_id,
              metric_id: item.metric_id,
              threshold: item.threshold,
              recommendation: item.recommendation_text,
              status: item.status_text,
              notes: item.notes,
              metric_type: item.metric_type,
              scale_points: item.scale_points
            });
          });
          return Object.values(eventsMap);
        };

        // Set initial data immediately
        setAuditData({
          auditName: currentAudit?.name || `Audit ${auditId}`,
          events: transformToEvents(summaryData.audit_criteria)
        });
        setLoading(false);

        // Step 2: Trigger async output generation in background (don't block)
        handlers.handleGenerateOutputEvaluation()
          .then((resultsData) => {
            // Step 3: Merge new outputs with existing summary data
            if (resultsData?.audit_criteria) {
              // Create a map of audit_criteria_id -> new output
              const outputMap = {};
              resultsData.audit_criteria.forEach(item => {
                outputMap[item.audit_criteria_id] = {
                  output: item.output,
                  target_features: item.target_features
                };
              });

              // Update summary data with new outputs
              const mergedCriteria = summaryData.audit_criteria.map(criterion => {
                const newData = outputMap[criterion.audit_criteria_id];
                if (newData) {
                  return {
                    ...criterion,
                    output: newData.output,
                    target_features: newData.target_features || criterion.target_features
                  };
                }
                return criterion;
              });

              // Update state with merged data
              setAuditData({
                auditName: currentAudit?.name || `Audit ${auditId}`,
                events: transformToEvents(mergedCriteria)
              });
            }
          })
          .catch((outputError) => {
            // console.warn("Output generation failed (might already exist):", outputError);
            // Page continues showing existing data
          });

      } catch (error) {
        // console.error("Error fetching audit data:", error);
        setLoading(false);
      }
    };

    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auditId, currentAudit]);


  // Parse output evaluation data and generate chart data
  useEffect(() => {
    if (selectedMetricForAnalysis) {

      // Reset error state
      setOutputError(false);

      // Extract output data from the metric
      const output = selectedMetricForAnalysis.output;
      const targetFeature = selectedMetricForAnalysis.target_features;
      const metricType = selectedMetricForAnalysis.metric_type;
      const thresholdStr = selectedMetricForAnalysis.threshold;
      const threshold = parseFloat(thresholdStr) || 0;

      let generatedChartData = [];

      // Check if we have output with underlying_features (target feature is optional - we'll use fallback)
      if (output && output.underlying_features) {

        // Get ALL distinguishing factors (e.g., "P2-P3", "P4", etc.)
        const underlyingFeatureKeys = Object.keys(output.underlying_features);

        // Collect all group values from all distinguishing factors
        const allGroupValues = [];

        underlyingFeatureKeys.forEach(underlyingFeatureKey => {
          const featureData = output.underlying_features[underlyingFeatureKey];

          // Check if we have group data - can be under 'overall' or directly under the feature key
          // For "all" feature, data is directly under it as {"all": {...}} instead of {"overall": {"all": {...}}}
          const groupsData = featureData.overall || featureData;

          if (groupsData && typeof groupsData === 'object') {
            const groups = Object.keys(groupsData);

            // Extract values for all groups in this underlying feature
            groups.forEach(groupName => {
              const groupData = groupsData[groupName];

              // Extract the target feature value (e.g., accuracy, precision)
              let value = 0;

              // If we have a target feature, try to find it
              if (targetFeature) {
                const targetKey = targetFeature.toLowerCase().replace(/\s+/g, '_');

                // Handle case where groupData is a primitive value (single number)
                if (typeof groupData === 'number') {
                  value = groupData * 100; // Convert to percentage for display
                }
                // Handle case where groupData is an object with metrics
                else if (typeof groupData === 'object' && groupData !== null) {
                  // Try different key formats
                  if (groupData[targetKey] !== undefined) {
                    value = groupData[targetKey] * 100; // Convert to percentage for display
                  } else if (groupData[targetFeature.toLowerCase()] !== undefined) {
                    value = groupData[targetFeature.toLowerCase()] * 100;
                  } else if (groupData.accuracy !== undefined) {
                    // Fallback to accuracy if target not found
                    value = groupData.accuracy * 100;
                  }
                }
              } else {
                // No target feature specified - use fallback

                if (typeof groupData === 'number') {
                  value = groupData * 100;
                } else if (typeof groupData === 'object' && groupData !== null) {
                  // Try common metric names
                  if (groupData.accuracy !== undefined) {
                    value = groupData.accuracy * 100;
                  } else if (groupData.precision !== undefined) {
                    value = groupData.precision * 100;
                  } else if (groupData.recall !== undefined) {
                    value = groupData.recall * 100;
                  } else {
                    // Use the first numeric value found
                    const firstNumericKey = Object.keys(groupData).find(k => typeof groupData[k] === 'number');
                    if (firstNumericKey) {
                      value = groupData[firstNumericKey] * 100;
                    }
                  }
                }
              }

              // Create unique name combining underlying feature and group
              // e.g., "P2-P3 Male", "P4 Female"
              const displayName = underlyingFeatureKeys.length > 1
                ? `${underlyingFeatureKey} ${groupName.charAt(0).toUpperCase() + groupName.slice(1)}`
                : groupName.charAt(0).toUpperCase() + groupName.slice(1);

              allGroupValues.push({
                name: displayName,
                rawValue: value
              });
            });
          }
        });

        // Calculate threshold line based on metric type
        // Threshold values are treated as percentages directly (e.g., 5 = 5%, 0.1 = 0.1%)
        let thresholdLine = threshold;

        // Build chart data with values and threshold
        generatedChartData = allGroupValues.map(group => {
          return {
            name: group.name,
            value: parseFloat(group.rawValue.toFixed(2)),
            threshold: parseFloat(thresholdLine.toFixed(2))
          };
        });
      }

      // Check if we have valid output data - only for quantitative metrics
      if (metricType?.toLowerCase() === 'quantitative') {

        if (generatedChartData.length === 0 && !output?.confusion_matrix) {
          // No valid output data for quantitative metric - set error state
          setOutputError(true);
          setChartData([]);
        } else {
          setOutputError(false);
          setChartData(generatedChartData);
        }
      } else if (metricType?.toLowerCase() === 'qualitative') {

        // For qualitative metrics, check if we have scale_points and optionally output
        // scale_points can be either an array of {value, label} objects or an object with label:value pairs
        const hasScalePoints = selectedMetricForAnalysis.scale_points &&
          ((Array.isArray(selectedMetricForAnalysis.scale_points) && selectedMetricForAnalysis.scale_points.length > 0) ||
           (typeof selectedMetricForAnalysis.scale_points === 'object' && Object.keys(selectedMetricForAnalysis.scale_points).length > 0));

        if (!hasScalePoints) {
          setOutputError(true);
        } else {
          setOutputError(false);
        }
        setChartData([]);
      } else {
        setChartData(generatedChartData);
      }
      setNotes(selectedMetricForAnalysis.notes || "");

      // Set recommendation based on existing recommendation text
      const existingRec = selectedMetricForAnalysis.recommendation;
      if (existingRec) {
        const rec = existingRec.toLowerCase();
        if (rec.includes('pass')) setRecommendation('Pass');
        else if (rec.includes('fail')) setRecommendation('Fail');
        else if (rec.includes('inconclusive')) setRecommendation('Inconclusive');
        else setRecommendation(null);
      } else {
        setRecommendation(null);
      }
    }
  }, [selectedMetricForAnalysis]);

  useEffect(() => {

  }, [selectedMetricForAnalysis]);


  // Helpers
  const getAllMetrics = () => auditData.events.flatMap(event => event.metrics);
  const getMetricsForEvent = (eventName) => {
    const event = auditData.events.find(e => e.name === eventName);
    return event ? event.metrics : [];
  };

  const getCurrentMetrics = () => {
  if (selectedEvent === "overview") {
    return getAllMetrics();
  } else {
    // For individual metric views, extract just the event name
    const eventName = selectedEvent.split('-').slice(0, -1).join('-');
    return getMetricsForEvent(eventName);
  }
};
  const [selectedEvent, setSelectedEvent] = useState("overview");

  // Status styling
  const getRowBackgroundColor = (recommendation) => {
    if (!recommendation) return 'bg-gradient-to-r from-purple-50 to-blue-50 border-gray-300';
    
    const rec = recommendation.toLowerCase();
    // Check if recommendation is one of: pass, fail, or inclusive
    if (rec === 'pass' || rec === 'fail' || rec === 'inclusive'|| rec === 'inconclusive') {
      return 'bg-green-50 border-green-200 border-2 border-purple-200';
    }
    // Default for any other recommendation value
    return 'bg-gradient-to-r from-purple-50 to-blue-50 border-2 border-purple-200 ';
  };

  // Helper function for recommendation label/badge style
  const getRecommendationStyle = (recommendation) => {
    if (!recommendation) return 'bg-gray-100 text-gray-800';
    
    const rec = recommendation.toLowerCase();
    if (rec === 'fail') return 'bg-red-500 text-white';
    if (rec === 'pass') return 'bg-green-500 text-white';
    if (rec === 'inclusive' || rec === 'inconclusive') return 'bg-yellow-500 text-white';
    return 'bg-gray-100 text-gray-800';
  };

  const handlePerformAnalysis = (metric) => {
    // Reset validation state when selecting a new metric
    setValidationErrors({ notes: '', recommendation: '' });
    setTouched({ notes: false, recommendation: false });
    setSelectedMetricForAnalysis(metric);
    setActiveTab('detail-analysis');
  };

  // Using validateNotes and validateRecommendation from performanceAnalysisHandlers

  const validateAllFields = () => {
    const notesError = validateNotes(notes);
    const recommendationError = validateRecommendation(recommendation);

    setValidationErrors({
      notes: notesError,
      recommendation: recommendationError
    });

    setTouched({
      notes: true,
      recommendation: true
    });

    return !notesError && !recommendationError;
  };

  const handleNotesChange = (value) => {
    setNotes(value);
    if (touched.notes) {
      setValidationErrors(prev => ({
        ...prev,
        notes: validateNotes(value)
      }));
    }
  };

  const handleNotesBlur = () => {
    setTouched(prev => ({ ...prev, notes: true }));
    setValidationErrors(prev => ({
      ...prev,
      notes: validateNotes(notes)
    }));
  };

  const handleRecommendationChange = (value) => {
    setRecommendation(value);
    setTouched(prev => ({ ...prev, recommendation: true }));
    setValidationErrors(prev => ({
      ...prev,
      recommendation: validateRecommendation(value)
    }));
  };

  // New code for saving
  const handleSaveAnalysis = async () => {
    if (!selectedMetricForAnalysis) {
      console.error('No metric selected for analysis');
      return;
    }

    // Validate all fields before saving
    if (!validateAllFields()) {
      toast.error('Please fix the validation errors before saving');
      return;
    }

    setIsSaving(true);
    try {
      // Create the status data object first
      const statusData = {
        event_id: parseInt(selectedMetricForAnalysis.event_id),
        metric_id: parseInt(selectedMetricForAnalysis.metric_id),
        user_audit_id: parseInt(auditId), // This was missing!
        recommendation: getRecommendationNumber(recommendation),
        notes: notes.trim()
      };

      // OPTION 1: Try direct format (what you were doing)

      try {
        await evaluationAPI.updateEventMetricStatus(auditId, statusData);
      } catch (directError) {
        // OPTION 2: Try wrapped format like batch API
        const wrappedStatusData = {
          audit_status: statusData  // Singular, not plural like batch
        };
        await evaluationAPI.updateEventMetricStatus(auditId, wrappedStatusData);
      }
      // Update local state on success
      setAuditData(prevData => ({
        ...prevData,
        events: prevData.events.map(event => ({
          ...event,
          metrics: event.metrics.map(metric =>
            metric.id === selectedMetricForAnalysis.id
              ? { ...metric, notes: notes, recommendation: recommendation }
              : metric
          )
        }))
      }));

      // Reset validation state
      setValidationErrors({ notes: '', recommendation: '' });
      setTouched({ notes: false, recommendation: false });

      toast.success('Analysis saved successfully');
      setSelectedMetricForAnalysis(null);
      setSelectedEvent("overview");
      setActiveTab('overview');
    } catch (error) {
      // console.log(error);
      toast.error('Failed to save analysis');
    } finally {
      setIsSaving(false);
    }
  };
      // Using getMetricTypeColor from performanceAnalysisHandlers




  if (loading) {
    return <div className="p-6 text-gray-600">Loading audit data...</div>;
  }

   
  // --------------------
  // Overview Content
  // --------------------
  const renderOverviewContent = () => (
    <div className="flex gap-6">
      
      {/* Sidebar */}
      <div className="w-1/4" data-onboarding="sidebar">
        <div className="bg-gradient-to-b from-purple-100 to-pink-100 rounded-2xl p-4 border-2 border-purple-200">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            Audit Name: {auditData.auditName}
          </h2>
          <nav className="space-y-2 mt-4">
            <button
              onClick={() => {
                setSelectedMetricForAnalysis(null); 
                setSelectedEvent("overview");
              }}
              className={`w-full text-left px-4 py-3 rounded-md font-medium text-sm ${
                selectedEvent === "overview"
                  ? "bg-purple-200 text-purple-900 border border-purple-300"
                  : "bg-gradient-to-b from-purple-100 to-pink-100 text-gray-700 border border-gray-300 hover:bg-gray-50"
                }`}
            >
              Overview
            </button>
      
            {auditData.events.flatMap((event) =>
              event.metrics.map((metric) => (
                <button
                  key={metric.id}
                  onClick={() => {
                    setSelectedEvent(`${event.name}-${metric.name}`); // Use the full event-metric format
                    handlePerformAnalysis(metric);
                  }}
                  className={`w-full text-left px-4 py-3 rounded-md font-medium text-sm ${
                    selectedEvent === `${event.name}-${metric.name}` // Compare with full format
                      ? "bg-purple-200 text-purple-900 border border-purple-300"
                      : "bg-gradient-to-b from-purple-100 to-pink-100 text-gray-700 border border-gray-300 hover:bg-gray-50"
                    }`}
                >
                  {event.name} – {metric.name}
                </button>
              ))
            )}
          </nav>
        </div>
      </div>


      {/* Metrics */}
      <div className="flex-1">
        <div className="border-2 border-purple-100 rounded-2xl p-6 bg-purple from-purple-50 to-pink-50 w-full ">
          <div className="space-y-4">
            {getCurrentMetrics().map((metric, index) => (
              <div
                key={metric.id}
                data-onboarding={index === 0 ? "first-metric" : undefined}
                className={`border rounded-lg p-6 shadow-sm ${getRowBackgroundColor(metric.recommendation)}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1 grid grid-cols-3 gap-6">
                    <div>
                      <h3 className="font-semibold text-gray-800 mb-2">Audit Criteria</h3>
                      <p className="text-gray-700">
                        {metric.eventName} - {metric.name}
                        <span className={`text-xs px-2 py-1 rounded-full ${getMetricTypeColor(metric.metric_type)} ml-2 border`}>
                          {(metric.metricType || metric.metric_type).charAt(0).toUpperCase() + 
                          (metric.metricType || metric.metric_type).slice(1)}
                        </span>
                      </p>
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-800 mb-2">Threshold</h3>
                      <p className="text-gray-700">
                        {formatThreshold(metric.threshold)}
                      </p>
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-800 mb-2">Recommendation</h3>
                      <span className={`px-3 py-1 rounded-full text-sm font-medium ${getRecommendationStyle(metric.recommendation)}`}>
                        {metric.recommendation}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => handlePerformAnalysis(metric)}
                    className="bg-purple-100 hover:bg-purple-200 px-6 py-2 rounded-full text-base font-semibold transition-colors border-2 border-purple-200"
                  >
                    Perform Analysis
                  </button>
                </div>
              </div>
            ))}

            {getCurrentMetrics().length === 0 && (
              <div className="text-center py-12">
                <p className="text-gray-600 text-lg">No metrics available for the selected event.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
  // --------------------
  // Detail Analysis Content
  // --------------------
  const renderDetailAnalysisContent = () => (
    <div className="flex gap-6">
      {/* Sidebar with metrics */}
      <div className="w-1/4">
        <div className="bg-gradient-to-b from-purple-100 to-pink-100 rounded-2xl p-4 border-2 border-purple-200">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            Audit Name: {auditData.auditName}
          </h2>

          <div className="space-y-2">
            {/* Overview item */}
            <button
              onClick={() => {
                setSelectedMetricForAnalysis(null);
                setSelectedEvent("overview");
                setActiveTab('overview');
              }}
              className={`w-full text-left px-4 py-3 rounded-md font-medium text-sm ${
                // selectedEvent === "overview"
                !selectedMetricForAnalysis
                  ? "bg-purple-200 text-purple-900 border border-purple-300"
                  : "bg-gradient-to-b from-purple-100 to-pink-100 text-gray-700 border border-gray-300 hover:bg-gray-50"
              }`}
            >
              Overview
            </button>

            {/* Metric items */}
            {auditData.events.flatMap((e) =>
              e.metrics.map((metric) => (
                <button
                  key={metric.id}
                  // onClick={() => setSelectedMetricForAnalysis(metric)}
                  onClick={() => handlePerformAnalysis(metric)}
                  
                  className={`w-full text-left px-4 py-3 rounded-md font-medium text-sm ${
                    selectedMetricForAnalysis?.id === metric.id
                      ? "bg-purple-200 text-purple-900 border border-purple-300"
                      : "bg-gradient-to-b from-purple-100 to-pink-100 text-gray-700 border border-gray-300 hover:bg-gray-50"
                    }`}
                >
                  {metric.eventName} - {metric.name}
                </button>
              ))
            )}
          </div>
        </div>
      </div>
      {/* Analysis Panel */}
      <div className="flex-1">
        <div className="border-2 border-purple-100 rounded-2xl p-6 bg-purple from-purple-50 to-pink-50 w-full">
          <div className="flex justify-between items-center mb-6">
            <h1 className="text-xl font-semibold text-gray-800">
              Performance Analysis: {selectedMetricForAnalysis ? `${selectedMetricForAnalysis.eventName} - ${selectedMetricForAnalysis.name}` : '< Select a Metric >'}
            </h1>
            {/* Show Perform Output Evaluation only for Grey or White Box */}
            {(accessTypeLabel === "Grey Box" || accessTypeLabel === "White Box") && selectedMetricForAnalysis && (
              <div className="flex flex-col">
                <h2 className="text-xl font-semibold text-gray-800 mb-2">
                  Test your own data:
                </h2>
                <button
                  onClick={() => { setShowOutputEvaluation(true); setIsVisible(false); }}
                  className="flex items-center gap-2 px-4 py-2 rounded-full font-semibold border-2 border-purple-200 bg-purple-100 hover:bg-purple-200 transition-colors"
                >
                  Perform Output Evaluation
                </button>
              </div>
            )}
          </div>

          {/* Chart or Scale Visualization */}
          {selectedMetricForAnalysis && (
          <div className="flex gap-6 mb-6">
            {/* Original Visualization */}
          <div className={`${(accessTypeLabel === "Grey Box" || accessTypeLabel === "White Box") ? 'w-1/2' : 'w-full'}`}>
            {selectedMetricForAnalysis.metric_type.toLowerCase() === "quantitative" ? (
              // Quantitative Metric Visualization - supports all output types
              <div className="bg-white border border-purple-300 rounded-2xl p-4 shadow-sm h-full">
                <h3 className="text-lg font-semibold text-gray-800 mb-4">Performance Analysis</h3>

                {/* Info section for bar chart data */}
                {!outputError && !selectedMetricForAnalysis.output?.confusion_matrix &&
                 detectOutputType(selectedMetricForAnalysis.output) === 'grouped_comparison' && chartData.length > 0 && (
                  <div className="mb-6 p-4 bg-gradient-to-r from-purple-50 to-blue-50 border-purple-200 rounded-lg">
                    <div className="flex justify-between items-start">
                      <div>
                        {/* Group Values */}
                        <div className="space-y-2">
                          {chartData.map((item, index) => (
                            <div key={index} className="flex items-center gap-3">
                              <div className="flex items-center">
                                <div
                                  className="w-3 h-3 rounded-full mr-2"
                                  style={{ backgroundColor: '#D263EB' }}
                                />
                                <span className="text-sm font-medium text-gray-700">{item.name}:</span>
                              </div>
                              <span className="text-sm text-gray-900 font-semibold">{item.value.toFixed(1)}%</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Threshold Value */}
                      <div className="bg-white border-purple-300 rounded-lg p-3">
                        <h4 className="text-sm font-semibold text-gray-800 mb-1">Metric Threshold:</h4>
                        <div className="text-lg font-bold text-purple-700">
                          {selectedMetricForAnalysis.threshold ? `${selectedMetricForAnalysis.threshold}%` : "5%"}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Use MetricVisualization for all output types */}
                <MetricVisualization
                  output={selectedMetricForAnalysis.output}
                  metricType={selectedMetricForAnalysis.name || 'accuracy'}
                  threshold={selectedMetricForAnalysis.threshold}
                  targetFeature={selectedMetricForAnalysis.target_features}
                  chartData={chartData}
                  showTitle={false}
                />
              </div>
            ) : selectedMetricForAnalysis.metric_type.toLowerCase() === "qualitative" &&
              selectedMetricForAnalysis.scale_points ? (
              // Qualitative Scale Visualization
              <div className="bg-white border border-pink-300 rounded-2xl p-4 shadow-sm h-full">
                <h3 className="text-lg font-semibold text-gray-800 mb-4">Performance Analysis</h3>
                
                {outputError ? (
                  // Error message when output can't be calculated
                  <div className="flex flex-col items-center justify-center h-64 text-center">
                    <div className="text-5xl mb-4">⚠️</div>
                    <p className="text-lg font-medium text-gray-700 mb-2">Unable to Calculate Metric</p>
                    <p className="text-sm text-gray-500">Sorry, we can't calculate the metric right now.</p>
                  </div>
                ) : (
                  <div className="relative w-full">

                    {/* Scale points */}
                    <div className="flex justify-between mt-4 relative">
                      {/* Scale visualization */}
                      {(() => {
                        let scalePointsArray = [];
                        if (Array.isArray(selectedMetricForAnalysis.scale_points)) {
                          scalePointsArray = [...selectedMetricForAnalysis.scale_points].sort((a, b) => a.value - b.value);
                        } else if (typeof selectedMetricForAnalysis.scale_points === 'object') {
                          scalePointsArray = Object.entries(selectedMetricForAnalysis.scale_points)
                            .sort((a, b) => a[1] - b[1])
                            .map(([label, value]) => ({ label, value }));
                        }

                        if (scalePointsArray.length > 0) {
                          return (
                            <div className="text-center w-full px-4 py-2">
                              <div className="relative flex flex-col items-center">
                                
                                {/* Gradient Connecting Line - Centered on the circles */}
                                <div 
                                  className="absolute top-7 h-3 bg-gradient-to-r from-purple-200 to-purple-400 rounded-full"
                                  style={{ 
                                    width: `calc(100% - ${100 / scalePointsArray.length}%)`,
                                    left: `${50 / scalePointsArray.length}%` 
                                  }}
                                />

                                <div className="relative w-full flex items-start justify-between">
                                  {scalePointsArray.map((point, index) => {
                                    const isThreshold = String(point.label) === String(selectedMetricForAnalysis.threshold);
                                    const isOutput = String(point.label) === String(selectedMetricForAnalysis.output?.satisfaction_level || "");

                                    return (
                                      <div key={index} className="flex-1 flex flex-col items-center z-10">
                                        
                                        {/* Threshold Label ABOVE */}
                                        <div className="min-h-[24px] mb-1">
                                          {isThreshold && (
                                            <span className="block text-base uppercase tracking-tighter text-purple-600 font-black">
                                              Threshold
                                            </span>
                                          )}
                                        </div>

                                        {/* Circle Badge */}
                                        <div className={`w-10 h-10 rounded-full text-white text-sm font-bold flex items-center justify-center transition-all duration-300 ring-4 ring-white shadow-base border-3 border-purple-100 ${
                                          isOutput 
                                            ? 'bg-pink-600 scale-125 shadow-pink-200 ring-pink-100' 
                                            : isThreshold 
                                              ? 'bg-purple-400 text-purple-900' 
                                              : 'bg-purple-500'
                                        }`}>
                                          {index + 1}
                                        </div>
                                        
                                        {/* Label Text BELOW */}
                                        <div className="mt-4 min-h-[40px]">
                                          <div className={`text-base font-medium leading-tight ${isOutput ? 'text-pink-700' : 'text-gray-700'}`}>
                                            {point.label}
                                          </div>
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            </div>
                          );
                        }
                      })()}
                    </div>

                    {/* Threshold Check Details */}
                    {(() => {
                      const threshold = selectedMetricForAnalysis.threshold;
                      const outputLevel = selectedMetricForAnalysis.output?.satisfaction_level;

                      // Build scale lookup for position comparison
                      let scaleMap = {};
                      if (Array.isArray(selectedMetricForAnalysis.scale_points)) {
                        selectedMetricForAnalysis.scale_points.forEach(p => { scaleMap[String(p.label)] = p.value; });
                      } else if (typeof selectedMetricForAnalysis.scale_points === 'object') {
                        Object.entries(selectedMetricForAnalysis.scale_points).forEach(([label, value]) => { scaleMap[String(label)] = value; });
                      }

                      const thresholdValue = scaleMap[String(threshold)];
                      const outputValue = outputLevel ? scaleMap[String(outputLevel)] : null;

                      let meetsThreshold = null;
                      if (thresholdValue != null && outputValue != null) {
                        meetsThreshold = outputValue >= thresholdValue;
                      }

                      return (
                        <div className="mt-6 space-y-2">
                          <div className="flex text-gray-700">
                            <h4 className="text-md font-semibold text-gray-800">Threshold: </h4>
                            <h4 className="text-md px-1">{threshold || 'Not set'}</h4>
                          </div>
                          {outputLevel && (
                            <div className="flex text-gray-700">
                              <h4 className="text-md font-semibold text-gray-800">Output: </h4>
                              <h4 className="text-md px-1">{outputLevel}</h4>
                            </div>
                          )}
                          {meetsThreshold !== null && (
                            <div className={`mt-3 p-3 rounded-lg border-2 ${
                              meetsThreshold
                                ? 'bg-green-50 border-green-200'
                                : 'bg-red-50 border-red-200'
                            }`}>
                              <p className={`text-sm font-semibold ${meetsThreshold ? 'text-green-700' : 'text-red-700'}`}>
                                {meetsThreshold
                                  ? `✓ Output "${outputLevel}" meets or exceeds the threshold "${threshold}"`
                                  : `✗ Output "${outputLevel}" does not meet the threshold "${threshold}"`
                                }
                              </p>
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-gray-500 italic">No visualization available for this metric.</div>
            )}
          </div>

            {/* Output Evaluation Bar Chart - Always reserve space for Grey/White Box */}
            {(accessTypeLabel === "Grey Box" || accessTypeLabel === "White Box") && (
              <div className="w-1/2">
                <div className="bg-white border border-purple-300 rounded-2xl p-4 shadow-sm h-full">
                  <h3 className="text-lg font-semibold text-gray-800 mb-2">Further Analysis</h3>
                  <h4 className="text-md font-semibold text-purple-700 mb-4">
                    Output Evaluation
                  </h4>
                  
                  {hasCurrentOutputEvaluation ? (
                    <>
                      {/* Output Evaluation Bar Chart - Show when evaluation completed */}
                      <div className="mb-6">
                        <ResponsiveContainer width="100%" height={200}>
                          <BarChart
                            data={[
                              { name: 'Yes', value: getCurrentOutcomeData()?.summary?.yes || 0, fill: '#10b981' },
                              { name: 'No', value: getCurrentOutcomeData()?.summary?.no || 0, fill: '#ef4444' },
                              { name: 'Maybe', value: getCurrentOutcomeData()?.summary?.maybe || 0, fill: '#f59e0b' },
                              { name: 'Not Evaluated', value: getCurrentOutcomeData()?.summary?.notEvaluated || 0, fill: '#6b7280' }
                            ]}
                            margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
                          >
                            <XAxis dataKey="name" />
                            <YAxis />
                            <Bar dataKey="value" radius={[4, 4, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>

                      {/* Output Evaluation Summary */}
                      <div className="grid grid-cols-2 gap-4">
                        <div className="text-center">
                          <div className="text-2xl font-bold text-green-600">
                            {getCurrentOutcomeData()?.summary?.yes || 0}
                          </div>
                          <div className="text-sm text-gray-600">Yes</div>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold text-red-600">
                            {getCurrentOutcomeData()?.summary?.no || 0}
                          </div>
                          <div className="text-sm text-gray-600">No</div>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold text-yellow-600">
                            {getCurrentOutcomeData()?.summary?.maybe || 0}
                          </div>
                          <div className="text-sm text-gray-600">Maybe</div>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold text-gray-600">
                            {getCurrentOutcomeData()?.summary?.notEvaluated || 0}
                          </div>
                          <div className="text-sm text-gray-600">Not Evaluated</div>
                        </div>
                      </div>
                    </>
                  ) : (
                    /* Empty state - reserved space */
                    <div className="flex flex-col items-center justify-center h-64 text-center text-gray-400">
                      <div className="text-4xl mb-4">📊</div>
                      <p className="text-lg font-medium mb-2">No Output Evaluation Yet</p>
                      <p className="text-sm mb-4">Perform outcome evaluation to see results for this metric</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
          )}

          {/* Notes */}
          <div className="mb-6">
            <h3 className="text-lg font-semibold text-gray-800 mb-3">Feedback and Justification *</h3>
            <textarea
              value={notes}
              onChange={(e) => handleNotesChange(e.target.value)}
              onBlur={handleNotesBlur}
              disabled={isReadOnly}
              className={`w-full h-32 p-4 bg-white border rounded-lg disabled:cursor-not-allowed transition-colors ${
                touched.notes && validationErrors.notes
                  ? 'border-red-500 focus:border-red-500 focus:ring-red-200'
                  : 'border-gray-300 focus:border-purple-400'
              }`}
              placeholder="Feedback and Justification..."
            />
            {touched.notes && validationErrors.notes && (
              <p className="text-sm text-red-600 mt-1">{validationErrors.notes}</p>
            )}
          </div>

          {/* Recommendation */}
          <div className="mb-6">
            <div className="flex items-center gap-6">
              <h3 className="text-lg font-semibold text-gray-800">Recommendation: *</h3>
              <div className="flex gap-4">
                {["Pass", "Fail", "Inconclusive"].map(opt => (
                  <label key={opt} className="flex items-center gap-2">
                    <span className="font-medium">{opt}</span>
                    <input
                      type="radio"
                      name="recommendation"
                      value={opt}
                      checked={recommendation === opt}
                      onChange={(e) => handleRecommendationChange(e.target.value)}
                      disabled={isReadOnly}
                      className="h-6 w-6 disabled:cursor-not-allowed"
                    />
                  </label>
                ))}
              </div>
            </div>
            {touched.recommendation && validationErrors.recommendation && (
              <p className="text-sm text-red-600 mt-2">{validationErrors.recommendation}</p>
            )}
          </div>

          {/* Buttons */}
          <div className="flex justify-between">
            <button
              onClick={() => {
                setSelectedMetricForAnalysis(null); 
                setSelectedEvent("overview");
                setActiveTab('overview')
              }}
              disabled={isSaving || !selectedMetricForAnalysis || isReadOnly}
              className={`flex items-center gap-2 px-4 py-2 rounded-full font-semibold border-2 border-purple-200 transition-colors ${isSaving || !selectedMetricForAnalysis || isReadOnly
                  ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
                  : 'hover:bg-purple-200'
                }`}
            >
              Return to Overview without Saving
            </button>
            <button
              onClick={handleSaveAnalysis}
              disabled={isSaving || !selectedMetricForAnalysis || isReadOnly}
              className={`flex items-center gap-2 px-4 py-2 rounded-full font-semibold border-2 border-purple-200 transition-colors ${isSaving || !selectedMetricForAnalysis || isReadOnly
                  ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
                  : 'bg-purple-100 hover:bg-purple-200'
                }`}
            >
              {isSaving ? 'Saving...' : 'Save Analysis'}
            </button>

          </div>
        </div>
      </div>
    </div>
  );
  // Get access type label
  const accessTypeLabel = getAccessTypeLabel(accessType);

  // Determine help context based on current view state
  const getHelpContext = () => {
    if (showOutputEvaluation) {
      return { activeView: 'outputEvaluation' };
    }
    if (activeTab === 'detail-analysis' && selectedMetricForAnalysis) {
      return { activeView: 'analysis' };
    }
    return {};
  };

  return (
    <div className="min-h-screen bg-purple-to-br from-purple-50 to-pink-50 p-4">
      <Navigation
        hasSelectedMetrics={true}
        hasEvaluated={hasEvaluated}
        currentPage={currentPage}
        hasEnteredAudit={true}
        isReadOnly={isReadOnly}
        onNavigate={(pageId) => handlers.handleNavigation(pageId, navigate, auditData.events)}
        helpContext={getHelpContext()}
      />

      {/* Purpose Box - Added as per wireframe */}
      {isVisible &&
       <div className="mb-6 bg-b7efff rounded-2xl border-2 border-purple-300 p-6 shadow-md" data-onboarding="purpose-box">
        <div className="flex items-start">
          <div>
            <p className="text-gray-700">
              {getPurposeBoxMessage()}
            </p>
            </div>
        </div>
      </div>
     }
      <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg w-full">
        {/* Conditional rendering - OutputEvaluationScreen replaces content when shown */}
        {showOutputEvaluation ? (
          <OutputEvaluationScreen
            key={selectedMetricForAnalysis?.metric_id || selectedMetricForAnalysis?.id}
            auditId={auditId}
            selectedMetricForAnalysis={selectedMetricForAnalysis}
            onClose={() => {
              setShowOutputEvaluation(false);
              setIsVisible(true);
            }}
            onComplete={handleOutputEvaluationComplete}
            onEvaluationStart={handleOutputEvaluationStart}
            onStartEvaluation={(files) => {
              // console.log('Start evaluation with files', files);
            }}
            isReadOnly={isReadOnly}
            initialEvaluationData={getCurrentOutcomeData()}
            onSave={auditDataAPI.reloadData}
            applicationModels={currentAudit?.application_models || []}
          />
        ) : (
          <>
            {activeTab === 'overview' && renderOverviewContent()}
            {activeTab === 'detail-analysis' && renderDetailAnalysisContent()}
            <div className="flex gap-4 justify-between pt-6" data-onboarding="navigation-buttons">
              <button
                onClick={() => handlers.handleBackwardNavigation('performance', navigate)}
                className="flex items-center gap-2 hover:bg-purple-200 px-4 py-3 rounded-full text-base font-semibold transition-colors border-2 border-purple-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-purple-100">
                <ArrowLeft/>Back to Audit Criteria
              </button>
              <button
                onClick={() => handlers.handleNavigation("audit-outcome", navigate, auditData.events)}
                disabled={!hasEvaluated}
                className="flex items-center gap-2 hover:bg-purple-200 px-4 py-3 rounded-full text-base font-semibold transition-colors border-2 border-purple-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-purple-100">
                Next to Audit Recommendation <ArrowRight/>
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
export default PerformanceAnalysis;