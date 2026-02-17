import React from 'react';
import { Loader2 } from 'lucide-react';

/**
 * Full-screen saving overlay component
 * Shows a centered loading spinner with a message while saving
 */
const SavingOverlay = ({
  isVisible = false,
  message = 'Saving...',
  subMessage = 'Please wait while we save your changes.'
}) => {
  if (!isVisible) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl p-8 shadow-xl flex flex-col items-center max-w-md mx-4">
        <Loader2 className="w-12 h-12 animate-spin text-purple-600 mb-4" />
        <h3 className="text-xl font-semibold text-gray-800 mb-2">{message}</h3>
        <p className="text-gray-600 text-center">{subMessage}</p>
      </div>
    </div>
  );
};

export default SavingOverlay;
