import { useState } from 'react';
import type { AreaDto, CategoryDto } from '../../../api/types';

export type LookupKind = 'category' | 'area';

export interface PendingLookup {
  kind: LookupKind;
  /** Selects the newly created record in the form that asked for it. */
  apply: (id: string) => void;
}

/**
 * Category / operating-area selection state for machine forms: the records behind the selected
 * ids (for the Review step) and inline "create new" requests. Options themselves are searched on
 * the server by the autocomplete pickers.
 */
export function useMachineLookups() {
  const [category, setCategory] = useState<CategoryDto | null>(null);
  const [area, setArea] = useState<AreaDto | null>(null);
  const [pending, setPending] = useState<PendingLookup | null>(null);

  return {
    category,
    area,
    setCategory,
    setArea,
    pending,
    requestNew: (kind: LookupKind, apply: (id: string) => void) => {
      setPending({ kind, apply });
    },
    closePending: () => {
      setPending(null);
    },
    categoryCreated: (c: CategoryDto) => {
      setCategory(c);
      pending?.apply(c.id);
    },
    areaCreated: (a: AreaDto) => {
      setArea(a);
      pending?.apply(a.id);
    },
  };
}

export type MachineLookups = ReturnType<typeof useMachineLookups>;
