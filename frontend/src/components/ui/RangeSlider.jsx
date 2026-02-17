import React, { useState, useRef } from 'react';

const RangeSlider = ({
  label,
  value,
  onChange,
  helptext,
  min = 0,
  max = 100,
  disabled = false
}) => {
  const [currentValue, setCurrentValue] = useState(value ?? 50);
  const sliderRef = useRef(null);

  // Get color based on value
  const getTrackColor = () => {
    if (disabled) return '#9ca3af';
    if (currentValue < 33) return '#4ade80';
    if (currentValue < 66) return '#6c00df';
    return '#f87171';
  };

  const handleInputChange = (e) => {
    const newValue = parseInt(e.target.value, 10);
    setCurrentValue(newValue);
    if (onChange) {
      onChange(newValue);
    }
  };

  return (
    <div className="space-y-3">
      <label className="block text-base font-medium text-gray-700">{label}</label>
      {helptext && (
        <label className="block text-base text-gray-500 mb-2">{helptext}</label>
      )}
      <div className="px-2 py-4">
        <input
          ref={sliderRef}
          type="range"
          min={min}
          max={max}
          value={currentValue}
          disabled={disabled}
          onChange={handleInputChange}
          className="w-full h-3 rounded-lg cursor-pointer"
          style={{
            background: disabled ? 'linear-gradient(to right, #f3e8ff, #6c00df)' : 'linear-gradient(to right, #f3e8ff, #6c00df)',
            // accentColor: getTrackColor(),
            opacity: disabled ? 0.6 : 1,
            cursor: disabled ? 'not-allowed' : 'pointer'
          }}
        />
        {/* Scale labels */}
        <div className="flex justify-between text-base text-gray-500 mt-3 px-1">
          <span className={currentValue === 0 ? 'text-purple-600 font-semibold' : ''}>{min}</span>
          <span className={currentValue === 25 ? 'text-purple-600 font-semibold' : ''}>25</span>
          <span className={currentValue === 50 ? 'text-purple-600 font-semibold' : ''}>50</span>
          <span className={currentValue === 75 ? 'text-purple-600 font-semibold' : ''}>75</span>
          <span className={currentValue === 100 ? 'text-purple-600 font-semibold' : ''}>{max}</span>
        </div>
      </div>
      {/* Value display */}
      <div className="text-center">
        <span className={`inline-block px-4 py-2 rounded-full text-base font-semibold ${
          disabled ? 'bg-gray-100 text-gray-500' : 'bg-purple-100 text-purple-800'
        }`}>
          {currentValue}%
        </span>
      </div>
    </div>
  );
};

export default RangeSlider;
