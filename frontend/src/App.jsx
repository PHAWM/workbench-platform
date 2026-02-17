import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './components/auth/AuthContext';
import { ApiProvider } from './context/apiContext';
import { OnboardingProvider } from './context/onboardingContext';
import { ToastProvider } from './hooks/useToast';
import { TooltipProvider } from '@radix-ui/react-tooltip';
import OnboardingOverlay from './components/onboarding/OnboardingOverlay';

// Import your pages
import LoginForm from './components/auth/LoginForm';
import ProtectedRoute from './components/auth/ProtectedRoute';
import LoginRedirect from './components/auth/LoginRedirect';
import Dashboard from './pages/Dashboard';
import AIApplicationOverview from './pages/AIApplicationOverview';
import AuditCriteriaDashboard from './pages/AuditCriteria';
import PerformanceAnalysis from './pages/PerformanceAnalysis';
import AuditOutcomeInterface from './pages/AuditOutcome';
import ProfileInterface from './pages/AuditorProfile';
import Error403 from './pages/Error403';
import AcceptInvite from './components/auth/AcceptInvite';
// import RegistrationForm from './components/auth/RegistrationForm';

import ForgotPassword from './components/auth/ForgotPassword';
import ResetPassword from './components/auth/ResetPassword';

import './App.css';

function App() {
  return (
    <BrowserRouter>
      <TooltipProvider delayDuration={300} skipDelayDuration={500}>
        <AuthProvider>
          <ApiProvider>
            <OnboardingProvider>
              <ToastProvider>
                <div className="App">
                  <OnboardingOverlay />
                  <Routes>
                    <Route path="/" element={<LoginRedirect><LoginForm /></LoginRedirect>} />
                    <Route path="/login" element={<LoginForm />} />
                    <Route path="/forgot-password" element={<ForgotPassword />} />
                    <Route path="/reset-password" element={<ResetPassword />} />
                    {/* <Route path="/register" element={<RegistrationForm />} /> */}
                    <Route path="/accept-invite" element={<AcceptInvite />} />
                    
                    <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                    <Route path="/ai-application/:auditId" element={<ProtectedRoute><AIApplicationOverview /></ProtectedRoute>} />
                    <Route path="/audit-criteria/:auditId" element={<ProtectedRoute><AuditCriteriaDashboard /></ProtectedRoute>} />
                    <Route path="/performance/:auditId" element={<ProtectedRoute><PerformanceAnalysis /></ProtectedRoute>} />
                    <Route path="/audit-outcome/:auditId" element={<ProtectedRoute><AuditOutcomeInterface/></ProtectedRoute>} />
                    <Route path="/profile" element={<ProtectedRoute><ProfileInterface /></ProtectedRoute>} />
                    
                    {/* Fallback routes without auditId - redirect to dashboard */}
                    <Route path="/403" element={<Error403 />} />
                    <Route path="/ai-application" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                    <Route path="/audit-criteria" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                    <Route path="/performance" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                    <Route path="/audit-outcome" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                  </Routes>
                </div>
              </ToastProvider>
            </OnboardingProvider>
          </ApiProvider>
        </AuthProvider>
      </TooltipProvider>


    </BrowserRouter>
  );
}



export default App;