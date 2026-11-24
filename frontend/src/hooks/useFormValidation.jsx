import { useState, useCallback, useMemo } from 'react';

/**
 * Custom hook for inline form validation
 *
 * @param {Object} validationRules - Object mapping field names to validation rules
 * @example
 * const rules = {
 *   name: { required: true, message: 'Name is required' },
 *   email: {
 *     required: true,
 *     pattern: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
 *     message: 'Valid email is required'
 *   },
 *   description: {
 *     required: true,
 *     minLength: 10,
 *     message: 'Description must be at least 10 characters'
 *   }
 * };
 */
export const useFormValidation = (validationRules = {}) => {
  const [touched, setTouched] = useState({});
  const [errors, setErrors] = useState({});

  // Validate a single field
  const validateField = useCallback((fieldName, value, rules = validationRules[fieldName]) => {
    if (!rules) return '';

    // Required validation
    if (rules.required) {
      if (Array.isArray(value)) {
        if (value.length === 0) {
          return rules.message || `${fieldName} is required`;
        }
      } else if (!value || (typeof value === 'string' && !value.trim())) {
        return rules.message || `${fieldName} is required`;
      }
    }

    // Min length validation
    if (rules.minLength && value && value.length < rules.minLength) {
      return rules.message || `${fieldName} must be at least ${rules.minLength} characters`;
    }

    // Max length validation
    if (rules.maxLength && value && value.length > rules.maxLength) {
      return rules.message || `${fieldName} must be at most ${rules.maxLength} characters`;
    }

    // Pattern validation
    if (rules.pattern && value && !rules.pattern.test(value)) {
      return rules.message || `${fieldName} is invalid`;
    }

    // Min value validation (for numbers)
    if (rules.min !== undefined && value !== '' && Number(value) < rules.min) {
      return rules.message || `${fieldName} must be at least ${rules.min}`;
    }

    // Max value validation (for numbers)
    if (rules.max !== undefined && value !== '' && Number(value) > rules.max) {
      return rules.message || `${fieldName} must be at most ${rules.max}`;
    }

    // Custom validation function
    if (rules.validate && typeof rules.validate === 'function') {
      const customError = rules.validate(value);
      if (customError) {
        return customError;
      }
    }

    return '';
  }, [validationRules]);

  // Mark a field as touched (typically on blur)
  const touchField = useCallback((fieldName) => {
    setTouched(prev => ({ ...prev, [fieldName]: true }));
  }, []);

  // Mark multiple fields as touched
  const touchFields = useCallback((fieldNames) => {
    setTouched(prev => {
      const newTouched = { ...prev };
      fieldNames.forEach(name => {
        newTouched[name] = true;
      });
      return newTouched;
    });
  }, []);

  // Touch all fields (useful for form submission)
  const touchAllFields = useCallback(() => {
    const allTouched = {};
    Object.keys(validationRules).forEach(key => {
      allTouched[key] = true;
    });
    setTouched(allTouched);
  }, [validationRules]);

  // Update error for a single field
  const setFieldError = useCallback((fieldName, error) => {
    setErrors(prev => ({ ...prev, [fieldName]: error }));
  }, []);

  // Validate a single field and update errors
  const validateAndSetError = useCallback((fieldName, value) => {
    const error = validateField(fieldName, value);
    setFieldError(fieldName, error);
    return error;
  }, [validateField, setFieldError]);

  // Validate all fields and return validation result.
  // Optionally pass `fieldsToValidate` to only validate a subset of the rules.
  const validateAllFields = useCallback((formData, fieldsToValidate = null) => {
    const newErrors = {};
    let isValid = true;

    const fields = Array.isArray(fieldsToValidate) && fieldsToValidate.length > 0
      ? fieldsToValidate.filter(name => name in validationRules)
      : Object.keys(validationRules);

    fields.forEach(fieldName => {
      const error = validateField(fieldName, formData[fieldName]);
      if (error) {
        newErrors[fieldName] = error;
        isValid = false;
      }
    });

    setErrors(newErrors);
    touchFields(fields);

    return { isValid, errors: newErrors };
  }, [validationRules, validateField, touchFields]);

  // Clear all errors and touched state
  const resetValidation = useCallback(() => {
    setTouched({});
    setErrors({});
  }, []);

  // Clear error for a specific field
  const clearFieldError = useCallback((fieldName) => {
    setErrors(prev => {
      const newErrors = { ...prev };
      delete newErrors[fieldName];
      return newErrors;
    });
  }, []);

  // Get error for a field (only if touched)
  const getFieldError = useCallback((fieldName) => {
    return touched[fieldName] ? errors[fieldName] : '';
  }, [touched, errors]);

  // Check if a field has an error (only if touched)
  const hasFieldError = useCallback((fieldName) => {
    return touched[fieldName] && !!errors[fieldName];
  }, [touched, errors]);

  // Check if the form has any errors
  const hasErrors = useMemo(() => {
    return Object.values(errors).some(error => !!error);
  }, [errors]);

  // Get props to spread on an input for validation
  const getFieldProps = useCallback((fieldName, value) => {
    return {
      onBlur: () => {
        touchField(fieldName);
        validateAndSetError(fieldName, value);
      },
      onChange: (newValue) => {
        // If field is already touched, validate on change
        if (touched[fieldName]) {
          validateAndSetError(fieldName, newValue);
        }
      }
    };
  }, [touchField, validateAndSetError, touched]);

  return {
    touched,
    errors,
    touchField,
    touchFields,
    touchAllFields,
    validateField,
    validateAndSetError,
    validateAllFields,
    setFieldError,
    clearFieldError,
    resetValidation,
    getFieldError,
    hasFieldError,
    hasErrors,
    getFieldProps
  };
};

export default useFormValidation;
