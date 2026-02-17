import React, { useRef, useState } from 'react';

export const CustomSlider = ({
  value = [50],
  onValueChange,
  min = 0,
  max = 100,
  step = 1,
  disabled = false,
  className = ""
}) => {
  const sliderRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);

  const currentValue = value[0];

  const updateValue = (clientX) => {
    if (disabled || !sliderRef.current) return;

    const rect = sliderRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
    const percentage = (x / rect.width) * 100;

    // Calculate value based on percentage
    const rawValue = (percentage / 100) * (max - min) + min;
    const steppedValue = Math.round(rawValue / step) * step;
    const clampedValue = Math.max(min, Math.min(max, steppedValue));

    if (onValueChange) {
      onValueChange([clampedValue]);
    }
  };

  const handleMouseDown = (e) => {
    if (disabled) return;
    e.preventDefault();
    setIsDragging(true);
    updateValue(e.clientX);

    // Add event listeners immediately
    const handleMouseMove = (e) => {
      e.preventDefault();
      updateValue(e.clientX);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };

  const percentage = ((currentValue - min) / (max - min)) * 100;

  return (
    <div
      ref={sliderRef}
      className={`relative flex w-full items-center py-2 ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'} ${className}`}
      onMouseDown={handleMouseDown}
      style={{ userSelect: 'none' }}
    >
      {/* Track */}
      <div className="relative h-2 w-full rounded-full bg-purple-200">
        {/* Filled Range */}
        <div
          className="absolute h-full rounded-full bg-purple-500"
          style={{ width: `${percentage}%` }}
        />
      </div>

      {/* Thumb */}
      <div
        className="absolute h-5 w-5 rounded-full border-2 border-purple-600 bg-white shadow-md"
        style={{
          left: `calc(${percentage}% - 10px)`,
          pointerEvents: 'none'
        }}
      />
    </div>
  );
};
