/**
 * Handlers for AuditOutcome page
 * Contains submission and recommendation functions
 */

import { evaluationAPI, adminAPI } from '../api/apiService';

/**
 * Map recommendation string to numeric value for API
 * @param {string} recommendation - Recommendation string ('pass', 'fail', 'inconclusive')
 * @returns {number} Recommendation value (1=Inconclusive, 2=Fail, 3=Pass)
 */
export const getRecommendationValue = (recommendation) => {
  switch (recommendation?.toLowerCase()) {
    case 'inconclusive': return 1;
    case 'fail': return 2;
    case 'pass': return 3;
    default: return 1; // Default to inconclusive
  }
};

/**
 * Map recommendation number to string for display
 * @param {number} value - Recommendation value
 * @returns {string} Recommendation string
 */
export const getRecommendationFromValue = (value) => {
  switch (value) {
    case 1: return 'inconclusive';
    case 2: return 'fail';
    case 3: return 'pass';
    default: return 'inconclusive';
  }
};

/**
 * Submit audit outcome to the server
 * @param {string} auditId - Audit ID
 * @param {string} overallRecommendation - Overall recommendation string
 * @param {string} feedback - Feedback notes
 * @returns {Promise<Object>} Result object with success status
 */
export const submitAuditOutcome = async (auditId, overallRecommendation, feedback) => {
  try {
    const submitData = {
      recommendation: getRecommendationValue(overallRecommendation),
      notes: feedback
    };

    // console.log('Submitting audit data:', submitData);
    await evaluationAPI.submitAudit(auditId, submitData);
    // Stamp submitted_at and compute duration_seconds on the backend
    await adminAPI.submitAuditTiming(auditId).catch(() => {});

    return { success: true };
  } catch (error) {
    console.error('Error submitting audit:', error);
    return { success: false, error };
  }
};

/**
 * Creates handlers for audit outcome page
 * @param {Object} params - Parameters for creating handlers
 * @returns {Object} Handler functions
 */
export const createAuditOutcomeHandlers = ({
  setShowConfirmModal,
  setIsSubmitted,
  setExpandedItems,
  auditId,
  overallRecommendation,
  feedback,
  toast,
  isAuditReadOnly
}) => {
  /**
   * Toggle item expansion in the accordion
   * @param {string} itemId - Item ID to toggle
   */
  const toggleExpansion = (itemId) => {
    setExpandedItems(prev => ({
      ...prev,
      [itemId]: !prev[itemId]
    }));
  };

  /**
   * Show confirmation modal before submission
   */
  const handleSubmitClick = () => {
    setShowConfirmModal(true);
  };

  /**
   * Confirm and submit the audit outcome
   */
  const handleConfirmSubmit = async () => {
    const result = await submitAuditOutcome(auditId, overallRecommendation, feedback);

    if (result.success) {
      setIsSubmitted(true);
      setShowConfirmModal(false);
      toast.success('Audit outcome submitted successfully!');
      isAuditReadOnly("Submitted");
      window.location.href = (import.meta.env.BASE_URL || '/') + 'dashboard';
    } else {
      toast.error('Error submitting audit. Please try again.');
    }
  };

  /**
   * Cancel submission and close modal
   */
  const handleGoBack = () => {
    setShowConfirmModal(false);
  };

  return {
    toggleExpansion,
    handleSubmitClick,
    handleConfirmSubmit,
    handleGoBack
  };
};

/**
 * Calculate overall recommendation based on criteria evaluations
 * @param {Array} criteriaEvaluations - Array of evaluation objects
 * @returns {string} Overall recommendation ('pass', 'fail', 'inconclusive')
 */
export const calculateOverallRecommendation = (criteriaEvaluations) => {
  if (!criteriaEvaluations || criteriaEvaluations.length === 0) {
    return 'inconclusive';
  }

  const hasAnyFail = criteriaEvaluations.some(e => e.recommendation === 'fail');
  const allPass = criteriaEvaluations.every(e => e.recommendation === 'pass');

  if (hasAnyFail) return 'fail';
  if (allPass) return 'pass';
  return 'inconclusive';
};
