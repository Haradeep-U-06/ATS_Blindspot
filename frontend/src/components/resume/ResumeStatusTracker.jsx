import React from 'react';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { ProgressBar } from '../ui/ProgressBar';

export function ResumeStatusTracker({ status, error }) {
  const steps = [
    { key: 'uploaded', label: 'Uploaded' },
    { key: 'parsing', label: 'Parsing' },
    { key: 'enriching', label: 'Enriching' },
    { key: 'vectorizing', label: 'Embedding' },
    { key: 'ready_for_evaluation', label: 'Ready ✓' }
  ];

  // Helper to determine step states
  const getStepIndex = (currentStatus) => {
    if (!currentStatus) return -1;
    if (['failed', 'parse_failed', 'vector_failed', 'completed_with_errors'].includes(currentStatus)) return -1;
    return steps.findIndex(s => s.key === currentStatus);
  };

  const currentIndex = getStepIndex(status);
  const isFailed = ['failed', 'parse_failed', 'vector_failed', 'completed_with_errors'].includes(status);
  
  // Calculate progress %
  let progress = 0;
  if (isFailed) progress = 100;
  else if (currentIndex === steps.length - 1) progress = 100;
  else if (currentIndex >= 0) progress = ((currentIndex + 1) / steps.length) * 100;

  return (
    <Card className="mt-8 animate-fade-slide-up">
      <div className="flex justify-between items-center mb-6">
        <h3 className="font-heading font-semibold text-lg">Processing Pipeline</h3>
        <Badge status={status} />
      </div>

      <div className="relative pt-2">
        <ProgressBar value={progress} animated={!isFailed && currentIndex >= 0 && currentIndex < steps.length - 1} className={isFailed ? '[&>div]:bg-error' : ''} />
        
        <div className="flex justify-between mt-4">
          {steps.map((step, idx) => {
            const isActive = idx === currentIndex;
            const isDone = idx < currentIndex || currentIndex === steps.length - 1;
            
            let color = 'text-mid/50';
            if (isActive && !isFailed) color = 'text-primary font-bold';
            if (isDone && !isFailed) color = 'text-dark font-medium';
            if (isFailed && isActive) color = 'text-error font-bold'; 

            return (
              <div key={step.key} className={`text-xs md:text-sm text-center ${color} transition-colors flex-1`}>
                {step.label}
              </div>
            );
          })}
        </div>
      </div>
      
      {isFailed && (
        <div className="mt-6 p-4 bg-error/10 border border-error/20 rounded-lg text-error text-sm">
          <strong>Error Processing Resume:</strong> {error || 'An unknown error occurred during the pipeline execution.'}
        </div>
      )}
    </Card>
  );
}
