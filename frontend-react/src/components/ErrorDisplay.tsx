import React from 'react';
import { AlertCircle } from 'lucide-react';

interface ErrorDisplayProps {
  error: string;
}

const ErrorDisplay: React.FC<ErrorDisplayProps> = ({ error }) => {
  if (!error) return null;
  return (
    <div className="mb-8 p-4 bg-rose-50 border border-rose-100 rounded-2xl text-rose-600 flex items-center gap-3 font-medium shadow-sm max-w-2xl mx-auto">
      <AlertCircle className="w-6 h-6" /> {error}
    </div>
  );
};

export default ErrorDisplay;
