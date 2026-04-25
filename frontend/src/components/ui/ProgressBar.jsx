import React from 'react';

export function ProgressBar({ value = 0, animated = false, className = "" }) {
  const percentage = Math.min(Math.max(value, 0), 100);
  
  return (
    <div className={`w-full h-2 bg-soft rounded-full overflow-hidden ${className}`}>
      <div 
        className={`h-full bg-primary transition-all duration-500 ease-out ${animated ? 'animate-pulse' : ''}`}
        style={{ width: `${percentage}%` }}
      />
    </div>
  );
}
