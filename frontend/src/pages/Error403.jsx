import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle } from 'lucide-react';

const Error403 = () => {
  const navigate = useNavigate();
  const [countdown, setCountdown] = useState(5);

  useEffect(() => {
    // Countdown timer
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          navigate('/login');
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [navigate]);

  const handleLoginRedirect = () => {
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-red-50 to-orange-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl border-2 border-red-200 p-8 shadow-lg max-w-md w-full text-center">
        <div className="flex justify-center mb-6">
          <div className="bg-red-100 rounded-full p-4">
            <AlertTriangle className="w-16 h-16 text-red-600" />
          </div>
        </div>

        <h1 className="text-4xl font-bold text-gray-900 mb-2">403</h1>
        <h2 className="text-2xl font-semibold text-gray-800 mb-4">Access Forbidden</h2>

        <p className="text-gray-600 mb-6">
          You don't have permission to access this resource. This could be because:
        </p>

        <ul className="text-left text-gray-600 mb-6 space-y-2">
          <li className="flex items-start">
            <span className="text-red-500 mr-2">•</span>
            <span>Your session has expired</span>
          </li>
          <li className="flex items-start">
            <span className="text-red-500 mr-2">•</span>
            <span>You don't have the required permissions</span>
          </li>
          <li className="flex items-start">
            <span className="text-red-500 mr-2">•</span>
            <span>Your authentication token is invalid</span>
          </li>
        </ul>

        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <p className="text-sm text-red-800">
            Redirecting to login page in <span className="font-bold text-xl">{countdown}</span> seconds...
          </p>
        </div>

        <button
          onClick={handleLoginRedirect}
          className="w-full bg-red-600 hover:bg-red-700 text-white font-semibold py-3 px-6 rounded-full transition-colors"
        >
          Go to Login Now
        </button>
      </div>
    </div>
  );
};

export default Error403;
