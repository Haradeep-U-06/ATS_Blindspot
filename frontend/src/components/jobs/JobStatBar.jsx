import React from 'react';
import { Card } from '../ui/Card';

export function JobStatBar({ stats }) {
  const items = [
    { label: 'Uploaded', value: stats?.uploaded || 0, icon: '📤' },
    { label: 'Processing', value: stats?.processing || 0, icon: '⚙️' },
    { label: 'Ready', value: stats?.ready_for_evaluation || stats?.ready || 0, icon: '✅' },
    { label: 'Evaluating', value: stats?.evaluating || 0, icon: '🔄' },
    { label: 'Completed', value: stats?.completed || 0, icon: '🏁' },
    { label: 'Failed', value: stats?.failed || 0, icon: '❌' },
  ];

  return (
    <Card className="!p-4 bg-light/50">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {items.map((item, i) => (
          <React.Fragment key={i}>
            <div className="flex items-center gap-3">
              <span className="text-xl">{item.icon}</span>
              <div className="flex flex-col">
                <span className="text-[10px] text-mid uppercase tracking-wider font-bold mb-0.5">{item.label}</span>
                <span className="font-mono text-lg leading-none font-bold text-dark">{item.value}</span>
              </div>
            </div>
            {i < items.length - 1 && <div className="hidden md:block w-px h-8 bg-mid/20"></div>}
          </React.Fragment>
        ))}
      </div>
    </Card>
  );
}
