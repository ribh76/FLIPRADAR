import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getApiError } from "../services/apiClient";

export type ServerStateKey = readonly (string | number | boolean | null)[];

type ServerQueryOptions<TData> = {
  abortOnUnmount?: boolean;
  enabled?: boolean;
  initialData?: TData;
};

type ServerQueryFn<TData> = (signal: AbortSignal) => Promise<TData>;

type ServerMutationOptions<TData, TVariables> = {
  onSuccess?: (data: TData, variables: TVariables) => void | Promise<void>;
  onError?: (message: string, variables: TVariables) => void;
};

const queryCache = new Map<string, unknown>();
const inFlightQueries = new Map<string, Promise<unknown>>();

function serializeKey(key: ServerStateKey): string {
  return JSON.stringify(key);
}

export function invalidateServerState(key: ServerStateKey): void {
  queryCache.delete(serializeKey(key));
}

async function loadQuery<TData>(
  cacheKey: string,
  queryFn: ServerQueryFn<TData>,
  signal: AbortSignal,
): Promise<TData> {
  const existing = inFlightQueries.get(cacheKey);
  if (existing) {
    return existing as Promise<TData>;
  }

  const request = queryFn(signal).finally(() => {
    inFlightQueries.delete(cacheKey);
  });
  inFlightQueries.set(cacheKey, request);
  return request;
}

export function useServerQuery<TData>(
  key: ServerStateKey,
  queryFn: ServerQueryFn<TData>,
  options: ServerQueryOptions<TData> = {},
) {
  const { abortOnUnmount = false, enabled = true, initialData } = options;
  const cacheKey = useMemo(() => serializeKey(key), [key]);
  const [data, setData] = useState<TData | undefined>(() => {
    if (queryCache.has(cacheKey)) {
      return queryCache.get(cacheKey) as TData;
    }
    return initialData;
  });
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(enabled && data === undefined);
  const [isFetching, setIsFetching] = useState(false);
  const dataRef = useRef(data);
  const controllerRef = useRef<AbortController | null>(null);
  dataRef.current = data;

  const refetch = useCallback(async () => {
    if (!enabled) {
      return undefined;
    }
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setIsFetching(true);
    setIsLoading(dataRef.current === undefined);
    setError("");
    try {
      const result = await loadQuery(cacheKey, queryFn, controller.signal);
      if (controller.signal.aborted) {
        return undefined;
      }
      queryCache.set(cacheKey, result);
      setData(result);
      return result;
    } catch (queryError) {
      if (controller.signal.aborted) {
        return undefined;
      }
      setError(getApiError(queryError));
      return undefined;
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
        setIsFetching(false);
        setIsLoading(false);
      }
    }
  }, [cacheKey, enabled, queryFn]);

  const setCachedData = useCallback(
    (value: TData) => {
      queryCache.set(cacheKey, value);
      setData(value);
    },
    [cacheKey],
  );

  useEffect(() => {
    if (!enabled) {
      setIsLoading(false);
      return;
    }
    if (queryCache.has(cacheKey)) {
      setData(queryCache.get(cacheKey) as TData);
      setIsLoading(false);
      return;
    }
    void refetch();
    return () => {
      if (abortOnUnmount) {
        controllerRef.current?.abort();
        controllerRef.current = null;
        // Type-ahead and route-abandoned reads should neither consume memory nor
        // repopulate the result cache after the user has moved on.
        queryCache.delete(cacheKey);
      }
    };
  }, [abortOnUnmount, cacheKey, enabled, refetch]);

  return {
    data,
    error,
    isFetching,
    isLoading,
    refetch,
    setData: setCachedData,
  };
}

export function useServerMutation<TData, TVariables>(
  mutationFn: (variables: TVariables) => Promise<TData>,
  options: ServerMutationOptions<TData, TVariables> = {},
) {
  const [error, setError] = useState("");
  const [isPending, setIsPending] = useState(false);

  const mutate = useCallback(
    async (variables: TVariables) => {
      setIsPending(true);
      setError("");
      try {
        const result = await mutationFn(variables);
        await options.onSuccess?.(result, variables);
        return result;
      } catch (mutationError) {
        const message = getApiError(mutationError);
        setError(message);
        options.onError?.(message, variables);
        return undefined;
      } finally {
        setIsPending(false);
      }
    },
    [mutationFn, options],
  );

  return {
    error,
    isPending,
    mutate,
    setError,
  };
}
