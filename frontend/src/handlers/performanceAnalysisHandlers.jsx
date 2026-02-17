/**
 * Handlers for PerformanceAnalysis page
 * Contains validation logic and utility functions
 */

/**
 * Validates the notes/feedback field
 * @param {string} value - The notes value to validate
 * @returns {string} Error message or empty string if valid
 */
export const validateNotes = (value) => {
  if (!value || !value.trim()) {
    return 'Feedback and justification is required';
  }
  if (value.trim().length < 10) {
    return 'Please provide more detailed feedback (at least 10 characters)';
  }
  return '';
};

/**
 * Validates the recommendation field
 * @param {string} value - The recommendation value to validate
 * @returns {string} Error message or empty string if valid
 */
export const validateRecommendation = (value) => {
  if (!value) {
    return 'Please select a recommendation (Pass, Fail, or Inconclusive)';
  }
  return '';
};

/**
 * Converts recommendation string to number for API
 * @param {string} rec - Recommendation string ('pass', 'fail', 'inconclusive')
 * @returns {number} Recommendation number (3=Pass, 2=Fail, 1=Inconclusive, 0=Not Evaluated)
 */
export const getRecommendationNumber = (rec) => {
  switch (rec?.toLowerCase()) {
    case 'pass': return 3;
    case 'fail': return 2;
    case 'inconclusive': return 1;
    default: return 0;
  }
};

/**
 * Converts recommendation number to string for display
 * @param {number} num - Recommendation number
 * @returns {string} Recommendation string
 */
export const getRecommendationString = (num) => {
  switch (num) {
    case 3: return 'pass';
    case 2: return 'fail';
    case 1: return 'inconclusive';
    default: return '';
  }
};

/**
 * Gets the CSS class for recommendation badge
 * @param {string} rec - Recommendation string
 * @returns {string} Tailwind CSS classes
 */
export const getRecommendationBadgeClass = (rec) => {
  if (rec === 'fail') return 'bg-red-500 text-white';
  if (rec === 'pass') return 'bg-green-500 text-white';
  if (rec === 'inclusive' || rec === 'inconclusive') return 'bg-yellow-500 text-white';
  return 'bg-gray-100 text-gray-800';
};

/**
 * Gets the CSS class for metric type badge
 * @param {string} metricType - Metric type ('quantitative' or 'qualitative')
 * @returns {string} Tailwind CSS classes
 */
export const getMetricTypeColor = (metricType) => {
  switch (metricType?.toLowerCase()) {
    case 'quantitative':
      return 'bg-blue-100 border-blue-100';
    case 'qualitative':
      return 'bg-green-100 border-green-100';
    default:
      return 'bg-gray-100 border-gray-100';
  }
};

/**
 * Creates handlers for performance analysis form
 * @param {Object} params - Parameters for creating handlers
 * @returns {Object} Handler functions
 */
export const createPerformanceAnalysisHandlers = ({
  setNotes,
  setRecommendation,
  setValidationErrors,
  setTouched,
  touched,
  notes
}) => {
  const handleNotesChange = (value) => {
    setNotes(value);
    if (touched.notes) {
      setValidationErrors(prev => ({
        ...prev,
        notes: validateNotes(value)
      }));
    }
  };

  const handleNotesBlur = () => {
    setTouched(prev => ({ ...prev, notes: true }));
    setValidationErrors(prev => ({
      ...prev,
      notes: validateNotes(notes)
    }));
  };

  const handleRecommendationChange = (value) => {
    setRecommendation(value);
    setTouched(prev => ({ ...prev, recommendation: true }));
    setValidationErrors(prev => ({
      ...prev,
      recommendation: validateRecommendation(value)
    }));
  };

  const validateAllFields = (notesValue, recommendationValue) => {
    const notesError = validateNotes(notesValue);
    const recommendationError = validateRecommendation(recommendationValue);

    setValidationErrors({
      notes: notesError,
      recommendation: recommendationError
    });

    setTouched({
      notes: true,
      recommendation: true
    });

    return !notesError && !recommendationError;
  };

  return {
    handleNotesChange,
    handleNotesBlur,
    handleRecommendationChange,
    validateAllFields
  };
};
