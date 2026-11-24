import { useState, useEffect } from 'react';
import { Navigation } from '../components/navigation/Navigation';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../components/auth/AuthContext';
import { tenantPath } from '../utils/tenant';
import { useOnboarding } from '../context/onboardingContext';
import { User, Settings } from 'lucide-react';
import {
  validatePasswordData,
  loadUserProfile as loadUserProfileHandler,
  updateUserProfile,
  changePassword
} from '../handlers/auditorProfileHandlers';
import { demoAPI } from '../api/apiService';

const ProfileInterface = () => {
  const [profile, setProfile] = useState({
    full_name: '',
    username: '',
    email: '',
    gender: '',
    ethnicity: '',
    country: '',
    organisation: ''
  });

  const [isLoading, setIsLoading] = useState(false);
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [message, setMessage] = useState('');
  const { logout, user } = useAuth();
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [passwordData, setPasswordData] = useState({
    oldPassword: '',
    newPassword: '',
    confirmPassword: ''
  });
  const [passwordError, setPasswordError] = useState('');
  const [showPasswordSuccess, setShowPasswordSuccess] = useState(false);

  const [currentPage, setCurrentPage] = useState('profile');
  const [showTutorialReset, setShowTutorialReset] = useState(false);
  const [showDemoReset, setShowDemoReset] = useState(false);
  const [isDemoResetting, setIsDemoResetting] = useState(false);

  const isDemo = import.meta.env.VITE_IS_DEMO === 'true';

  const navigate = useNavigate();
  const { resetOnboarding } = useOnboarding();

  useEffect(() => {
    const fetchProfile = async () => {
      const result = await loadUserProfileHandler();
      if (result.success) {
        setProfile(result.profile);
      } else {
        setMessage(result.error);
      }
      setLoadingProfile(false);
    };
    fetchProfile();
  }, []);

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  const handleInputChange = (field, value) => {
    setProfile(prev => ({ ...prev, [field]: value }));
  };

  const handlePasswordChange = (field, value) => {
    setPasswordData(prev => ({ ...prev, [field]: value }));
    setPasswordError('');
  };


  const handleChangePassword = async () => {
    // Use validatePasswordData from handlers
    const validationError = validatePasswordData(passwordData);
    if (validationError) {
      setPasswordError(validationError);
      return;
    }

    // Use changePassword from handlers
    const result = await changePassword(passwordData.oldPassword, passwordData.newPassword);

    if (result.success) {
      setPasswordData({ oldPassword: '', newPassword: '', confirmPassword: '' });
      setShowPasswordModal(false);
      setShowPasswordSuccess(true);
      // Hide success message after 3 seconds
      setTimeout(() => {
        setShowPasswordSuccess(false);
      }, 3000);
    } else {
      setPasswordError(result.error);
    }
  };

  const handleSaveChanges = async () => {
    setIsLoading(true);
    setMessage('');

    // Use updateUserProfile from handlers
    const result = await updateUserProfile(profile);
    setMessage(result.message);
    setIsLoading(false);
  };


    const handleNavigation = (pageId) => {
    setCurrentPage(pageId);
    if (pageId === 'dashboard') {
        navigate(tenantPath('/dashboard'));
    }
  };

  if (loadingProfile) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-100 to-pink-100 p-8 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto mb-4"></div>
          <p className="text-gray-700">Loading profile...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-purple-to-br from-purple-50 to-pink-50 p-4">
      <Navigation
                  currentPage={currentPage}
                  onNavigate={handleNavigation}
                />
      <div className="w-two-third mx-auto">
        {/* Profile Section */}
        <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg">
          <div className="flex items-center mb-6">
            <User className="w-5 h-5 mr-2 text-gray-700"/>
            <h2 className="text-xl font-semibold text-gray-800">Profile</h2>
          </div>
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-800">Account Details</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                <input
                  type="text"
                  value={profile.full_name}
                  onChange={(e) => handleInputChange('full_name', e.target.value)}
                  className="w-full px-3 py-2 bg-transparent border-b border-gray-600 focus:border-purple-600 outline-none text-gray-800"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
                <input
                  type="text"
                  value={profile.username}
                  onChange={(e) => handleInputChange('username', e.target.value)}
                  className="w-full px-3 py-2 bg-transparent border-b border-gray-600 focus:border-purple-600 outline-none text-gray-800"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input
                  type="email"
                  value={profile.email}
                  disabled
                  className="w-full px-3 py-2 bg-gray-200 border-b border-gray-600 outline-none text-gray-600 cursor-not-allowed"
                />
              </div>
            </div>
          </div>
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-800">Demographics Details</h2>
            <p className="text-xs text-gray-500 mt-1 mb-3">
              Demographic information is collected for research and reporting purposes only. It is kept confidential and handled in compliance with applicable data protection regulations. Providing this information is optional. See our{' '}
              <a
                href="https://phawm.org/privacy-notice/"
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-purple hover:font-bold transition-colors"
              >
                Privacy Notice
              </a>
              .
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Gender</label>
                <input
                  type="text"
                  value={profile.gender}
                  onChange={(e) => handleInputChange('gender', e.target.value)}
                  className="w-full px-3 py-2 bg-transparent border-b border-gray-600 focus:border-purple-600 outline-none text-gray-800"
                />
              </div>

              {/* Ethnicity field — hidden visually, kept as placeholder only */}
              <div className="hidden">
                <input
                  type="text"
                  value={profile.ethnicity}
                  onChange={(e) => handleInputChange('ethnicity', e.target.value)}
                  placeholder="Ethnicity"
                  tabIndex={-1}
                  aria-hidden="true"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Country</label>
                <input
                  type="text"
                  value={profile.country}
                  onChange={(e) => handleInputChange('country', e.target.value)}
                  className="w-full px-3 py-2 bg-transparent border-b border-gray-600 focus:border-purple-600 outline-none text-gray-800"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Organisation</label>
                <input
                  type="text"
                  value={profile.organisation}
                  onChange={(e) => handleInputChange('organisation', e.target.value)}
                  className="w-full px-3 py-2 bg-transparent border-b border-gray-600 focus:border-purple-600 outline-none text-gray-800"
                />
              </div>

            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="flex gap-4">
              <button
                onClick={() => setShowPasswordModal(true)}
                className="flex-1 bg-purple-100 hover:bg-purple-200 px-8 py-2 rounded-full text-base font-semibold transition-colors border-2 border-purple-200"
              >
                Change Password
              </button>
            </div>
            <div className="flex gap-4">
              <button
                onClick={handleSaveChanges}
                disabled={isLoading}
                className="flex-1 bg-purple-100 hover:bg-purple-200 px-8 py-2 rounded-full text-base font-semibold transition-colors border-2 border-purple-200"
              >
                {isLoading ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
            <div className="flex gap-4">
              <button
                onClick={() => {
                  resetOnboarding();
                  setShowTutorialReset(true);
                  setTimeout(() => setShowTutorialReset(false), 3000);
                }}
                className="flex-1 bg-purple-100 hover:bg-purple-200 px-8 py-2 rounded-full text-base font-semibold transition-colors border-2 border-purple-200"
              >
                Reset Tutorial
              </button>
            </div>
            <div className="flex gap-4">
                <button
                  onClick={handleLogout}
                  className="flex-1 bg-purple-100 hover:bg-purple-200 px-8 py-2 rounded-full text-base font-semibold transition-colors border-2 border-purple-200"
                >
                  Logout
                </button>
              </div>
              {user?.is_superuser && (
                <div className="flex gap-4">
                  <button
                    onClick={() => navigate(tenantPath('/admin'))}
                    className="flex-1 bg-purple-100 hover:bg-purple-200 px-8 py-2 rounded-full text-base font-semibold transition-colors border-2 border-purple-200"
                  >
                    Admin Panel
                  </button>
                </div>
              )}
              {isDemo && (
                <div className="flex gap-4">
                  <button
                    onClick={async () => {
                      setIsDemoResetting(true);
                      try {
                        await demoAPI.resetDemo();
                        setShowDemoReset(true);
                        setTimeout(() => setShowDemoReset(false), 3000);
                      } catch (err) {
                        setMessage(err.message || 'Failed to reset demo');
                      }
                      setIsDemoResetting(false);
                    }}
                    disabled={isDemoResetting}
                    className="flex-1 bg-purple-100 hover:bg-purple-200 px-8 py-2 rounded-full text-base font-semibold transition-colors border-2 border-purple-200"
                  >
                    {isDemoResetting ? 'Resetting...' : 'Reset Demo'}
                  </button>
                </div>
              )}
          </div>
        </div>

        {/* PHAWM Logo */}
        <div className="mt-8 text-right">
          <span className="text-purple-600 font-bold text-sm">PHAWM</span>
        </div>

      </div>

      {/* Password Change Modal */}
      {showPasswordModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-gradient-to-br from-purple-100 to-pink-100 rounded-lg p-8 max-w-sm w-full border-2 border-purple-400">
            <h2 className="text-2xl font-bold text-center text-gray-800 mb-8">Change Password</h2>
            
            <div className="space-y-6">
              <div>
                <label className="block text-gray-600 text-sm font-medium mb-2">Old Password</label>
                <input
                  type="password"
                  value={passwordData.oldPassword}
                  onChange={(e) => handlePasswordChange('oldPassword', e.target.value)}
                  className="w-full px-4 py-3 bg-white/80 border-2 border-purple-300 rounded-full focus:border-purple-500 outline-none transition-colors"
                />
              </div>

              <div>
                <label className="block text-gray-600 text-sm font-medium mb-2">New Password</label>
                <input
                  type="password"
                  value={passwordData.newPassword}
                  onChange={(e) => handlePasswordChange('newPassword', e.target.value)}
                  className="w-full px-4 py-3 bg-white/80 border-2 border-purple-300 rounded-full focus:border-purple-500 outline-none transition-colors"
                />
              </div>

              <div>
                <label className="block text-gray-600 text-sm font-medium mb-2">Confirm New Password</label>
                <input
                  type="password"
                  value={passwordData.confirmPassword}
                  onChange={(e) => handlePasswordChange('confirmPassword', e.target.value)}
                  className="w-full px-4 py-3 bg-white/80 border-2 border-purple-300 rounded-full focus:border-purple-500 outline-none transition-colors"
                />
              </div>

              {passwordError && (
                <div className="bg-red-100 text-red-800 p-3 rounded text-sm border border-red-300">
                  {passwordError}
                </div>
              )}

              <div className="flex space-x-3 pt-4">
                <button
                  onClick={() => {
                    setShowPasswordModal(false);
                    setPasswordData({ oldPassword: '', newPassword: '', confirmPassword: '' });
                    setPasswordError('');
                  }}
                  className="bg-purple-100 hover:bg-purple-200 px-8 py-2 rounded-full text-base font-semibold transition-colors border-2 border-purple-200"
                >
                  Cancel
                </button>
                <button
                  onClick={handleChangePassword}
                  className="bg-purple-100 hover:bg-purple-200 px-8 py-2 rounded-full text-base font-semibold transition-colors border-2 border-purple-200"
                >
                  Change Password
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Success Toast for Password Change */}
      {showPasswordSuccess && (
        <div className="fixed top-4 right-4 bg-green-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 animate-fade-in">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span className="font-semibold">Password changed successfully!</span>
          </div>
        </div>
      )}

      {/* Success Toast for Tutorial Reset */}
      {showTutorialReset && (
        <div className="fixed top-4 right-4 bg-green-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 animate-fade-in">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span className="font-semibold">Tutorial reset! It will show when you enter an audit.</span>
          </div>
        </div>
      )}

      {/* Success Toast for Demo Reset */}
      {showDemoReset && (
        <div className="fixed top-4 right-4 bg-green-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 animate-fade-in">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span className="font-semibold">Demo reset successfully!</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProfileInterface;