import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';

// Onboarding steps configuration for each page (react-joyride format)
const ONBOARDING_STEPS = {
  'ai-application': [
    {
      target: 'body',
      content: 'The purpose of this page is to provide information on the AI Application you are asked to audit and the auditing context. Once you have read through the information, you can move forward to the Audit Criteria page.',
      title: 'Welcome to the AI Application Overview',
      placement: 'center',
      disableBeacon: true,
      styles: {
        options: {
          width: 600
        }
      }
    },
    {
      target: '[data-onboarding="purpose-box"]',
      content: 'This box provides a summary of what you can do on this page. It will guide you through the purpose and available actions for each stage of the audit process.',
      title: 'Page Purpose',
      placement: 'bottom',
      disableBeacon: true
    },
    {
      target: '[data-onboarding="top-navigation"]',
      content: 'Use this navigation bar to move between different stages of the audit process. The Help icon opens context-sensitive documentation, and the Profile icon lets you access your profile settings.',
      title: 'Top Navigation',
      placement: 'bottom',
      disableBeacon: true
    },
    {
      target: '[data-onboarding="sidebar"]',
      content: 'Use this sidebar to navigate between different sections of information about the AI application. Click on any section to expand and view its details.',
      title: 'Navigation Sidebar',
      placement: 'right',
      disableBeacon: true
    },
    {
      target: '[data-onboarding="content"]',
      content: 'This area displays detailed information about the AI application, including its summary, audit details, development pipeline, and legal framework.',
      title: 'Application Details',
      placement: 'left',
      disableBeacon: true
    },
    {
      target: '[data-onboarding="navigation-buttons"]',
      content: 'Use these buttons to navigate between pages. Click "Next to Audit Criteria" when you\'re ready to proceed to selecting your audit criteria.',
      title: 'Navigation Controls',
      placement: 'top',
      disableBeacon: true
    }
  ],
  'audit-criteria': [
    {
      target: 'body',
      content: 'The purpose of this page is to choose the audit criteria for your audit. There might be some existing audit criteria provided by the audit instigators, which you may choose to use in your audit. For these, you can adjust the Event Values - valence, likelihood and magnitude - of the event and the threshold of the metric. You can also create your own audit criteria by creating your own event and/ or metric. For these, you can Edit all fields. Once you have chosen which audit criteria to use in the audit by clicking the corresponding checkbox(es), you can move forward to the Performance Analysis page.',
      title: 'Audit Criteria Selection',
      placement: 'center',
      disableBeacon: true,
      styles: {
        options: {
          width: 600
        }
      }
    },
    {
      target: '[data-onboarding="purpose-box"]',
      content: 'This box provides a summary of what you can do on this page. It will guide you through the purpose and available actions for each stage of the audit process.',
      title: 'Page Purpose',
      placement: 'bottom',
      disableBeacon: true
    },
    {
      target: '[data-onboarding="top-navigation"]',
      content: 'Use this navigation bar to move between different stages of the audit process. The Help icon opens context-sensitive documentation, and the Profile icon lets you access your profile settings.',
      title: 'Top Navigation',
      placement: 'bottom',
      disableBeacon: true
    },
    {
      target: '[data-onboarding="create-buttons"]',
      content: 'Use these buttons to create new events or metrics. You can customise your audit criteria to match your specific auditing needs.',
      title: 'Create New Criteria',
      placement: 'bottom',
      disableBeacon: true
    },
    {
      target: '[data-onboarding="first-event"]',
      content: 'Each event contains associated metrics. Click the checkbox next to a metric to include it in your audit. You must set thresholds for selected metrics before proceeding. User-created events appear at the top of the list.',
      title: 'Events and Metrics',
      placement: 'bottom',
      disableBeacon: true
    },
    {
      target: '[data-onboarding="navigation-buttons"]',
      content: 'Once you have selected at least one metric and set its threshold, click "Next to Performance Analysis" to continue.',
      title: 'Proceed to Analysis',
      placement: 'top',
      disableBeacon: true
    }
  ],
  'performance': [
    {
      target: 'body',
      content: 'This page allows you to analyse the AI application\'s performance against your selected audit criteria and make recommendations.',
      title: 'Performance Analysis',
      placement: 'center',
      disableBeacon: true,
      styles: {
        options: {
          width: 600
        }
      }
    },
    {
      target: '[data-onboarding="purpose-box"]',
      content: 'This box provides a summary of what you can do on this page. It will guide you through the purpose and available actions for each stage of the audit process.',
      title: 'Page Purpose',
      placement: 'bottom',
      disableBeacon: true
    },
    {
      target: '[data-onboarding="top-navigation"]',
      content: 'Use this navigation bar to move between different stages of the audit process. The Help icon opens context-sensitive documentation, and the Profile icon lets you access your profile settings.',
      title: 'Top Navigation',
      placement: 'bottom',
      disableBeacon: true
    },
    {
      target: '[data-onboarding="sidebar"]',
      content: 'Use this sidebar to navigate between different metrics. Click "Overview" to see all metrics, or select a specific metric to analyse it in detail.',
      title: 'Metrics Overview',
      placement: 'right',
      disableBeacon: true
    },
    {
      target: '[data-onboarding="first-metric"]',
      content: 'Click "Perform Analysis" on any metric to view detailed performance data, charts, and make your recommendation (Pass, Fail, or Inconclusive).',
      title: 'Perform Analysis',
      placement: 'bottom',
      disableBeacon: true
    },
    {
      target: '[data-onboarding="navigation-buttons"]',
      content: 'After analysing all metrics and making recommendations, click "Next to Audit Recommendation" to provide your overall audit outcome recommendation.',
      title: 'Complete Your Analysis',
      placement: 'top',
      disableBeacon: true
    }
  ],
  'audit-outcome': [
    {
      target: 'body',
      content: 'This is the final step where you provide your overall audit recommendation based on all your individual metric analyses.',
      title: 'Audit Recommendation',
      placement: 'center',
      disableBeacon: true,
      styles: {
        options: {
          width: 600
        }
      }
    },
    {
      target: '[data-onboarding="purpose-box"]',
      content: 'This box provides a summary of what you can do on this page. It will guide you through the purpose and available actions for each stage of the audit process.',
      title: 'Page Purpose',
      placement: 'bottom',
      disableBeacon: true
    },
    {
      target: '[data-onboarding="top-navigation"]',
      content: 'Use this navigation bar to move between different stages of the audit process. The Help icon opens context-sensitive documentation, and the Profile icon lets you access your profile settings.',
      title: 'Top Navigation',
      placement: 'bottom',
      disableBeacon: true
    },
    {
      target: '[data-onboarding="criteria-summary"]',
      content: 'Review your recommendations for each audit criterion. Click on any item to expand and see your feedback and justification.',
      title: 'Criteria Summary',
      placement: 'left',
      disableBeacon: true
    },
    {
      target: '[data-onboarding="overall-recommendation"]',
      content: 'Select your overall recommendation (Pass, Fail, or Inconclusive) and provide feedback to justify your decision.',
      title: 'Overall Recommendation',
      placement: 'top',
      disableBeacon: true
    },
    {
      target: '[data-onboarding="submit-button"]',
      content: 'When you\'re ready, click "Submit Audit Recommendation" to finalise and submit your audit. This action cannot be undone.',
      title: 'Submit Your Audit',
      placement: 'top',
      disableBeacon: true
    }
  ]
};

const OnboardingContext = createContext();

export const OnboardingProvider = ({ children }) => {
  const [isOnboardingActive, setIsOnboardingActive] = useState(false);
  const [currentPage, setCurrentPage] = useState(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [hasSeenOnboarding, setHasSeenOnboarding] = useState({});
  const [enteredFromDashboard, setEnteredFromDashboard] = useState(false);

  // Load persisted state from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem('onboarding_state');
      if (stored) {
        const parsed = JSON.parse(stored);
        setHasSeenOnboarding(parsed.hasSeenOnboarding || {});
      }
    } catch (error) {
      console.error('Failed to load onboarding state:', error);
    }
  }, []);

  // Persist state to localStorage
  const persistState = useCallback((newHasSeenOnboarding) => {
    try {
      localStorage.setItem('onboarding_state', JSON.stringify({
        hasSeenOnboarding: newHasSeenOnboarding
      }));
    } catch (error) {
      console.error('Failed to persist onboarding state:', error);
    }
  }, []);

  // Get steps for current page
  const getSteps = useCallback(() => {
    if (!currentPage || !ONBOARDING_STEPS[currentPage]) return [];
    return ONBOARDING_STEPS[currentPage];
  }, [currentPage]);

  // Start onboarding for a specific page
  const startOnboarding = useCallback((page) => {
    if (ONBOARDING_STEPS[page]) {
      setCurrentPage(page);
      setStepIndex(0);
      setIsOnboardingActive(true);
    }
  }, []);

  // Start onboarding from dashboard entry
  const startOnboardingFromDashboard = useCallback(() => {
    setEnteredFromDashboard(true);
  }, []);

  // Check if should show onboarding for a page (called when entering a page)
  const checkAndStartOnboarding = useCallback((page) => {
    if (enteredFromDashboard && !hasSeenOnboarding[page] && ONBOARDING_STEPS[page]) {
      setCurrentPage(page);
      setStepIndex(0);
      setIsOnboardingActive(true);
      return true;
    }
    return false;
  }, [enteredFromDashboard, hasSeenOnboarding]);

  // Handle joyride callback
  const handleJoyrideCallback = useCallback((data) => {
    const { status, index, action, type } = data;
    const finishedStatuses = ['finished', 'skipped'];
    const closeActions = ['skip', 'close'];

    // Check if tour is finished or skipped (either by status or action)
    if (finishedStatuses.includes(status) || closeActions.includes(action)) {
      // Completed or skipped onboarding
      if (currentPage) {
        const newHasSeenOnboarding = {
          ...hasSeenOnboarding,
          [currentPage]: true
        };
        setHasSeenOnboarding(newHasSeenOnboarding);
        persistState(newHasSeenOnboarding);
      }
      setIsOnboardingActive(false);
      setStepIndex(0);
    } else if (type === 'step:after') {
      // Update step index after each step
      if (action === 'next') {
        setStepIndex(index + 1);
      } else if (action === 'prev') {
        setStepIndex(index - 1);
      }
    }
  }, [currentPage, hasSeenOnboarding, persistState]);

  // Skip onboarding
  const skipOnboarding = useCallback(() => {
    if (currentPage) {
      const newHasSeenOnboarding = {
        ...hasSeenOnboarding,
        [currentPage]: true
      };
      setHasSeenOnboarding(newHasSeenOnboarding);
      persistState(newHasSeenOnboarding);
    }
    setIsOnboardingActive(false);
    setStepIndex(0);
  }, [currentPage, hasSeenOnboarding, persistState]);

  // Reset onboarding (for testing or user preference)
  const resetOnboarding = useCallback(() => {
    setHasSeenOnboarding({});
    setEnteredFromDashboard(false);
    persistState({});
  }, [persistState]);

  // End audit session (called when returning to dashboard)
  const endAuditSession = useCallback(() => {
    setEnteredFromDashboard(false);
  }, []);

  const value = {
    // State
    isOnboardingActive,
    currentPage,
    stepIndex,
    hasSeenOnboarding,
    enteredFromDashboard,

    // Computed
    steps: getSteps(),

    // Actions
    startOnboarding,
    startOnboardingFromDashboard,
    checkAndStartOnboarding,
    handleJoyrideCallback,
    skipOnboarding,
    resetOnboarding,
    endAuditSession
  };

  return (
    <OnboardingContext.Provider value={value}>
      {children}
    </OnboardingContext.Provider>
  );
};

export const useOnboarding = () => {
  const context = useContext(OnboardingContext);
  if (!context) {
    throw new Error('useOnboarding must be used within an OnboardingProvider');
  }
  return context;
};

export default OnboardingContext;
