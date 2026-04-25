import React from 'react';
import { CheckCircle, XCircle, Info, X } from 'lucide-react';

export function Toast({ message, variant = 'info', onClose }) {
  const variants = {
    success: { bg: 'bg-primary/90 text-white', icon: CheckCircle },
    error: { bg: 'bg-error/90 text-white', icon: XCircle },
    info: { bg: 'bg-mid/90 text-white', icon: Info },
  };

  const { bg, icon: Icon } = variants[variant] || variants.info;

  return (
    <div className={`flex items-center p-4 rounded-lg shadow-lg backdrop-blur-sm min-w-[300px] animate-fade-slide-up ${bg}`}>
      <Icon className="w-5 h-5 mr-3 flex-shrink-0" />
      <span className="flex-1 text-sm font-medium">{message}</span>
      <button onClick={onClose} className="p-1 hover:bg-black/10 rounded ml-3">
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
