import { useCallback, useEffect, useMemo, useState } from "react";
import { getApiError } from "../services/apiClient";

export type ServerStateKey = readonly (string | number | boolean | null)[];

type ServerQueryOptions<TData> = {
  enabled?: boolean;
  initialData?: TData;
};

type ServerMutationOptions<TData, TVariables> = {
  onSuccess?: (data: TData, variables: TVariables) => void | Promise<void>;
  onError?: (message: string, variables: TVariables) => void;
};

const queryCache = new Map<string, unknown>();

function serializeKey(key: ServerStateKey): string {
  return JSON.stringify(key);
}

export function invalidateServerState(key: ServerStateKey): void {
  queryCache.delete(serializeKey(key));
}

export function useServerQuery<TData>(
  key: ServerStateKey,
  queryFn: () => Promise<TData>,
  options: ServerQueryOptions<TData> = {},
) {
  const { enabled = true, initialData } = options;
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

  const refetch = useCallback(async () => {
    if (!enabled) {
      return undefined;
    }
    setIsFetching(true);
    setIsLoading(data === undefined);
    setError("");
    try {
      const result = await queryFn();
      queryCache.set(cacheKey, result);
      setData(result);
      return result;
    } catch (queryError) {
      setError(getApiError(queryError));
      return undefined;
    } finally {
      setIsFetching(false);
      setIsLoading(false);
    }
  }, [cacheKey, data, enabled, queryFn]);

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
  }, [cacheKey, enabled, refetch]);

  return {
    data,
    error,
    isFetching,
    isLoading,
    refetch,
    setData,
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
