import React from 'react';
import { PulsingDot } from '../ui/PulsingDot';

export function EvaluationStatusBanner({ status, message }) {
  const isError = status === 'failed' || status === 'completed_with_errors';
  const bgClass = isError ? 'bg-error/10 border-error/20' : 'bg-primary/10 border-primary/20';
  const titleColor = isError ? 'text-error' : 'text-primary';
  
  return (
    <div className={`${bgClass} border rounded-lg p-4 flex items-center gap-3 animate-fade-slide-up mb-6`}>
      {status === 'processing' || status === 'queued' ? (
        <PulsingDot className={isError ? "bg-error" : "bg-primary"} />
      ) : null}
      <div>
        <p className={`font-medium ${titleColor}`}>
          {isError ? 'Evaluation Error' : 'Evaluating Candidates'}
        </p>
        <p className="text-sm text-mid">{message || `Status: ${status}`}</p>
      </div>
    </div>
  );
}
