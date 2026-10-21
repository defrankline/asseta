import { useCallback, useState } from 'react';
import { machineService } from '../../../api/services/machineService';
import type { AreaDto, CategoryDto } from '../../../api/types';
import { useAsyncResource } from '../../../hooks/useAsyncResource';

export type LookupKind = 'category' | 'area';

export interface PendingLookup {
  kind: LookupKind;
  /** Selects the newly created record in the form that asked for it. */
  apply: (id: string) => void;
}

/** Categories + operating areas for machine forms, with inline "create new" requests. */
export function useMachineLookups() {
  const loadCategories = useCallback(
    (signal: AbortSignal) => machineService.listCategories(signal),
    [],
  );
  const loadAreas = useCallback((signal: AbortSignal) => machineService.listAreas(signal), []);
  const categoryResource = useAsyncResource(loadCategories);
  const areaResource = useAsyncResource(loadAreas);
  const [extraCategories, setExtraCategories] = useState<CategoryDto[]>([]);
  const [extraAreas, setExtraAreas] = useState<AreaDto[]>([]);
  const [pending, setPending] = useState<PendingLookup | null>(null);

  const merge = <T extends { id: string }>(base: T[] | null, extra: T[]) => [
    ...(base ?? []),
    ...extra.filter((e) => !(base ?? []).some((b) => b.id === e.id)),
  ];

  return {
    categories: merge(categoryResource.data, extraCategories),
    areas: merge(areaResource.data, extraAreas),
    loadError: categoryResource.error ?? areaResource.error,
    pending,
    requestNew: (kind: LookupKind, apply: (id: string) => void) => {
      setPending({ kind, apply });
    },
    closePending: () => {
      setPending(null);
    },
    categoryCreated: (c: CategoryDto) => {
      setExtraCategories((xs) => [...xs, c]);
      pending?.apply(c.id);
    },
    areaCreated: (a: AreaDto) => {
      setExtraAreas((xs) => [...xs, a]);
      pending?.apply(a.id);
    },
  };
}

export type MachineLookups = ReturnType<typeof useMachineLookups>;
