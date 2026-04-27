import React from 'react';
import { ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { TrendItem } from '../types';
import { formatNumber } from '../utils/formatters';

interface StockHeaderProps {
  stock: string;
  latest: TrendItem;
}

const StockHeader: React.FC<StockHeaderProps> = ({ stock, latest }) => {
  return (
    <div className="mb-12 text-center animate-in zoom-in-95 duration-700">
      <h2 className="text-4xl font-black text-slate-900 mb-2">{stock || latest.date}</h2>
      <div className="flex items-center justify-center gap-6">
        <span className="text-8xl font-black text-slate-900 tracking-tighter">
          {formatNumber(latest.price)}
        </span>
        <div className={`flex flex-col items-start ${latest.isUp ? 'text-rose-500' : 'text-indigo-500'}`}>
          <div className="flex items-center font-black text-3xl">
            {latest.isUp ? <ArrowUpRight className="w-8 h-8" /> : <ArrowDownRight className="w-8 h-8" />}
            {latest.changeVal}
          </div>
          <div className="font-bold text-xl">{latest.changePct}</div>
        </div>
      </div>
    </div>
  );
};

export default StockHeader;
