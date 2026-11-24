import React, { createContext, useContext, useState, useEffect } from 'react';
import { TokenStorage } from '../../api/apiService';
import { resolveTenantId, getTenantFromToken } from '../../utils/tenant';

// Your actual API endpoints
const API_BASE_URL = import.meta.env.VITE_API_URL;

// const API_BASE_URL = 'http://<address_to_VM>/api/v1'; // V>
const LOGIN_ENDPOINT = `${API_BASE_URL}/login/access-token`;
const USER_PROFILE_ENDPOINT = `${API_BASE_URL}/users/me`; // Updated endpoint

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const login = async (credentials) => {
    setLoading(true);
    try {
      // Try form data format first (common for FastAPI login endpoints)
      const formData = new FormData();
      formData.append('username', credentials.username);
      formData.append('password', credentials.password);

      // X-Tenant-ID is only required on the login request.
      // After login the issued JWT embeds the tenant (tid claim) and all
      // subsequent requests are routed automatically via the Bearer token.
      const tenantId = resolveTenantId();
      const loginHeaders = {};
      if (tenantId) {
        loginHeaders['X-Tenant-ID'] = tenantId;
      }

      const response = await fetch(LOGIN_ENDPOINT, {
        method: 'POST',
        headers: loginHeaders,
        body: formData,
      });

      const data = await response.json();

      if (response.ok) {
        // Based on your API response format
        const { access_token, token_type } = data;

        // Use TokenStorage instead of direct sessionStorage
        TokenStorage.setToken(access_token);
        sessionStorage.setItem('tokenType', token_type);

        // Persist tenant ID so other parts of the app can read it if needed.
        // Not required for API routing (the JWT tid claim handles that), but
        // useful for display or debug purposes.
        if (tenantId) {
          TokenStorage.setTenantId(tenantId);
        }

        // Now get user profile
        const userResponse = await fetch(USER_PROFILE_ENDPOINT, {
          headers: {
            'Authorization': `Bearer ${access_token}`,
          },
        });

        if (userResponse.ok) {
          const userData = await userResponse.json();
          setUser(userData);
          setIsAuthenticated(true);

          return { success: true, data: { token: access_token, user: userData } };
        } else {
          TokenStorage.clearToken();
          sessionStorage.removeItem('tokenType');
          return { success: false, error: 'Failed to get user profile' };
        }
      } else {
        return { 
          success: false, 
          error: data.detail || data.message || 'Login failed' 
        };
      }
    } catch (error) {
      console.error('Login error:', error);
      return { 
        success: false, 
        error: 'Network error. Please try again.' 
      };
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    TokenStorage.clearToken();
    TokenStorage.clearTenantId();
    sessionStorage.removeItem('tokenType');
    setUser(null);
    setIsAuthenticated(false);
  };

  useEffect(() => {
    const checkAuthStatus = async () => {
      const token = TokenStorage.getToken();

      // If the logged-in user's JWT tenant doesn't match the deployment's
      // tenant (user navigated /workbench/tenant_1 → /workbench/tenant_2),
      // force a logout so we don't render the wrong tenant's data.
      const deploymentTenant = resolveTenantId();
      const tokenTenant = getTenantFromToken(token);
      if (deploymentTenant && tokenTenant && deploymentTenant !== tokenTenant) {
        TokenStorage.clearToken();
        TokenStorage.clearTenantId();
        sessionStorage.removeItem('tokenType');
        setUser(null);
        setIsAuthenticated(false);
        setLoading(false);
        return;
      }

      if (token) {
        try {
          const response = await fetch(USER_PROFILE_ENDPOINT, {
            headers: {
              'Authorization': `Bearer ${token}`,
            },
          });

          if (response.ok) {
            const userData = await response.json();
            setUser(userData);
            setIsAuthenticated(true);
          } else {
            TokenStorage.clearToken();
            sessionStorage.removeItem('tokenType');
          }
        } catch (error) {
          console.error('Auth check failed:', error);
          TokenStorage.clearToken();
          sessionStorage.removeItem('tokenType');
        }
      }

      setLoading(false);
    };

    checkAuthStatus();
  }, []);

  const value = {
    user,
    isAuthenticated,
    loading,
    login,
    logout,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
