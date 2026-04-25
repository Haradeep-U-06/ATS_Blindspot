import React from 'react';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';

export function Badge({ status, text, className = "" }) {
  const getStyles = () => {
    switch (status) {
      case 'processing':
      case 'queued':
      case 'running':
      case 'evaluating':
        return 'bg-warning/20 text-warning';
      case 'ready':
      case 'ready_for_evaluation':
        return 'bg-primary/20 text-primary';
      case 'completed':
      case 'strong_fit':
        return 'bg-dark/10 text-dark'; // wait, prompt says completed -> dark green
      case 'failed':
      case 'completed_with_errors':
      case 'parse_failed':
      case 'vector_failed':
        return 'bg-error/20 text-error';
      default:
        return 'bg-mid/10 text-mid';
    }
  };

  const renderIcon = () => {
    if (['processing', 'queued', 'running', 'evaluating'].includes(status)) {
      return <Loader2 className="w-3 h-3 mr-1 animate-spin" />;
    }
    if (status === 'completed') {
      return <CheckCircle className="w-3 h-3 mr-1" />;
    }
    if (['failed', 'completed_with_errors', 'parse_failed', 'vector_failed'].includes(status)) {
      return <XCircle className="w-3 h-3 mr-1" />;
    }
    return null;
  };

  // Adjust for completed styling as per prompt: dark green + checkmark
  const isCompleted = status === 'completed';
  const customStyle = isCompleted ? 'bg-mid text-white' : getStyles();

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${customStyle} ${className}`}>
      {renderIcon()}
      {text || status.replace(/_/g, ' ')}
    </span>
  );
}
