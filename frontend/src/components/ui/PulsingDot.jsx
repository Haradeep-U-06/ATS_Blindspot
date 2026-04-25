import React from 'react';

export function PulsingDot({ className = "" }) {
  return (
    <div className={`w-3 h-3 rounded-full bg-primary animate-pulseDot ${className}`} />
  );
}
