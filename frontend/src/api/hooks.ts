import { useState, useCallback, useEffect, useRef } from 'react';
import apiClient from './client';
import { AxiosError } from 'axios';

interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

// 자동 fetch 훅 — mount 시 fetcher 호출, deps 변경 시 재호출
export function useApiData<T>(
  fetcher: () => Promise<T | null>,
  deps: unknown[] = [],
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetcher();
      if (mountedRef.current) {
        setData(result);
        setLoading(false);
      }
    } catch (err: unknown) {
      if (!mountedRef.current) return;
      const msg = err instanceof AxiosError
        ? (err.response?.data as { detail?: string } | undefined)?.detail ?? err.message
        : '알 수 없는 오류';
      setError(msg);
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    mountedRef.current = true;
    void refetch();
    return () => { mountedRef.current = false; };
  }, [refetch]);

  return { data, loading, error, refetch };
}

// GET 훅
export function useApiGet<T>() {
  const [state, setState] = useState<UseApiState<T>>({
    data: null, loading: false, error: null,
  });

  const execute = useCallback(async (url: string) => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    try {
      const res = await apiClient.get<T>(url);
      setState({ data: res.data, loading: false, error: null });
      return res.data;
    } catch (err: unknown) {
      const msg = err instanceof AxiosError
        ? (err.response?.data as { detail?: string } | undefined)?.detail ?? err.message
        : '알 수 없는 오류';
      setState({ data: null, loading: false, error: msg });
      throw err;
    }
  }, []);

  return { ...state, execute };
}

// POST 훅
export function useApiPost<T, B = unknown>() {
  const [state, setState] = useState<UseApiState<T>>({
    data: null, loading: false, error: null,
  });

  const execute = useCallback(async (url: string, body: B) => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    try {
      const res = await apiClient.post<T>(url, body);
      setState({ data: res.data, loading: false, error: null });
      return res.data;
    } catch (err: unknown) {
      const msg = err instanceof AxiosError
        ? (err.response?.data as { detail?: string } | undefined)?.detail ?? err.message
        : '알 수 없는 오류';
      setState({ data: null, loading: false, error: msg });
      throw err;
    }
  }, []);

  return { ...state, execute };
}
