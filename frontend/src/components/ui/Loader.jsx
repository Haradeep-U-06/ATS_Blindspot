import React from 'react';
import { Loader2 } from 'lucide-react';

export function Loader({ variant = 'spinner', text = "Loading...", className = "" }) {
  if (variant === 'skeleton') {
    return (
      <div className={`animate-pulse bg-mid/10 rounded-lg ${className}`}></div>
    );
  }

  return (
    <div className={`flex flex-col items-center justify-center p-8 text-mid ${className}`}>
      <Loader2 className="w-8 h-8 animate-spin mb-3 text-primary" />
      <span className="text-sm font-medium">{text}</span>
    </div>
  );
}
