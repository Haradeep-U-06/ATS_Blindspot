import React from 'react';
import { Loader2 } from 'lucide-react';

export function Button({ 
  children, 
  variant = 'primary', 
  isLoading, 
  disabled, 
  className = "", 
  ...props 
}) {
  const baseStyle = "inline-flex items-center justify-center rounded-lg px-4 py-2 font-medium transition-all duration-200 active:scale-[0.98]";
  
  const variants = {
    primary: "bg-primary text-white hover:bg-mid shadow-sm hover:shadow",
    secondary: "bg-soft text-dark hover:bg-secondary border border-transparent",
    outline: "bg-transparent border border-mid/30 text-dark hover:bg-soft",
    danger: "bg-error/10 text-error hover:bg-error hover:text-white"
  };

  const isDisabled = disabled || isLoading;
  
  return (
    <button 
      disabled={isDisabled}
      className={`${baseStyle} ${variants[variant]} ${isDisabled ? 'opacity-50 cursor-not-allowed' : ''} ${className}`}
      {...props}
    >
      {isLoading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
      {children}
    </button>
  );
}
