import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import logo from "src/FullLogoTransparent.png"
import { authAPI } from '../../api/apiService';

const RegistrationForm = () => {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    full_name: '',
  });
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
    if (error) setError('');
    if (successMessage) setSuccessMessage('');
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
      const normalizedEmail = formData.email.trim().toLowerCase();
      await authAPI.signup({
        username: normalizedEmail,
        email: normalizedEmail,
        password: formData.password,
        full_name: formData.full_name,
      });

      // Registration successful, show verification message
      setSuccessMessage('Registration successful! Please check your email to verify your account before logging in.');
      // Clear form
      setFormData({
        email: '',
        password: '',
        confirmPassword: '',
        full_name: '',
      });
    } catch (error) {
      console.error('Registration error:', error);
      setError(error.message || 'Registration failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg text-center w-800px h-800px flex items-center justify-center">
        <div className="w-full flex-col flex items-center">
          <img src={logo} alt="Logo" width="600px"/>
          <h1 className="mb-4">Register</h1>
          <form onSubmit={handleSubmit} className="w-full">
            <div className="mb-4">
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                placeholder="Email"
                required
                disabled={isSubmitting}
                className="w-half bg-purple text-center px-2 py-3 border-2 border-purple-200 rounded-full focus:border-purple-400 focus:outline-none transition-colors"
              />
            </div>
            <div className="mb-4">
              <input
                type="text"
                name="full_name"
                value={formData.full_name}
                onChange={handleChange}
                placeholder="Full Name"
                required
                disabled={isSubmitting}
                className="w-half bg-purple text-center px-2 py-3 border-2 border-purple-200 rounded-full focus:border-purple-400 focus:outline-none transition-colors"
              />
            </div>
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
              {isSubmitting ? 'Registering...' : 'Register'}
            </button>
            <p
              style={{ marginTop: '12px', textDecoration: 'underline', cursor: 'pointer' }}
              onClick={() => navigate('/login')}
            >
              Already have an account? Log in
            </p>
          </form>
        </div>
      </div>
    </div>
  );
};

export default RegistrationForm;
