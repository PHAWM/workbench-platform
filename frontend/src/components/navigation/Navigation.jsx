import React, { useState, useEffect } from 'react';
import { ChevronDown, HelpCircle, User } from 'lucide-react';
import { useParams, useLocation } from 'react-router-dom';

// Documentation URL mapping based on current page/route
const DOCS_BASE_URL = import.meta.env.VITE_DOCS_URL || 'http://127.0.0.1:8080';

const getHelpUrl = (pathname, helpContext = {}) => {
  const { activeForm, activeView } = helpContext;

  // Check for specific form contexts first
  if (pathname.includes('/audit-criteria')) {
    // Creating new event
    if (activeForm === 'createEvent') {
      return `${DOCS_BASE_URL}/frontend/audit_criteria/create_new_event/`;
    }
    // Creating qualitative metric
    if (activeForm === 'qualitative') {
      return `${DOCS_BASE_URL}/frontend/audit_criteria/create_new_metric_qual/`;
    }
    // Creating quantitative metric
    if (activeForm === 'quantitative') {
      return `${DOCS_BASE_URL}/frontend/audit_criteria/create_new_metric_quant/`;
    }
    // Default audit criteria page
    return `${DOCS_BASE_URL}/frontend/audit_criteria/audit_criteria/`;
  }

  if (pathname.includes('/performance')) {
    // Specific metric analysis view
    if (activeView === 'analysis') {
      return `${DOCS_BASE_URL}/frontend/performance_analysis/performance_analysis/`;
    }
    // Output evaluation view
    if (activeView === 'outputEvaluation') {
      return `${DOCS_BASE_URL}/frontend/performance_analysis/output_evaluation/`;
    }
    // Default performance overview
    return `${DOCS_BASE_URL}/frontend/performance_analysis/performance_analysis_overview/`;
  }

  // Extract the page type from the pathname
  if (pathname.includes('/dashboard') || pathname === '/') {
    return `${DOCS_BASE_URL}/frontend/dashboard/dashboard/`;
  }
  if (pathname.includes('/ai-application')) {
    return `${DOCS_BASE_URL}/frontend/ai_application/ai_application_overview/`;
  }
  if (pathname.includes('/audit-outcome')) {
    return `${DOCS_BASE_URL}/frontend/audit_recommedation/audit_recommendation/`;
  }
  if (pathname.includes('/profile')) {
    return `${DOCS_BASE_URL}/frontend/`;
  }
  // Default to main frontend docs
  return `${DOCS_BASE_URL}/frontend/`;
};

export const Navigation = ({
  hasSelectedMetrics,
  hasEvaluated,
  currentPage,
  onNavigate,
  hasEnteredAudit = false,  // New prop to track if user has entered an audit
  isReadOnly = false,  // When audit is completed/submitted, enable all navigation items
  helpContext = {}  // Context for help URL (e.g., { activeForm: 'qualitative' } or { activeView: 'analysis' })
}) => {
  const { auditId } = useParams();
  const location = useLocation();

  // State to track persisted audit state from localStorage
  const [persistedState, setPersistedState] = useState({
    hasSelectedMetrics: false,
    hasEvaluated: false
  });

  // Load persisted state from localStorage on mount, when auditId changes, or when currentPage changes
  useEffect(() => {
    if (!auditId) return;

    const loadPersistedState = () => {
      try {
        const stored = localStorage.getItem(`audit_state_${auditId}`);
        if (stored) {
          const parsed = JSON.parse(stored);
          setPersistedState(parsed);
        }
      } catch (err) {
        console.error('Failed to load persisted audit state in Navigation:', err);
      }
    };

    loadPersistedState();

    // Listen for storage events (from other tabs)
    const handleStorageChange = (e) => {
      if (e.key === `audit_state_${auditId}`) {
        loadPersistedState();
      }
    };

    // Listen for custom auditStateChange events (from same tab)
    const handleAuditStateChange = (e) => {
      if (e.detail?.auditId === auditId && e.detail?.state) {
        setPersistedState(e.detail.state);
      }
    };

    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('auditStateChange', handleAuditStateChange);
    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('auditStateChange', handleAuditStateChange);
    };
  }, [auditId, currentPage]);

  // Use props if explicitly provided (including false), otherwise fall back to persisted state
  const effectiveHasSelectedMetrics = hasSelectedMetrics !== undefined ? hasSelectedMetrics : persistedState.hasSelectedMetrics;
  const effectiveHasEvaluated = hasEvaluated !== undefined ? hasEvaluated : persistedState.hasEvaluated;

  const navigationItems = [
    { id: 'dashboard', label: 'Dashboard', enabled: true },
    { id: 'ai-application', label: 'AI Application Overview', enabled: isReadOnly || hasEnteredAudit },
    { id: 'audit-criteria', label: 'Audit Criteria', enabled: isReadOnly || hasEnteredAudit },
    { id: 'performance', label: 'Performance Analysis', enabled: isReadOnly || effectiveHasSelectedMetrics },
    { id: 'audit-outcome', label: 'Audit Recommendation', enabled: isReadOnly || effectiveHasEvaluated }
  ];

  const handleNavClick = (itemId, enabled) => {
    if (enabled && onNavigate) {
      onNavigate(itemId);
    }
  };

  const handleHelpClick = () => {
    const helpUrl = getHelpUrl(location.pathname, helpContext);
    window.open(helpUrl, '_blank', 'noopener,noreferrer');
  };

  const getCurrentPageIndex = () => {
    return navigationItems.findIndex(nav => nav.id === currentPage);
  };

  const getNavItemStyles = (item, index) => {
    const isActive = currentPage === item.id;
    const isEnabled = item.enabled;
    const currentPageIndex = getCurrentPageIndex();
    
    if (isActive) {
      return 'bg-purple-100 hover:bg-purple-200 px-4 py-2 rounded-full text-base font-bold transition-colors border-3 border-black cursor-pointer';
    }
    
    if (!isEnabled) {
      return 'px-4 py-2 bg-gray-200 rounded-full border border-gray-300 shadow-sm text-gray-500 cursor-not-allowed';
    }

    // For completed/accessible pages (at or before current page)
    if (index <= currentPageIndex) {
      return 'bg-purple-100 hover:bg-purple-200 px-4 py-2 rounded-full text-base font-medium transition-colors border border-black cursor-pointer';
    }
    
    // For future pages (after current page) that are enabled
    return 'bg-purple-100 hover:bg-purple-100 px-4 py-2 rounded-full text-base font-medium transition-colors border border-black cursor-pointer';
  };

  const getChevronStyles = (index) => {
    const nextItem = navigationItems[index + 1];
    if (!nextItem) return 'w-4 h-4 rotate-[-90deg] text-gray-400';
    
    return `w-4 h-4 rotate-[-90deg] ${nextItem.enabled ? 'text-gray-400' : 'text-gray-300'}`;
  };

  return (
    <div className="mb-6 flex items-center gap-2 text-sm" data-onboarding="top-navigation">
      {navigationItems.map((item, index) => (
        <React.Fragment key={item.id}>
          <span 
            className={getNavItemStyles(item, index)}
            onClick={() => handleNavClick(item.id, item.enabled)}
          >
            {item.label}
          </span>
          {index < navigationItems.length - 1 && (
            <ChevronDown className={getChevronStyles(index)} />
          )}
        </React.Fragment>
      ))}
      
      <div className="ml-auto flex items-center gap-2">
        <HelpCircle
          className="w-6 h-6 text-gray-500 hover:text-gray-700 cursor-pointer transition-colors"
          onClick={handleHelpClick}
          title="Open documentation"
        />
        <div
          className="w-8 h-8 bg-black rounded-full flex items-center justify-center hover:bg-gray-800 cursor-pointer transition-colors"
          onClick={() => onNavigate && onNavigate('profile')}
        >
          <User className="w-5 h-5 text-white" />
        </div>
      </div>
    </div>
  );
};

export default Navigation;