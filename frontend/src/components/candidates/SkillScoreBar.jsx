import React, { useEffect, useState } from 'react';

export function SkillScoreBar({ label, score }) {
  const [width, setWidth] = useState(0);

  useEffect(() => {
    // Animate on mount
    const timer = setTimeout(() => setWidth(score || 0), 100);
    return () => clearTimeout(timer);
  }, [score]);

  const getColorClass = () => {
    if (score >= 80) return 'bg-primary';
    if (score >= 60) return 'bg-secondary';
    if (score >= 40) return 'bg-warning';
    return 'bg-error';
  };

  return (
    <div className="mb-4">
      <div className="flex justify-between text-sm mb-1">
        <span className="font-medium text-dark">{label}</span>
        <span className="font-mono text-mid">{Math.round(score || 0)}</span>
      </div>
      <div className="w-full h-2 bg-mid/20 rounded-full overflow-hidden shadow-inner">
        <div 
          className={`h-full rounded-full transition-all duration-1000 ease-out ${getColorClass()}`}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}
