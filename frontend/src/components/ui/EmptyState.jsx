import React from 'react';
import { Leaf } from 'lucide-react';

export function EmptyState({ title, message, action, className = "" }) {
  return (
    <div className={`flex flex-col items-center justify-center p-12 text-center bg-white rounded-xl border border-mid/10 shadow-sm ${className}`}>
      <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mb-4 text-primary">
        <Leaf className="w-8 h-8" />
      </div>
      <h3 className="text-xl font-heading font-semibold text-dark mb-2">{title}</h3>
      <p className="text-mid max-w-sm mb-6">{message}</p>
      {action && <div>{action}</div>}
    </div>
  );
}
