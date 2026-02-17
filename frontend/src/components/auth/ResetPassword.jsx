import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import logo from "src/FullLogoTransparent.png"
import { authAPI } from '../../api/apiService';

const ResetPassword = () => {
  const [searchParams] = useSearchParams();
  const [formData, setFormData] = useState({
    password: '',
    confirmPassword: '',
  });
  const [token, setToken] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const tokenFromUrl = searchParams.get('token');
    if (!tokenFromUrl) {
      setError('Invalid reset link. No token provided.');
    } else {
      setToken(tokenFromUrl);
    }
  }, [searchParams]);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
    if (error) setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError('');

    // Validation
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      setIsSubmitting(false);
      return;
    }

    if (formData.password.length < 8) {
      setError('Password must be at least 8 characters long');
      setIsSubmitting(false);
      return;
    }

    try {
      await authAPI.resetPassword({
        token: token,
        new_password: formData.password,
      });

      // Password reset successful, redirect to login
      navigate('/login', {
        state: { message: 'Password reset successfully! You can now log in with your new password.' }
      });
    } catch (error) {
      console.error('Reset password error:', error);
      setError(error.message || 'Failed to reset password. The link may be expired or invalid.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!token && error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg text-center w-800px h-800px flex items-center justify-center">
          <div className="w-full flex-col flex items-center">
            <img src={logo} alt="Logo" width="600px"/>
            <h1 className="mb-4">Invalid Reset Link</h1>
            <div className="text-red-600 text-5xl mb-4">✗</div>
            <p className="text-red-600 font-semibold text-lg mb-4">{error}</p>
            <button
              onClick={() => navigate('/login')}
              className="bg-purple-100 hover:bg-purple-200 px-8 py-2 rounded-full text-base font-semibold transition-colors border-2 border-purple-200"
            >
              Go to Login
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg text-center w-800px h-800px flex items-center justify-center">
        <div className="w-full flex-col flex items-center">
          <img src={logo} alt="Logo" width="600px"/>
          <h1 className="mb-4">Reset Password</h1>
          <p className="text-gray-700 mb-4">
            Please enter your new password.
          </p>
          <form onSubmit={handleSubmit} className="w-full">
            <div className="mb-4">
              <input
                type="password"
                name="password"
                value={formData.password}
                onChange={handleChange}
                placeholder="New Password"
                required
                disabled={isSubmitting}
                className="w-half bg-purple text-center px-2 py-3 border-2 border-purple-200 rounded-full focus:border-purple-400 focus:outline-none transition-colors"
              />
            </div>
            <div className="mb-4">
              <input
                type="password"
                name="confirmPassword"
                value={formData.confirmPassword}
                onChange={handleChange}
                placeholder="Confirm New Password"
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
            <button
              type="submit"
              disabled={isSubmitting}
              className="bg-purple-100 hover:bg-purple-200 px-8 py-2 rounded-full text-base font-semibold transition-colors border-2 border-purple-200"
            >
              {isSubmitting ? 'Resetting...' : 'Reset Password'}
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

export default ResetPassword;
