import React, { useEffect, useState } from 'react';

export function ScoreGauge({ score, size = 160 }) {
  const [animatedScore, setAnimatedScore] = useState(0);
  const strokeWidth = size * 0.08;
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  
  useEffect(() => {
    setAnimatedScore(score || 0);
  }, [score]);

  const offset = circumference - (animatedScore / 100) * circumference;

  const getColorClass = () => {
    if (score >= 80) return 'stroke-primary text-primary';
    if (score >= 60) return 'stroke-secondary text-secondary';
    if (score >= 40) return 'stroke-warning text-warning';
    return 'stroke-error text-error';
  };

  return (
    <div className="relative flex flex-col items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-mid/10"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={`transition-all duration-1000 ease-out ${getColorClass()}`}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`font-mono text-4xl font-bold ${getColorClass().split(' ')[1]}`}>
          {Math.round(animatedScore)}
        </span>
        <span className="text-xs text-mid uppercase tracking-widest font-semibold mt-1">Score</span>
      </div>
    </div>
  );
}
