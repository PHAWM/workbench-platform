import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { tenantPath } from '../../utils/tenant';
import logo from "src/FullLogoTransparent.png"
import { authAPI } from '../../api/apiService';

const AcceptInvite = () => {
  const [searchParams] = useSearchParams();
  const [formData, setFormData] = useState({
    password: '',
    confirmPassword: '',
  });
  const [inviteData, setInviteData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const validateInvite = async () => {
      const token = searchParams.get('token');

      if (!token) {
        setError('Invalid invitation link. No token provided.');
        setLoading(false);
        return;
      }

      try {
        const data = await authAPI.validateInvite(token);
        setInviteData({ token, ...data });
      } catch (error) {
        console.error('Validation error:', error);
        setError(error.message || 'Invalid or expired invitation link.');
      } finally {
        setLoading(false);
      }
    };

    validateInvite();
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
      await authAPI.setPasswordWithInvite(inviteData.token, formData.password);
      // Invitation accepted successfully, redirect to login
      navigate(tenantPath('/login'), {
        state: { message: 'Account created successfully! You can now log in.' }
      });
    } catch (error) {
      console.error('Accept invite error:', error);
      setError(error.message || 'Failed to accept invitation');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg text-center w-800px h-800px flex items-center justify-center">
          <div className="w-full flex-col flex items-center">
            <img src={logo} alt="Logo" width="600px"/>
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-400 mx-auto mb-4"></div>
            <p className="text-gray-700">Validating invitation...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error && !inviteData) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg text-center w-800px h-800px flex items-center justify-center">
          <div className="w-full flex-col flex items-center">
            <img src={logo} alt="Logo" width="600px"/>
            <h1 className="mb-4">Invalid Invitation</h1>
            <div className="text-red-600 text-5xl mb-4">✗</div>
            <p className="text-red-600 font-semibold text-lg mb-4">{error}</p>
            <button
              onClick={() => navigate(tenantPath('/login'))}
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
          <h1 className="mb-4">Accept Invitation</h1>
          {inviteData && (
            <p className="text-gray-700 mb-4">
              Welcome! Please create a password for your account.
            </p>
          )}
          <form onSubmit={handleSubmit} className="w-full">
            <div className="mb-4">
              <input
                type="password"
                name="password"
                value={formData.password}
                onChange={handleChange}
                placeholder="Password"
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
                placeholder="Confirm Password"
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
              {isSubmitting ? 'Creating Account...' : 'Create Account'}
            </button>
            <p
              style={{ marginTop: '12px', textDecoration: 'underline', cursor: 'pointer' }}
              onClick={() => navigate(tenantPath('/login'))}
            >
              Already have an account? Log in
            </p>
          </form>
        </div>
      </div>
    </div>
  );
};

export default AcceptInvite;
