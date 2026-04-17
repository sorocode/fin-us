import { useCallback, useState, type FormEvent } from 'react';
import axios from 'axios';
import type { AnalysisReport } from '../types';

function axiosDetail(err: unknown): string {
  if (axios.isAxiosError(err) && err.response?.data?.detail) {
    const d = err.response.data.detail;
    return typeof d === 'string' ? d : JSON.stringify(d);
  }
  return '서버와 통신 중 오류가 발생했습니다.';
}

export function useFinUsDashboard() {
  const [stock, setStock] = useState('');
  const [provider, setProvider] = useState('openai');
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [rawNews, setRawNews] = useState<string[]>([]);
  const [rawTrend, setRawTrend] = useState<string | null>(null);
  const [error, setError] = useState('');

  const resetForRequest = useCallback(() => {
    setError('');
    setReport(null);
    setRawNews([]);
    setRawTrend(null);
  }, []);

  const handleAnalyze = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      if (!stock) return;
      setLoading(true);
      resetForRequest();
      try {
        const params = new URLSearchParams({ stock, provider });
        const response = await axios.get(`/api/v1/analyze?${params.toString()}`);
        if (response.data.status === 'success') setReport(response.data.data);
        else setError('분석 데이터를 가져오지 못했습니다.');
      } catch (err: unknown) {
        setError(axiosDetail(err));
      } finally {
        setLoading(false);
      }
    },
    [provider, resetForRequest, stock],
  );

  const handleFetchData = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      if (!stock) return;
      setLoading(true);
      resetForRequest();
      try {
        const q = new URLSearchParams({ stock }).toString();
        const [newsRes, trendRes] = await Promise.all([
          axios.get(`/api/v1/news?${q}`),
          axios.get(`/api/v1/trading/trend?${q}`),
        ]);
        if (newsRes.data.status === 'success') setRawNews(newsRes.data.data.news);
        if (trendRes.data.status === 'success') setRawTrend(trendRes.data.data.trend);
      } catch {
        setError('데이터 수집 중 오류가 발생했습니다.');
      } finally {
        setLoading(false);
      }
    },
    [resetForRequest, stock],
  );

  return {
    stock,
    setStock,
    provider,
    setProvider,
    loading,
    report,
    rawNews,
    rawTrend,
    error,
    handleAnalyze,
    handleFetchData,
  };
}
