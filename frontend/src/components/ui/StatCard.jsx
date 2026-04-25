import React from 'react';

export function StatCard({ icon: Icon, label, value, delta }) {
  return (
    <div className="relative overflow-hidden bg-white rounded-2xl border border-mid/10 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 p-6 flex flex-col group">
      {/* Accent bar */}
      <div className="absolute top-0 left-0 right-0 h-[3px] bg-gradient-to-r from-primary to-secondary" />

      <div className="flex items-center justify-between mb-5">
        <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-mid/70">{label}</span>
        <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary group-hover:bg-primary/20 group-hover:scale-105 transition-all">
          <Icon className="w-5 h-5" />
        </div>
      </div>

      <div className="flex items-end gap-2 mt-auto">
        <span className="font-heading text-[2.5rem] font-bold text-dark leading-none">{value}</span>
        {delta && (
          <span className={`text-sm font-semibold mb-1 ${delta.startsWith('+') ? 'text-primary' : 'text-error'}`}>
            {delta}
          </span>
        )}
      </div>
    </div>
  );
}
