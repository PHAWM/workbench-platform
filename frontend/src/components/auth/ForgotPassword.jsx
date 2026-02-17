import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import logo from "src/FullLogoTransparent.png"
import { authAPI } from '../../api/apiService';

const ForgotPassword = () => {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError('');
    setSuccessMessage('');

    try {
      await authAPI.passwordRecovery(email);
      setSuccessMessage('Password reset link has been sent to your email. Please check your inbox.');
      setEmail('');
    } catch (error) {
      console.error('Password recovery error:', error);
      setError(error.message || 'Failed to send password reset email. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg text-center w-800px h-800px flex items-center justify-center">
        <div className="w-full flex-col flex items-center">
          <img src={logo} alt="Logo" width="600px"/>
          <h1 className="mb-4">Forgot Password</h1>
          <p className="text-gray-600 mb-6">Enter your email address and we'll send you a link to reset your password.</p>

          <form onSubmit={handleSubmit} className="w-full">
            <div className="mb-4">
              <input
                type="email"
                name="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email"
                required
                disabled={isSubmitting}
                className="w-half bg-purple text-center px-2 py-3 border-2 border-purple-200 rounded-full focus:border-purple-400 focus:outline-none transition-colors"
              />
            </div>

            {error && (
              <div className="mb-4 text-red-600">
                {error}
              </div>
            )}

            {successMessage && (
              <div className="mb-4 text-green-600 font-semibold">
                {successMessage}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="bg-purple-100 hover:bg-purple-200 px-8 py-2 rounded-full text-base font-semibold transition-colors border-2 border-purple-200"
            >
              {isSubmitting ? 'Sending...' : 'Send Reset Link'}
            </button>

            <p
              style={{ marginTop: '12px', textDecoration: 'underline', cursor: 'pointer' }}
              onClick={() => navigate('/login')}
            >
              Back to Login
            </p>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ForgotPassword;
