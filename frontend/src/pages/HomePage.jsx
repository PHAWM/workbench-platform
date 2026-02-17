import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

const HomePage = () => {
  const { isAuthenticated, user } = useAuth();

  return (
    <div style={{ 
      padding: '40px 20px', 
      textAlign: 'center',
      maxWidth: '600px',
      margin: '0 auto'
    }}>
      <h1 style={{ marginBottom: '20px' }}>Welcome to My App</h1>
      
      {isAuthenticated ? (
        <div>
          <p style={{ marginBottom: '20px' }}>
            Hello, {user?.name || user?.username}! You are logged in.
          </p>
          <Link 
            to="/dashboard"
            style={{
              display: 'inline-block',
              padding: '12px 24px',
              backgroundColor: '#007bff',
              color: 'white',
              textDecoration: 'none',
              borderRadius: '4px'
            }}
          >
            Go to Dashboard
          </Link>
        </div>
      ) : (
        <div>
          <p style={{ marginBottom: '20px' }}>
            Please log in to access your dashboard.
          </p>
          <Link 
            to="/login"
            style={{
              display: 'inline-block',
              padding: '12px 24px',
              backgroundColor: '#28a745',
              color: 'white',
              textDecoration: 'none',
              borderRadius: '4px'
            }}
          >
            Login
          </Link>
        </div>
      )}
    </div>
  );
};

export default HomePage;