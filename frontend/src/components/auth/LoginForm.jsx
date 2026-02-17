import React, { useState } from 'react';
import { useAuth } from './AuthContext';
import { useNavigate } from 'react-router-dom';
import logo from "src/FullLogoTransparent.png"

const LoginForm = () => {
  const [formData, setFormData] = useState({
    username: '', // Changed from email to username
    password: '',
  });
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

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
    const result = await login(formData);

    if (result.success) {
    navigate('/dashboard');
    } else {
    setError(result.error);
    }
    // navigate('/dashboard');
    setIsSubmitting(false);
  };

  return (
    // Centering container
    <div className="min-h-screen flex items-center justify-center">
      <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg text-center w-800px h-800px flex items-center justify-center">
        <div className="w-full flex-col flex items-center">
        <img src={logo} alt="Logo" width="600px"/>
        <h1 className="mb-4">Login</h1>
        <form onSubmit={handleSubmit} className="w-full">
          <div className="mb-4">
            <input
              type="text"
              name="username" 
              value={formData.username}
              onChange={handleChange}
              placeholder="Email"
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
          {error && (
            <div className="mb-4">
              {error}
            </div>
          )}
          <button
            type="submit"
            disabled={isSubmitting}
            className="bg-purple-100 hover:bg-purple-200 px-8 py-2 rounded-full text-base font-semibold transition-colors border-2 border-purple-200"
          >
            {isSubmitting ? 'Logging in...' : 'Log in'}
          </button>
          {/* Add the link to the forgot password page here! */}
          <p
            style={{ marginTop: '12px', textDecoration: 'underline', cursor: 'pointer' }}
            onClick={() => navigate('/forgot-password')}
          >
            Forgot password?
          </p>
        </form>
        </div>
      </div>
    </div>
  );
};

export default LoginForm;