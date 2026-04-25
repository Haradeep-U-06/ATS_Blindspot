import React from 'react';

export function Card({ children, className = "" }) {
  return (
    <div className={`bg-white rounded-2xl shadow-sm border border-mid/10 transition-all duration-300 p-6 ${className}`}>
      {children}
    </div>
  );
}
