import React, { useState } from 'react';
import axios from 'axios';
import { AnalysisReport } from './types';
import { parseTrendData } from './utils/parsers';
import Header from './components/Header';
import SearchForm from './components/SearchForm';
import ErrorDisplay from './components/ErrorDisplay';
import StockHeader from './components/StockHeader';
import ReportSidebar from './components/ReportSidebar';
import MainDashboard from './components/MainDashboard';
import EmptyState from './components/EmptyState';

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
      console.log(`Analyzing ${stock} with ${provider}...`);
      const response = await axios.get(`/api/v1/analyze?stock=${stock}&provider=${provider}`);
      console.log("Analyze response:", response.data);
      if (response.data.status === 'success') setReport(response.data.data);
      else setError('분석 데이터를 가져오지 못했습니다.');
    } catch (err: any) {
      console.error("Analyze error:", err);
      setError(err.response?.data?.detail || '서버와 통신 중 오류가 발생했습니다.');
    } finally { setLoading(false); }
  };

  const handleFetchData = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stock) return;
    setLoading(true); setError(''); setReport(null); setRawNews([]); setRawTrend(null);
    try {
      console.log(`Fetching data for ${stock}...`);
      const [newsRes, trendRes] = await Promise.all([
        axios.get(`/api/v1/news?stock=${stock}`),
        axios.get(`/api/v1/trading/trend?stock=${stock}`)
      ]);
      console.log("News response:", newsRes.data);
      console.log("Trend response:", trendRes.data);
      if (newsRes.data.status === 'success') setRawNews(newsRes.data.data.news);
      if (trendRes.data.status === 'success') setRawTrend(trendRes.data.data.trend);
    } catch (err: any) { 
      console.error("Fetch data error:", err);
      setError('데이터 수집 중 오류가 발생했습니다.'); 
    }
    finally { setLoading(false); }
  };

  const currentTrend = report?.trading_trend || rawTrend;
  const currentNews = report?.source_news || rawNews;
  const trendData = parseTrendData(currentTrend);
  const latest = trendData[trendData.length - 1];

  const hasData = report || currentNews.length > 0 || currentTrend;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 bg-slate-50 min-h-screen">
      <Header />

      <SearchForm
        stock={stock}
        setStock={setStock}
        provider={provider}
        setProvider={setProvider}
        loading={loading}
        handleFetchData={handleFetchData}
        handleAnalyze={handleAnalyze}
      />

      <ErrorDisplay error={error} />

      {latest && <StockHeader stock={stock} latest={latest} />}

      {hasData ? (
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-8">
          <ReportSidebar report={report} currentNews={currentNews} />
          <MainDashboard trendData={trendData} report={report} />
        </div>
      ) : (
        <EmptyState loading={loading} />
      )}
    </div>
  );
}
