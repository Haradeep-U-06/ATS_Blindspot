import React from 'react';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';
import { ToastProvider } from '../../hooks/useToast';

export function Layout({ children }) {
  return (
    <ToastProvider>
      <div className="min-h-screen bg-cream flex">
        <Sidebar />
        <div className="flex-1 ml-[220px] flex flex-col min-h-screen">
          <Topbar />
          <main className="flex-1 px-8 py-8">
            {children}
          </main>
        </div>
      </div>
    </ToastProvider>
  );
}
