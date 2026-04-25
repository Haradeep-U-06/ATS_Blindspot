import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, PlusCircle, Leaf } from 'lucide-react';

const NAV = [
  { to: '/', end: true, icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/jobs/new', end: false, icon: PlusCircle, label: 'New Job' },
];

export function Sidebar() {
  return (
    <aside className="w-[220px] bg-dark h-screen fixed top-0 left-0 flex flex-col z-40 select-none">
      {/* Logo */}
      <div className="h-[64px] flex items-center px-5 border-b border-white/8 shrink-0">
        <div className="w-8 h-8 rounded-xl bg-primary/20 border border-primary/30 flex items-center justify-center mr-3">
          <Leaf className="w-4 h-4 text-primary" />
        </div>
        <span className="font-heading font-bold text-[17px] text-white tracking-wide">ATS</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 pt-4 space-y-1">
        {NAV.map(({ to, end, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 ${
                isActive
                  ? 'bg-white/10 text-white'
                  : 'text-white/45 hover:text-white/80 hover:bg-white/6'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <div className={`w-1 h-5 rounded-full mr-3 flex-shrink-0 transition-all ${isActive ? 'bg-primary' : 'bg-transparent'}`} />
                <Icon className="w-4 h-4 mr-2.5 flex-shrink-0" />
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-white/8">
        <p className="text-[10px] text-white/20 font-mono tracking-wider">v1.0.0 · organic</p>
      </div>
    </aside>
  );
}
