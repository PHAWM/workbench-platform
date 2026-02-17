import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import logo from "src/FullLogoTransparent.png"
import { authAPI } from '../../api/apiService';

const EmailVerification = () => {
  const [searchParams] = useSearchParams();
  const [verificationStatus, setVerificationStatus] = useState('verifying'); // verifying, success, error
  const [message, setMessage] = useState('Verifying your email...');
  const navigate = useNavigate();

  useEffect(() => {
    const verifyEmail = async () => {
      const token = searchParams.get('token');

      if (!token) {
        setVerificationStatus('error');
        setMessage('Invalid verification link. No token provided.');
        return;
      }

      try {
        await authAPI.verifyEmail(token);
        setVerificationStatus('success');
        setMessage('Email verified successfully! You can now log in.');
        // Redirect to login after 3 seconds
        setTimeout(() => {
          navigate('/login');
        }, 3000);
      } catch (error) {
        console.error('Verification error:', error);
        setVerificationStatus('error');
        setMessage(error.message || 'Email verification failed. The link may be expired or invalid.');
      }
    };

    verifyEmail();
  }, [searchParams, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg text-center w-800px h-800px flex items-center justify-center">
        <div className="w-full flex-col flex items-center">
          <img src={logo} alt="Logo" width="600px"/>
          <h1 className="mb-4">Email Verification</h1>

          <div className="w-full flex flex-col items-center">
            {verificationStatus === 'verifying' && (
              <div className="mb-4">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-400 mx-auto mb-4"></div>
                <p className="text-gray-700">{message}</p>
              </div>
            )}

            {verificationStatus === 'success' && (
              <div className="mb-4">
                <div className="text-green-600 text-5xl mb-4">✓</div>
                <p className="text-green-600 font-semibold text-lg">{message}</p>
                <p className="text-gray-600 mt-2">Redirecting to login...</p>
              </div>
            )}

            {verificationStatus === 'error' && (
              <div className="mb-4">
                <div className="text-red-600 text-5xl mb-4">✗</div>
                <p className="text-red-600 font-semibold text-lg">{message}</p>
                <button
                  onClick={() => navigate('/login')}
                  className="mt-4 bg-purple-100 hover:bg-purple-200 px-8 py-2 rounded-full text-base font-semibold transition-colors border-2 border-purple-200"
                >
                  Go to Login
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default EmailVerification;
