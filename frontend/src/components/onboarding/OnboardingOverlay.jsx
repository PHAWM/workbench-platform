import React from 'react';
import Joyride from 'react-joyride';
import { useOnboarding } from '../../context/onboardingContext';

// Custom tooltip component for better styling
const CustomTooltip = ({
  index,
  step,
  backProps,
  closeProps,
  primaryProps,
  tooltipProps,
  isLastStep,
  size
}) => (
  <div
    {...tooltipProps}
    className="bg-white rounded-2xl shadow-2xl border-2 border-purple-200 p-6 max-w-xl"
    style={{ width: step.styles?.options?.width || 500 }}
  >
    {/* Step indicator */}
    <div className="flex items-center justify-between mb-4">
      <span className="text-base font-medium text-purple-600">
        Step {index + 1} of {size}
      </span>
      <div className="flex gap-1.5">
        {Array.from({ length: size }).map((_, i) => (
          <div
            key={i}
            className={`w-2 h-2 rounded-full transition-colors ${
              i === index
                ? 'bg-purple-600'
                : i < index
                ? 'bg-purple-300'
                : 'bg-gray-200'
            }`}
          />
        ))}
      </div>
    </div>

    {/* Content */}
    <div className="mb-6">
      {step.title && (
        <h3 className="text-lg font-semibold text-gray-800 mb-2">
          {step.title}
        </h3>
      )}
      <p className="text-gray-600 text-base leading-relaxed">
        {step.content}
      </p>
    </div>

    {/* Navigation buttons */}
    <div className="flex items-center justify-between">
      <button
        {...closeProps}
        className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
      >
        Skip tutorial
      </button>

      <div className="flex gap-2">
        {index > 0 && (
          <button
            {...backProps}
            className="flex items-center gap-1 px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back
          </button>
        )}
        <button
          {...primaryProps}
          className="flex items-center gap-1 px-4 py-2 text-sm font-medium text-white bg-purple-600 rounded-full hover:bg-purple-700 transition-colors"
        >
          {isLastStep ? 'Get Started' : 'Next'}
          {!isLastStep && (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          )}
        </button>
      </div>
    </div>
  </div>
);

const OnboardingOverlay = () => {
  const {
    isOnboardingActive,
    steps,
    stepIndex,
    handleJoyrideCallback
  } = useOnboarding();

  // Custom callback to handle joyride events
  const handleCallback = (data) => {
    const { action, status, type } = data;

    // Call the context handler
    handleJoyrideCallback(data);

  };

  if (!isOnboardingActive || steps.length === 0) return null;

  return (
    <Joyride
      steps={steps}
      stepIndex={stepIndex}
      run={isOnboardingActive}
      continuous
      showProgress={false}
      showSkipButton
      scrollToFirstStep
      scrollOffset={100}
      spotlightPadding={8}
      disableOverlayClose
      disableCloseOnEsc={false}
      callback={handleCallback}
      tooltipComponent={CustomTooltip}
      floaterProps={{
        disableAnimation: false,
        styles: {
          floater: {
            filter: 'none'
          }
        }
      }}
      styles={{
        options: {
          zIndex: 10000,
          primaryColor: '#9333ea',
          overlayColor: 'rgba(0, 0, 0, 0.6)'
        },
        spotlight: {
          borderRadius: 8,
          border: '3px solid #D263EB'
        },
        overlay: {
          backgroundColor: 'rgba(0, 0, 0, 0.6)'
        },
        buttonClose: {
          display: 'none' // Hide default close button, we use custom
        },
        buttonBack: {
          display: 'none' // Hide default back button, we use custom
        },
        buttonNext: {
          display: 'none' // Hide default next button, we use custom
        },
        buttonSkip: {
          display: 'none' // Hide default skip button, we use custom
        }
      }}
      locale={{
        back: 'Back',
        close: 'Skip tutorial',
        last: 'Get Started',
        next: 'Next',
        skip: 'Skip tutorial'
      }}
    />
  );
};

export default OnboardingOverlay;
