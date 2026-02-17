import React from 'react';
import { AlertCircle, RefreshCw, X } from 'lucide-react';

const ErrorMessage = ({ 
  message, 
  onRetry, 
  onDismiss, 
  type = 'error' 
}) => {
  const typeStyles = {
    error: 'bg-red-50 border-red-200 text-red-800',
    warning: 'bg-yellow-50 border-yellow-200 text-yellow-800',
    info: 'bg-blue-50 border-blue-200 text-blue-800'
  };

  const iconColor = {
    error: 'text-red-500',
    warning: 'text-yellow-500',
    info: 'text-blue-500'
  };

  return (
    <div className={`border rounded-lg p-4 mb-4 ${typeStyles[type]}`}>
      <div className="flex items-start">
        <AlertCircle className={`w-5 h-5 ${iconColor[type]} mt-0.5 mr-3 flex-shrink-0`} />
        <div className="flex-1">
          <p className="text-sm font-medium">{message}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className={`mt-2 inline-flex items-center text-sm font-medium hover:underline ${iconColor[type]}`}
            >
              <RefreshCw className="w-4 h-4 mr-1" />
              Try Again
            </button>
          )}
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className={`ml-2 ${iconColor[type]} hover:opacity-75`}
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
};

export default ErrorMessage;