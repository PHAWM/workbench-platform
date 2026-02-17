import React, { useState, useEffect } from 'react';
import { Plus, ChevronDown, ArrowLeft, X, ChevronUp, User } from 'lucide-react';

const CreatableMultiSelect = ({
  value,
  onChange,
  onCreateNew, // New prop: callback when creating new item
  onBlur, // Prop for blur callback (validation)
  placeholder,
  options = [], // Default to empty array
  label,
  helpText,
  allowCreate = true, // New prop to control creation ability
  isDisabled = false, // Prop to disable the entire component
  hasError = false, // Prop to show error styling
  errorMessage = '' // Prop to show error message
}) => {
  const [selectedOptions, setSelectedOptions] = useState(Array.isArray(value) ? value : []);
  const [inputValue, setInputValue] = useState('');
  const [isOpen, setIsOpen] = useState(false);

  // Sync internal state with prop changes
  useEffect(() => {
    setSelectedOptions(Array.isArray(value) ? value : []);
  }, [value]);

  const handleOptionToggle = (option) => {
    if (isDisabled || !Array.isArray(selectedOptions)) return;

    const newSelected = selectedOptions.includes(option)
      ? selectedOptions.filter(item => item !== option)
      : [...selectedOptions, option];

    setSelectedOptions(newSelected);
    onChange(newSelected);
  };

  const handleCreateNew = () => {
    if (isDisabled || !Array.isArray(selectedOptions)) return;

    if (allowCreate && inputValue.trim() && !selectedOptions.includes(inputValue.trim())) {
      const newOption = inputValue.trim();

      // If onCreateNew callback is provided, use it instead of directly adding
      if (onCreateNew) {
        onCreateNew(newOption);
        setInputValue('');
        setIsOpen(false);
      } else {
        // Default behavior: add to selection directly
        const newSelected = [...selectedOptions, newOption];
        setSelectedOptions(newSelected);
        onChange(newSelected);
        setInputValue('');
      }
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (allowCreate) {
        handleCreateNew();
      }
    }
  };

  const removeOption = (optionToRemove) => {
    if (isDisabled || !Array.isArray(selectedOptions)) return;

    const newSelected = selectedOptions.filter(item => item !== optionToRemove);
    setSelectedOptions(newSelected);
    onChange(newSelected);
  };

  return (
    <div>
      <label className="block text-base font-medium text-gray-700 mb-1">{label}</label>
      {helpText && <p className="text-base text-gray-500 mb-2">{helpText}</p>}

      <div className="relative" style={{ zIndex: isOpen ? 20 : 'auto' }}>
        {/* Selected Options Display */}
        {Array.isArray(selectedOptions) && selectedOptions.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-1">
            {selectedOptions.map((option, index) => (
              <span
                key={index}
                className="inline-flex items-center gap-1 px-3 py-1 bg-purple-100 text-purple-800 rounded-full text-base"
              >
                {option}
                <button
                  onClick={() => removeOption(option)}
                  disabled={isDisabled}
                  className={`rounded-full p-0.5 ${isDisabled ? 'cursor-not-allowed opacity-50' : 'hover:bg-purple-200'}`}
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
        )}

        {/* Input Field */}
        <div className="relative">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            onFocus={() => !isDisabled && setIsOpen(true)}
            onBlur={() => {
              // Delay blur to allow click on dropdown options
              setTimeout(() => {
                if (onBlur) onBlur();
              }, 200);
            }}
            disabled={isDisabled}
            placeholder={
              (!Array.isArray(selectedOptions) || selectedOptions.length === 0)
                ? placeholder
                : allowCreate
                  ? "Type to add more..."
                  : "Search existing options..."
            }
            className={`w-full bg-purple px-4 py-3 border-2 rounded-2xl focus:outline-none transition-colors resize-none ${
              hasError ? 'border-red-500 focus:border-red-600' : 'border-purple-200 focus:border-purple-400'
            } ${isDisabled ? 'cursor-not-allowed opacity-60' : ''}`}
            // className="w-full px-4 py-3 border-2 border-purple-200 rounded-2xl focus:border-purple-400 focus:outline-none transition-colors pr-10"
          />
          <button
            onClick={() => !isDisabled && setIsOpen(!isOpen)}
            disabled={isDisabled}
            className={`absolute right-3 top-1/2 transform -translate-y-1/2 ${isDisabled ? 'cursor-not-allowed opacity-50' : ''}`}
          >
            <ChevronDown className={`w-5 h-5 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
          </button>
        </div>

        {/* Dropdown Options */}
        {isOpen && !isDisabled && (
          <div className="absolute z-10 w-full mt-1 bg-purple border-2 border-purple-200 rounded-xl shadow-lg max-h-48 overflow-y-auto">
            {/* Create New Option - Only show if allowCreate is true */}
            {allowCreate && inputValue.trim() &&
             !options.includes(inputValue.trim()) &&
             (!Array.isArray(selectedOptions) || !selectedOptions.includes(inputValue.trim())) && (
              <button
                onClick={handleCreateNew}
                disabled={isDisabled}
                className="w-full px-4 py-3 text-left hover:bg-purple-50 border-b border-gray-100 flex items-center gap-2"
                // className="w-full bg-purple px-4 py-3 border-2 border-purple-200 rounded-2xl focus:border-purple-400 focus:outline-none transition-colors resize-none"
              >
                <Plus className="w-4 h-4 text-purple-600" />
                <span className="text-purple-600">Create "{inputValue.trim()}"</span>
              </button>
            )}

            {/* Existing Options */}
            {options
              .filter(option =>
                option.toLowerCase().includes(inputValue.toLowerCase()) &&
                (!Array.isArray(selectedOptions) || !selectedOptions.includes(option))
              )
              .map((option, index) => (
                <button
                  key={index}
                  onClick={() => handleOptionToggle(option)}
                  disabled={isDisabled}
                  className="w-full px-4 py-3 text-left hover:bg-purple-50 border-b border-gray-100 last:border-b-0"
                >
                  {option}
                </button>
              ))}

            {/* No options message */}
            {options.filter(option => 
              option.toLowerCase().includes(inputValue.toLowerCase()) &&
              (!Array.isArray(selectedOptions) || !selectedOptions.includes(option))
            ).length === 0 && !inputValue.trim() && (
              <div className="px-4 py-3 text-gray-500 text-base">No options available</div>
            )}

            {/* No matches message when creation is disabled */}
            {!allowCreate && 
             inputValue.trim() && 
             options.filter(option => 
               option.toLowerCase().includes(inputValue.toLowerCase()) &&
               (!Array.isArray(selectedOptions) || !selectedOptions.includes(option))
             ).length === 0 && (
              <div className="px-4 py-3 text-gray-500 text-base">
                No matching options found
              </div>
            )}
          </div>
        )}
      </div>

      {/* Click outside to close */}
      {isOpen && (
        <div
          className="fixed inset-0"
          style={{ zIndex: 1, pointerEvents: 'auto' }}
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Error message */}
      {hasError && errorMessage && (
        <p className="text-base text-red-600 mt-1">{errorMessage}</p>
      )}
    </div>
  );
};

export default CreatableMultiSelect;