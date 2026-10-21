import { Box, LinearProgress } from '@mui/material';
import type { ReactNode } from 'react';
import type { AsyncResource } from '../../hooks/useAsyncResource';
import { EmptyState } from './EmptyState';
import { ErrorState } from './ErrorState';
import { LoadingState } from './LoadingState';

interface AsyncContentProps<T> {
  resource: AsyncResource<T>;
  children: (data: T) => ReactNode;
  /** When it returns true the empty state is shown instead of children. */
  isEmpty?: (data: T) => boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  errorTitle?: string;
  loadingLabel?: string;
}

/** Consistent loading / error / empty / data rendering for a useAsyncResource result. */
export function AsyncContent<T>({
  resource,
  children,
  isEmpty,
  emptyTitle = 'Nothing to show',
  emptyDescription,
  errorTitle = 'Could not load data',
  loadingLabel = 'Loading',
}: AsyncContentProps<T>) {
  const { data, error, loading, reload } = resource;
  if (error !== null) return <ErrorState error={error} title={errorTitle} onRetry={reload} />;
  if (data === null) return <LoadingState label={loadingLabel} />;
  return (
    <Box>
      {loading && <LinearProgress aria-label="Refreshing" />}
      {isEmpty?.(data) === true ? (
        <EmptyState
          title={emptyTitle}
          {...(emptyDescription !== undefined ? { description: emptyDescription } : {})}
        />
      ) : (
        children(data)
      )}
    </Box>
  );
}
