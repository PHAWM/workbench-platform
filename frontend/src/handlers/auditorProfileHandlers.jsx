/**
 * Handlers for AuditorProfile page
 * Contains profile management and password change functions
 */

import { authAPI } from '../api/apiService';

/**
 * Validate password data
 * @param {Object} passwordData - Password data object
 * @returns {string} Error message or empty string if valid
 */
export const validatePasswordData = (passwordData) => {
  if (!passwordData.oldPassword || !passwordData.newPassword || !passwordData.confirmPassword) {
    return 'All password fields are required';
  }

  if (passwordData.newPassword !== passwordData.confirmPassword) {
    return 'New passwords do not match';
  }

  if (passwordData.newPassword.length < 8) {
    return 'New password must be at least 8 characters long';
  }

  return '';
};

/**
 * Load user profile from API
 * @returns {Promise<Object>} User profile data
 */
export const loadUserProfile = async () => {
  try {
    const userData = await authAPI.getCurrentUser();
    return {
      success: true,
      profile: {
        full_name: userData.full_name || '',
        username: userData.username || '',
        email: userData.email || '',
        gender: userData.gender || '',
        ethnicity: userData.ethnicity || '',
        country: userData.country || '',
        organisation: userData.organisation || ''
      }
    };
  } catch (error) {
    console.error('Error loading profile:', error);
    return { success: false, error: 'Error loading profile data' };
  }
};

/**
 * Update user profile
 * @param {Object} profile - Profile data to update
 * @returns {Promise<Object>} Result object
 */
export const updateUserProfile = async (profile) => {
  try {
    await authAPI.updateUserProfile({
      full_name: profile.full_name,
      username: profile.username,
      gender: profile.gender,
      ethnicity: profile.ethnicity,
      country: profile.country,
      organisation: profile.organisation
    });
    return { success: true, message: 'Changes saved successfully!' };
  } catch (error) {
    console.error('Profile update error:', error);
    return { success: false, message: 'Error saving changes. Please try again.' };
  }
};

/**
 * Change user password
 * @param {string} oldPassword - Current password
 * @param {string} newPassword - New password
 * @returns {Promise<Object>} Result object
 */
export const changePassword = async (oldPassword, newPassword) => {
  try {
    await authAPI.updatePassword(oldPassword, newPassword);
    return { success: true };
  } catch (error) {
    console.error('Password change error:', error);
    const errorMessage = error?.message || error?.detail || 'Error changing password. Please check your old password and try again.';
    return { success: false, error: errorMessage };
  }
};

/**
 * Creates handlers for auditor profile page
 * @param {Object} params - Parameters for creating handlers
 * @returns {Object} Handler functions
 */
export const createAuditorProfileHandlers = ({
  setProfile,
  setPasswordData,
  setPasswordError,
  setShowPasswordModal,
  setShowPasswordSuccess,
  setIsLoading,
  setMessage,
  setCurrentPage,
  navigate,
  logout
}) => {
  /**
   * Handle profile field change
   * @param {string} field - Field name
   * @param {string} value - New value
   */
  const handleInputChange = (field, value) => {
    setProfile(prev => ({ ...prev, [field]: value }));
  };

  /**
   * Handle password field change
   * @param {string} field - Field name
   * @param {string} value - New value
   */
  const handlePasswordChange = (field, value) => {
    setPasswordData(prev => ({ ...prev, [field]: value }));
    setPasswordError('');
  };

  /**
   * Handle password change submission
   * @param {Object} passwordData - Password data
   */
  const handleChangePassword = async (passwordData) => {
    const validationError = validatePasswordData(passwordData);
    if (validationError) {
      setPasswordError(validationError);
      return;
    }

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

  /**
   * Handle profile save
   * @param {Object} profile - Profile data
   */
  const handleSaveChanges = async (profile) => {
    setIsLoading(true);
    setMessage('');

    const result = await updateUserProfile(profile);
    setMessage(result.message);
    setIsLoading(false);
  };

  /**
   * Handle navigation
   * @param {string} pageId - Target page ID
   */
  const handleNavigation = (pageId) => {
    setCurrentPage(pageId);
    if (pageId === 'dashboard') {
      navigate('/dashboard');
    } else if (pageId === 'profile') {
      navigate('/profile');
    }
  };

  /**
   * Handle logout
   */
  const handleLogout = async () => {
    try {
      await logout();
      window.location.href = '/login';
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  return {
    handleInputChange,
    handlePasswordChange,
    handleChangePassword,
    handleSaveChanges,
    handleNavigation,
    handleLogout
  };
};
