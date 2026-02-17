/**
 * Handlers for Dashboard page
 * Contains navigation and audit selection functions
 */

/**
 * Transform API audit data to dashboard display format
 * @param {Array} audits - Raw audit data from API
 * @returns {Array} Transformed audit data for display
 */
export const transformAuditData = (audits) => {
  if (!audits || !Array.isArray(audits)) return [];

  return audits.map((audit) => ({
    id: audit.audit_id,
    title: audit.audited_system_name,
    instigatorName: audit.display_name,
    auditStatus: parseInt(audit.completion_percentage),
    auditRecomendationText: audit.recommendation,
    action: "Enter Audit",
  }));
};

/**
 * Creates handlers for dashboard page
 * @param {Object} params - Parameters for creating handlers
 * @returns {Object} Handler functions
 */
export const createDashboardHandlers = ({
  setCurrentPage,
  setSelectedAuditId,
  navigate,
  auditId,
  startOnboardingFromDashboard
}) => {
  /**
   * Handle navigation to different pages
   * @param {string} pageId - Target page ID
   */
  const handleNavigation = (pageId) => {
    setCurrentPage(pageId);
    if (pageId === 'dashboard') {
      navigate('/dashboard');
    } else if (pageId === 'profile') {
      navigate('/profile');
    } else {
      navigate(`/${pageId}/${auditId}`);
    }
  };

  /**
   * Handle audit card click
   * @param {string} audit_id - Audit ID to select
   * @param {string} auditStatus - Current audit status
   */
  const handleAuditClick = (audit_id, auditStatus) => {
    setSelectedAuditId(audit_id);
    // Only start onboarding if the audit is not submitted
    if (auditStatus !== "Submitted") {
      startOnboardingFromDashboard?.();
    }
    // Navigate to AI application page
    setCurrentPage('ai-application');
    navigate(`/ai-application/${audit_id}`);
  };

  return {
    handleNavigation,
    handleAuditClick
  };
};

/**
 * Get status badge class based on audit status
 * @param {number} status - Completion percentage
 * @returns {string} Tailwind CSS classes
 */
export const getStatusBadgeClass = (status) => {
  if (status === 100) return 'bg-green-100 text-green-800';
  if (status >= 50) return 'bg-yellow-100 text-yellow-800';
  return 'bg-gray-100 text-gray-800';
};

/**
 * Get status text based on audit status
 * @param {number} status - Completion percentage
 * @returns {string} Status text
 */
export const getStatusText = (status) => {
  if (status === 100) return 'Completed';
  if (status > 0) return 'In Progress';
  return 'Not Started';
};
