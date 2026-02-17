import React, { useState, useEffect } from 'react';
import { ChevronUp, ChevronDown, ArrowLeft, X } from 'lucide-react';
import { Navigation } from '../components/navigation/Navigation';
import { useParams, useNavigate } from 'react-router-dom';
import { auditOutcomeAPI } from '../api/apiService';
import { createAuditHandlers } from '../handlers/auditHandlers';
import { useAuditData } from '../hooks/useAuditData';
import { isAuditReadOnly } from '../utils/auditUtils';
import { useApi } from '../context/apiContext';
import { useToast } from '../hooks/useToast';
import { useOnboarding } from '../context/onboardingContext';
import { submitAuditOutcome } from '../handlers/auditOutcomeHandlers';

const AuditOutcomeInterface = () => {
  const [currentPage, setCurrentPage] = useState('audit-outcome');
  const { auditId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { checkAndStartOnboarding } = useOnboarding();

  // Get audit status and access type from context
  const { auditStatus, accessType, loadAudit } = useApi();
  const isReadOnly = isAuditReadOnly(auditStatus);

  // Trigger onboarding when entering this page from dashboard
  useEffect(() => {
    checkAndStartOnboarding('audit-outcome');
  }, [checkAndStartOnboarding]);

  const [expandedItems, setExpandedItems] = useState({});
  const [overallRecommendation, setOverallRecommendation] = useState('');
  const [feedback, setFeedback] = useState('');
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [auditItems, setAuditItems] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  
  const auditDataAPI = useAuditData(auditId);
  
  const handlers = createAuditHandlers(
    auditId,
    auditDataAPI.updateState,
    () => {}, // updateModals
    () => {}, // updatePreserved
    auditDataAPI.reloadData,
    [], // availableEntities
    [], // eventCategories
    null, // updateVisibility
    toast // toast for notifications
  );

  // Fetch audit status and access type from context
  useEffect(() => {
    if (auditId) {
      loadAudit(auditId);
    }
  }, [auditId, loadAudit]);

  // Fetch data from APIs
  useEffect(() => {
    const fetchAuditData = async () => {
      try {
        const [auditResponse] = await Promise.all([auditOutcomeAPI.getAuditOutcomeSummary(auditId)])
        setIsLoading(true);
        
        const auditItems = auditResponse.audit_criteria.map((audit, index) => ({
          id: index + 1,
          eventName: audit.event_name,
          metricName: audit.metric_name,
          status: audit.recommendation_text,
          notes: audit.notes
        }));

        const overallRecommendation = auditResponse.recommendation_text;
        const feedback = auditResponse.notes;
        
        setAuditItems(auditItems);
        setOverallRecommendation(overallRecommendation);
        setFeedback(feedback);
        
        setIsLoading(false);
      } catch (error) {
        console.error('Error fetching audit data:', error);
        setIsLoading(false);
      }
    };

    fetchAuditData();
  }, [auditId]);

  const toggleExpansion = (itemId) => {
    setExpandedItems(prev => ({
      ...prev,
      [itemId]: !prev[itemId]
    }));
  };

  const handleSubmitClick = () => {
    setShowConfirmModal(true);
  };

  const handleConfirmSubmit = async () => {
    // Use submitAuditOutcome from handlers
    const result = await submitAuditOutcome(auditId, overallRecommendation, feedback);

    if (result.success) {
      setIsSubmitted(true);
      setShowConfirmModal(false);
      toast.success('Audit outcome submitted successfully!');
      isAuditReadOnly("Submitted");
      // Reset after showing success - force absolute navigation to dashboard
      window.location.href = '/dashboard';
    } else {
      toast.error('Error submitting audit. Please try again.');
    }
  };

  const handleGoBack = () => {
    setShowConfirmModal(false);
  };

  const isSubmitEnabled = overallRecommendation !== '';

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 p-4 flex items-center justify-center">
        {/* <div className="min-h-screen bg-gradient-to-br from-pink-100 via-purple-50 to-pink-100 p-4 flex items-center justify-center"></div> */}
        <div className="text-center">
          <div className="animate-spin w-12 h-12 border-4 border-purple-300 border-purple-600 rounded-full mx-auto mb-4"></div>
          <p className="text-gray-600 font-medium">Loading audit data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-purple-to-br from-purple-50 to-pink-50 p-4">
      {/* Header Navigation */}
        <Navigation
          currentPage={currentPage}
          hasEnteredAudit={true}
          hasEvaluated={auditDataAPI.hasEvaluated || true}
          hasSelectedMetrics={auditDataAPI.hasSelectedMetrics || true}
          isReadOnly={isReadOnly}
          onNavigate={(pageId) => handlers.handleNavigation(pageId, navigate, auditDataAPI.events || [], currentPage)}
        />

        {/* Purpose Box - Added as per wireframe */}
        <div className="mb-6 bg-b7efff rounded-2xl border-2 border-purple-300 p-6 shadow-md" data-onboarding="purpose-box">
           <div className="flex items-start">
              <div>
                 <p className="text-gray-700">
                This is the Audit Recommendation page. On this page you can view the recommendations and associated feedback and justifications you made for each of your Audit Criteria. Based on these, on the bottom of this page you can make an overall recommendation for how you think the AI Application performs against the collective audit criteria. Once you have done this, click the Submit Audit Recommendation button to finish the audit and return to the Dashboard.
                </p>
              </div>
            </div>
          </div>

        <div className="flex-1">
         {/* Main Content */}
         
          <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg w-full">
          {/* Audit Items Container with Border */}
            <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 w-full" data-onboarding="criteria-summary">

              <div className="space-y-4">
                {auditItems.map((item) => (
                  <div key={item.id}>
                    <div
                      className="bg-purple from-purple-50 to-blue-50 backdrop-blur-sm border-2 border-purple-200 rounded-3xl p-6 shadow-sm"
                      onClick={() => toggleExpansion(item.id)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          {item.status === 'cannot be calculated with provided data' ? (
                            <span className="text-gray-700 font-medium text-base">
                              <strong>{item.eventName}</strong> : <strong>{item.metricName}</strong> : {item.status}
                            </span>
                          ) : (
                            <span className="text-gray-700 font-medium text-base">
                              <strong>{item.eventName}</strong> : <strong>{item.metricName}</strong>
                            </span> 
                          )}
                        </div>
                        <div className="flex items-center space-x-4">
                          {item.status !== 'cannot be calculated with provided data' && (
                            <span className="text-gray-700 font-medium text-base">
                              <strong>{item.status}</strong>
                            </span>
                          )}
                          {expandedItems[item.id] ? (
                          
                            <ChevronUp className="w-5 h-5 text-gray-600" />
                          ) : (
                            <ChevronDown className="w-5 h-5 text-gray-600" />
                          )}
                        </div>
                      </div>

                    {/* inside list */}
                   
                    {expandedItems[item.id] && (
                      <div className="bg-white rounded-2xl border-2 border-gray-300 rounded-lg p-5 ml-4"
                        onClick={(e) => e.stopPropagation()} // Prevents click from bubbling up
                      >
                        <p className="text-gray-600 text-sm">
                          <span className="font-medium"></span> 
                          {item.notes ? (
                            <span className="text-gray-800">{item.notes}</span>
                          ) : (
                            <span className="text-gray-400 italic">Feedback and Justification...</span>
                          )}
                        </p>
                      </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
        
          </div>

         {/* Overall Recommendation */}
          <div className="mt-8 flex items-center justify-between" data-onboarding="overall-recommendation">
            <div className="flex items-center space-x-8">
              <span className="text-xl font-semibold text-gray-800">Overall Recommendation</span>
              
              <div className="flex items-center space-x-6">
                <label className={`flex items-center space-x-2 ${isReadOnly ? 'cursor-not-allowed' : 'cursor-pointer'}`}>
                  <span className={`text-gray-700 font-medium`}>Pass</span>
                  <div className="relative">
                    <input
                      type="radio"
                      name="recommendation"
                      value="Pass"
                      checked={overallRecommendation === 'Pass'}
                      onChange={(e) => setOverallRecommendation(e.target.value)}
                      disabled={isReadOnly}
                      className="w-5 h-5 text-pink-500 border-2 border-gray-400 focus:ring-pink-500 focus:ring-2  disabled:cursor-not-allowed"
                    />
                  </div>
                  
                </label>

                <label className={`flex items-center space-x-2 ${isReadOnly ? 'cursor-not-allowed' : 'cursor-pointer'}`}>
                  <span className={`text-gray-700 font-medium`}>Fail</span>
                  <div className="relative">
                    <input
                      type="radio"
                      name="recommendation"
                      value="Fail"
                      checked={overallRecommendation === 'Fail'}
                      onChange={(e) => setOverallRecommendation(e.target.value)}
                      disabled={isReadOnly}
                      className="w-5 h-5 text-pink-500 border-2 border-gray-400 focus:ring-pink-500 focus:ring-2  disabled:cursor-not-allowed"
                    />
                  </div>
                    </label>

                <label className={`flex items-center space-x-2 ${isReadOnly ? 'cursor-not-allowed' : 'cursor-pointer'}`}>
                  <span className={`text-gray-700 font-medium `}>Inconclusive</span>
                  <div className="relative">
                    <input
                      type="radio"
                      name="recommendation"
                      value="Inconclusive"
                      checked={overallRecommendation === 'Inconclusive'}
                      onChange={(e) => setOverallRecommendation(e.target.value)}
                      disabled={isReadOnly}
                      className="w-5 h-5 text-pink-500 border-2 border-gray-400 focus:ring-pink-500 focus:ring-2  disabled:cursor-not-allowed"
                    />
                  </div>
                  
                </label>
              </div>
            </div>

            
          </div>

          {/* Feedback Section */}
          <div className="mb-8 mt-4">
            <h3 className="text-xl font-semibold text-gray-800 mb-4"> Overall Feedback and Justification</h3>
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="Overall Feedback and Justification..."
              disabled={isReadOnly}
              className="w-full h-32 p-4 bg-white text-gray-700 placeholder-gray-400 focus:outline-none resize-none rounded-xl shadow-sm disabled:cursor-not-allowed mb-4" />
            
            <div className="flex justify-between">
              <button
                onClick={() => navigate(`/performance/${auditId}`)}
                className="flex items-center gap-2 hover:bg-purple-200 px-4 py-3 rounded-full text-base font-semibold transition-colors border-2 border-purple-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-purple-100">
                <ArrowLeft/>Back to Performance Analysis
              </button>
              <button
                disabled={!isSubmitEnabled || isReadOnly}
                className='flex items-center gap-2 bg-purple-100 hover:bg-purple-200 px-6 py-3 rounded-full text-base font-semibold transition-colors border-2 border-purple-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-purple-100'
                onClick={handleSubmitClick}
                data-onboarding="submit-button"
              >
                Submit Audit Recommendation
              </button>
            </div>
            
          </div>

        </div>
  

      {/* Confirmation Modal */}
      {showConfirmModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl border-2 border-purple-200 p-8 max-w-md w-full shadow-lg">
            {/* Header */}
            <div className="flex justify-between items-start mb-6">
              <div className="flex-1">
                <h2 className="text-lg font-semibold text-purple-800 mb-2">
                  Have you finished auditing this AI application?
                </h2>
                <p className="text-gray-600 text-sm leading-relaxed">
                  Once you submit the audit outcome, you will not be able to make changes.
                </p>
              </div>
              <button
                onClick={handleGoBack}
                className="ml-4 text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Actions */}
            <div className="flex gap-4 mt-6">
              <button
                onClick={handleGoBack}
                className="flex-1 px-5 py-2.5 border-2 border-gray-300 text-gray-700 rounded-full font-medium hover:bg-gray-50 transition-all duration-200"
              >
                No, go back
              </button>
              <button
                onClick={handleConfirmSubmit}
                className="flex-1 px-5 py-2.5 bg-purple-100 border-2 border-purple-200 text-purple-800 font-semibold rounded-full hover:bg-purple-200 transition-all duration-200"
              >
                Yes, submit my audit
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
    </div>
  );
};

export default AuditOutcomeInterface;