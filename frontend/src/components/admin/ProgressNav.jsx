import React from 'react';
import { Check } from 'lucide-react';

// Left-rail progress indicator for the admin setup wizard.
// Vertical list of pages with checkmarks for completed, an emphasized current
// page, and muted/struck-through entries for pages skipped (e.g. black-box).
//
// Props:
//   steps        [{ id, title, description }]
//   currentStep  the active step id
//   stepOrder    ordered array of step ids (drives completed vs upcoming)
//   skippedIds   Set of step ids that are skipped for the current config
//   onSelect(id) optional — allow jumping to a completed page
const ProgressNav = ({ steps, currentStep, stepOrder, skippedIds = new Set(), onSelect, allowAll = false }) => {
  const currentIdx = stepOrder.indexOf(currentStep);

  return (
    <nav className="space-y-1">
      {steps.map((step) => {
        const stepIdx = stepOrder.indexOf(step.id);
        const isSkipped = skippedIds.has(step.id);
        const isComplete = !isSkipped && stepIdx < currentIdx;
        const isCurrent = step.id === currentStep;
        // In edit mode (allowAll) any non-skipped page is reachable; otherwise only completed ones.
        const clickable = !isSkipped && (allowAll || isComplete) && typeof onSelect === 'function';

        return (
          <button
            key={step.id}
            type="button"
            disabled={!clickable}
            onClick={() => clickable && onSelect(step.id)}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-colors ${
              isCurrent
                ? 'bg-purple-50 border border-purple-200'
                : clickable
                ? 'hover:bg-gray-50 border border-transparent'
                : 'border border-transparent'
            }`}
          >
            {/* Marker */}
            <span
              className={`flex items-center justify-center w-7 h-7 rounded-full text-xs font-semibold shrink-0 ${
                isSkipped
                  ? 'bg-gray-100 text-gray-300'
                  : isComplete
                  ? 'bg-green-500 text-white'
                  : isCurrent
                  ? 'bg-purple-600 text-white'
                  : 'bg-gray-200 text-gray-500'
              }`}
            >
              {isSkipped ? '–' : isComplete ? <Check className="w-4 h-4" /> : step.id}
            </span>

            {/* Labels */}
            <span className="min-w-0">
              <span
                className={`block text-sm font-medium truncate ${
                  isSkipped
                    ? 'text-gray-300 line-through'
                    : isCurrent
                    ? 'text-purple-800'
                    : 'text-gray-700'
                }`}
              >
                {step.title}
              </span>
              {step.description && (
                <span className="block text-xs text-gray-400 truncate">{step.description}</span>
              )}
            </span>
          </button>
        );
      })}
    </nav>
  );
};

export default ProgressNav;
