import React from 'react';
import { Search } from 'lucide-react';

interface EmptyStateProps {
  loading: boolean;
}

const EmptyState: React.FC<EmptyStateProps> = ({ loading }) => {
  if (loading) return null;

  return (
    <div className="text-center py-40 bg-white rounded-[3rem] border-4 border-dashed border-slate-100 mt-10">
      <div className="inline-flex items-center justify-center w-32 h-32 bg-slate-50 rounded-full mb-8 shadow-inner">
        <Search className="w-12 h-12 text-slate-200" />
      </div>
      <p className="text-slate-300 font-black text-2xl tracking-tight">Ready to Analyze Market Data</p>
      <p className="text-slate-200 font-bold mt-2">Enter a ticker or company name to begin</p>
    </div>
  );
};

export default EmptyState;
