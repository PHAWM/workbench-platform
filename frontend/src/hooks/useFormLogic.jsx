// hooks/useFormLogic.js
import { useState, useEffect } from 'react';
import { 
  hasFormChanges, 
  getFormChanges, 
  validateRequiredFields,
  validateFeatureRanges,
  createFormHandlers
} from '../utils/formUtils';

export const useFormLogic = (initialData = {}, originalDataDependency = null) => {
  const [formData, setFormData] = useState(initialData);
  const [originalData, setOriginalData] = useState(null);

  // Create form handlers
  const handlers = createFormHandlers(formData, setFormData);

  // Update form data when initial data changes
  useEffect(() => {
    if (originalDataDependency) {
      setFormData(initialData);
      setOriginalData(JSON.parse(JSON.stringify(initialData)));
    }
  }, [originalDataDependency]);

  // Change detection
  const hasChanges = () => hasFormChanges(formData, originalData);
  const getChanges = () => getFormChanges(formData, originalData);

  // Validation
  const validateForm = (requiredFields = [], qualMetric = false) => {
    const missingFields = validateRequiredFields(formData, requiredFields);
    const incompleteRanges = (!qualMetric) ? validateFeatureRanges(formData) : 'None';
    
    return {
      isValid: missingFields.length === 0 && (incompleteRanges.length === 0 || qualMetric),
      missingFields,
      incompleteRanges
    };
  };

  // Reset form
  const resetForm = () => {
    setFormData(initialData);
    setOriginalData(null);
  };

  return {
    formData,
    setFormData,
    originalData,
    setOriginalData,
    hasChanges,
    getChanges,
    validateForm,
    resetForm,
    ...handlers
  };
};