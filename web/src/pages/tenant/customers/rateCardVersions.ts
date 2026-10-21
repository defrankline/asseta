import type { RateCardDto } from '../../../api/types';

export type VersionState = 'IN_FORCE' | 'SCHEDULED' | 'SUPERSEDED';

export interface CategoryVersions {
  categoryId: string;
  /** Newest effective first. */
  versions: { card: RateCardDto; state: VersionState }[];
}

/**
 * Group rate-card versions by machine category (newest first) and label each: the newest version
 * already effective is in force, later ones are scheduled, older ones superseded.
 */
export function groupRateCards(cards: readonly RateCardDto[], nowMs: number): CategoryVersions[] {
  const byCategory = new Map<string, RateCardDto[]>();
  for (const c of cards) {
    const list = byCategory.get(c.machine_category_id) ?? [];
    list.push(c);
    byCategory.set(c.machine_category_id, list);
  }
  return [...byCategory.entries()].map(([categoryId, list]) => {
    const sorted = [...list].sort((a, b) => b.effective_from.localeCompare(a.effective_from));
    let inForceSeen = false;
    const versions = sorted.map((card) => {
      if (Date.parse(card.effective_from) > nowMs) return { card, state: 'SCHEDULED' as const };
      if (!inForceSeen) {
        inForceSeen = true;
        return { card, state: 'IN_FORCE' as const };
      }
      return { card, state: 'SUPERSEDED' as const };
    });
    return { categoryId, versions };
  });
}
