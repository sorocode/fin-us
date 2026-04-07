import React, { useState } from 'react';
import axios from 'axios';
import { 
  Search, 
  TrendingUp, 
  TrendingDown, 
  Minus, 
  Newspaper, 
  BarChart3, 
  AlertCircle,
  Loader2,
  Settings2,
  Database,
  Activity,
  Layers,
  ArrowUpRight,
  ArrowDownRight
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
  ComposedChart,
  Area
} from 'recharts';

interface TradingSignal {
  decision: 'BUY' | 'SELL' | 'HOLD';
  confidence_score: number;
  reason: string;
  target_stock: string;
}

interface AnalysisReport {
  summary: string;
  details: TradingSignal;
  source_news: string[];
  trading_trend: string | null;
}

const formatNumber = (num: number) => {
  return new Intl.NumberFormat('ko-KR').format(num);
};

const parseTrendData = (trendStr: string | null) => {
  if (!trendStr) return [];
  const lines = trendStr.split('\n').filter(l => l.includes('|'));
  return lines.map(line => {
    const parts = line.split('|').map(p => p.trim());
    const date = parts[0]?.split(' ')[0] || '';
    const closeStr = parts[1]?.replace('종가: ', '').replace(/,/g, '') || '0';
    // parts[2] looks like "변동: 상승 6,900 (+3.71%)"
    const changeFull = parts[2]?.replace('변동: ', '') || '';
    const isUp = changeFull.includes('상승');
    const changeVal = changeFull.replace('상승 ', '').replace('하락 ', '').split(' (')[0];
    const changePct = changeFull.includes('(') ? changeFull.split('(')[1].replace(')', '') : '0%';
    const foreStr = parts[3]?.replace('외인: ', '').replace(/,/g, '') || '0';
    const instStr = parts[4]?.replace('기관: ', '').replace(/,/g, '') || '0';
    const volStr = parts[5]?.replace('거래량: ', '').replace(/,/g, '') || '0';
    
    return {
      date: date.substring(5),
      price: parseInt(closeStr),
      changeVal,
      changePct,
      isUp,
      foreigner: parseInt(foreStr),
      institution: parseInt(instStr),
      volume: parseInt(volStr)
    };
  }).reverse();
};

export default function App() {
  const [stock, setStock] = useState('');
  const [provider, setProvider] = useState('openai');
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [rawNews, setRawNews] = useState<string[]>([]);
  const [rawTrend, setRawTrend] = useState<string | null>(null);
  const [error, setError] = useState('');

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stock) return;
    setLoading(true); setError(''); setReport(null); setRawNews([]); setRawTrend(null);
    try {
      const response = await axios.get(`/api/v1/analyze?stock=${stock}&provider=${provider}`);
      if (response.data.status === 'success') setReport(response.data.data);
      else setError('분석 데이터를 가져오지 못했습니다.');
    } catch (err: any) {
      setError(err.response?.data?.detail || '서버와 통신 중 오류가 발생했습니다.');
    } finally { setLoading(false); }
  };

  const handleFetchData = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stock) return;
    setLoading(true); setError(''); setReport(null); setRawNews([]); setRawTrend(null);
    try {
      const [newsRes, trendRes] = await Promise.all([
        axios.get(`/api/v1/news?stock=${stock}`),
        axios.get(`/api/v1/trading/trend?stock=${stock}`)
      ]);
      if (newsRes.data.status === 'success') setRawNews(newsRes.data.data.news);
      if (trendRes.data.status === 'success') setRawTrend(trendRes.data.data.trend);
    } catch (err: any) { setError('데이터 수집 중 오류가 발생했습니다.'); }
    finally { setLoading(false); }
  };

  const currentTrend = report?.trading_trend || rawTrend;
  const currentNews = report?.source_news || rawNews;
  const trendData = parseTrendData(currentTrend);
  const latest = trendData[trendData.length - 1];

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 bg-slate-50 min-h-screen">
      <header className="mb-10 flex flex-col items-center">
        <h1 className="text-2xl font-black text-slate-400 mb-2 tracking-widest uppercase">Fin-Us Agent</h1>
      </header>

      {/* Search Controls */}
      <div className="mb-12">
        <form className="flex flex-col md:flex-row gap-4 items-center justify-center">
          <div className="relative w-full max-w-lg">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-300 w-6 h-6" />
            <input
              type="text" value={stock} onChange={(e) => setStock(e.target.value)}
              placeholder="분석할 종목명 (예: 삼성전자)"
              className="w-full pl-12 pr-4 py-4 rounded-2xl border-none focus:ring-4 focus:ring-indigo-100 focus:outline-none transition-all shadow-xl font-medium text-lg"
            />
          </div>
          
          <div className="flex gap-3">
            <button onClick={handleFetchData} disabled={loading}
              className="bg-white hover:bg-slate-50 text-slate-600 px-6 py-4 rounded-2xl font-bold transition-all shadow-lg border border-slate-100"
            >
              DATA ONLY
            </button>
            
            <div className="flex items-center gap-2 bg-indigo-600 px-3 py-2 rounded-2xl shadow-indigo-200 shadow-xl">
              <select value={provider} onChange={(e) => setProvider(e.target.value)}
                className="focus:outline-none bg-transparent text-xs font-black text-white mr-2 px-2"
              >
                <option value="openai" className="text-slate-900">GPT-5.4-mini</option>
                <option value="anthropic" className="text-slate-900">Claude-Sonnet-4-6</option>
              </select>
              <button onClick={handleAnalyze} disabled={loading}
                className="bg-white hover:bg-slate-100 disabled:bg-slate-300 text-indigo-600 px-6 py-2 rounded-xl font-black transition-all"
              >
                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'ANALYZE'}
              </button>
            </div>
          </div>
        </form>
      </div>

      {error && (
        <div className="mb-8 p-4 bg-rose-50 border border-rose-100 rounded-2xl text-rose-600 flex items-center gap-3 font-medium shadow-sm max-w-2xl mx-auto">
          <AlertCircle className="w-6 h-6" /> {error}
        </div>
      )}

      {latest && (
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
      )}

      {(report || currentNews.length > 0 || currentTrend) && (
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-8">
          
          {/* Side Info Column */}
          <div className="xl:col-span-1 space-y-6">
            {report && (
              <div className={`p-8 rounded-[2rem] border-none shadow-2xl relative overflow-hidden ${
                report.details.decision === 'BUY' ? 'bg-gradient-to-br from-rose-500 to-rose-600 text-white' :
                report.details.decision === 'SELL' ? 'bg-gradient-to-br from-indigo-500 to-indigo-600 text-white' :
                'bg-gradient-to-br from-slate-500 to-slate-600 text-white'
              }`}>
                <div className="flex justify-between items-center mb-6">
                  <span className="text-xs font-black uppercase tracking-widest opacity-80">AI STRATEGY</span>
                  {report.details.decision === 'BUY' ? <TrendingUp className="w-8 h-8 opacity-50" /> :
                   report.details.decision === 'SELL' ? <TrendingDown className="w-8 h-8 opacity-50" /> : <Minus className="w-8 h-8 opacity-50" />}
                </div>
                <h2 className="text-7xl font-black mb-4 tracking-tighter">{report.details.decision}</h2>
                <div className="space-y-2 mb-8">
                  <div className="flex justify-between text-xs font-black opacity-80 uppercase">
                    <span>Confidence</span>
                    <span>{(report.details.confidence_score * 100).toFixed(0)}%</span>
                  </div>
                  <div className="h-3 w-full bg-white/20 rounded-full overflow-hidden">
                    <div className="h-full bg-white transition-all shadow-[0_0_10px_rgba(255,255,255,0.5)]" style={{ width: `${report.details.confidence_score * 100}%` }} />
                  </div>
                </div>
                <p className="text-sm leading-relaxed font-bold bg-black/10 p-5 rounded-2xl backdrop-blur-sm">
                  {report.details.reason}
                </p>
              </div>
            )}

            <div className="bg-white p-6 rounded-[2rem] shadow-xl border border-slate-50">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2 bg-indigo-50 rounded-lg"><Newspaper className="w-5 h-5 text-indigo-600" /></div>
                <h3 className="text-slate-800 font-black tracking-tight text-lg">Market Context</h3>
              </div>
              <ul className="space-y-4">
                {currentNews.map((news, i) => (
                  <li key={i} className="text-sm text-slate-500 font-medium leading-snug hover:text-indigo-600 transition-colors cursor-default border-b border-slate-50 pb-3 last:border-0">
                    {news}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Main Visualizations */}
          <div className="xl:col-span-3 space-y-8">
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
               {/* Price Area */}
               <div className="bg-white p-8 rounded-[2.5rem] shadow-2xl border border-slate-50">
                  <div className="flex items-center gap-3 mb-8">
                    <div className="p-2 bg-rose-50 rounded-lg"><Activity className="w-6 h-6 text-rose-500" /></div>
                    <h3 className="text-slate-800 font-black text-xl tracking-tight">Price Trend</h3>
                  </div>
                  <div className="h-64 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <Area data={trendData} type="monotone" dataKey="price" fill="#fff1f2" stroke="#fb7185" strokeWidth={4} />
                    </ResponsiveContainer>
                  </div>
               </div>
               {/* Volume Area */}
               <div className="bg-white p-8 rounded-[2.5rem] shadow-2xl border border-slate-50">
                  <div className="flex items-center gap-3 mb-8">
                    <div className="p-2 bg-slate-50 rounded-lg"><BarChart3 className="w-6 h-6 text-slate-500" /></div>
                    <h3 className="text-slate-800 font-black text-xl tracking-tight">Liquidity</h3>
                  </div>
                  <div className="h-64 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <Bar data={trendData} dataKey="volume" fill="#f1f5f9" radius={[4, 4, 0, 0]} />
                    </ResponsiveContainer>
                  </div>
               </div>
            </div>

            {/* Investor Flow Chart */}
            <div className="bg-white p-10 rounded-[2.5rem] shadow-2xl border border-slate-50">
              <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-indigo-50 rounded-lg"><Layers className="w-6 h-6 text-indigo-500" /></div>
                  <h3 className="text-slate-800 font-black text-xl tracking-tight">Investor Flow</h3>
                </div>
                <div className="flex gap-4">
                  <div className="flex items-center gap-2"><div className="w-4 h-1.5 rounded-full bg-rose-400" /><span className="text-[10px] font-black text-slate-400 uppercase">Foreigner</span></div>
                  <div className="flex items-center gap-2"><div className="w-4 h-1.5 rounded-full bg-indigo-400" /><span className="text-[10px] font-black text-slate-400 uppercase">Institutional</span></div>
                </div>
              </div>
              
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={trendData} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{fontSize: 12, fontWeight: 700, fill: '#cbd5e1'}} />
                    <YAxis hide />
                    <Tooltip 
                      cursor={{fill: '#f8fafc'}}
                      contentStyle={{borderRadius: '24px', border: 'none', boxShadow: '0 25px 50px -12px rgb(0 0 0 / 0.15)', padding: '20px'}}
                      formatter={(value: number) => [formatNumber(value), '']}
                    />
                    <ReferenceLine y={0} stroke="#cbd5e1" strokeWidth={2} />
                    <Bar dataKey="foreigner" radius={[6, 6, 0, 0]}>
                      {trendData.map((entry, index) => (
                        <Cell key={`cell-f-${index}`} fill={entry.foreigner > 0 ? '#fb7185' : '#fda4af'} />
                      ))}
                    </Bar>
                    <Bar dataKey="institution" radius={[6, 6, 0, 0]}>
                      {trendData.map((entry, index) => (
                        <Cell key={`cell-i-${index}`} fill={entry.institution > 0 ? '#6366f1' : '#a5b4fc'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {report && (
                <div className="mt-10 p-8 bg-slate-900 rounded-3xl shadow-indigo-100 shadow-2xl relative overflow-hidden group">
                  <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                    <Activity className="w-24 h-24 text-white" />
                  </div>
                  <h4 className="text-[10px] font-black text-indigo-400 mb-3 uppercase tracking-[0.3em]">Neural Synthesis</h4>
                  <p className="text-white text-lg leading-relaxed font-bold tracking-tight">"{report.summary}"</p>
                </div>
              )}
            </div>
          </div>

        </div>
      )}

      {!report && currentNews.length === 0 && !loading && (
        <div className="text-center py-40 bg-white rounded-[3rem] border-4 border-dashed border-slate-100 mt-10">
          <div className="inline-flex items-center justify-center w-32 h-32 bg-slate-50 rounded-full mb-8 shadow-inner">
            <Search className="w-12 h-12 text-slate-200" />
          </div>
          <p className="text-slate-300 font-black text-2xl tracking-tight">Ready to Analyze Market Data</p>
          <p className="text-slate-200 font-bold mt-2">Enter a ticker or company name to begin</p>
        </div>
      )}
    </div>
  );
}
