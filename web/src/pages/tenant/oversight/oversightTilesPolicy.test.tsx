import { describe, expect, it } from 'vitest';
import { CAPABILITY } from '../../../access/capabilities';
import type { AccountabilitySummaryDto } from '../../../api/custodyTypes';
import { buildTiles } from '../accountability/accountabilityModel';

describe('dashboard tiles', () => {
  const SUMMARY = {
    as_of: '2026-10-26T12:00:00Z',
    policy_version: 'v1',
    hidden_tiles: [],
    unavailable_tiles: [],
    disabled_capabilities: [],
    idle_machines: {
      count: 1,
      after_days: 14,
      longest_idle_days: 25,
      items: [
        {
          machine_id: 'm3',
          machine_code: 'GR-03',
          machine_name: 'Grader',
          idle_since: '',
          idle_days: 25,
        },
      ],
    },
  } as unknown as AccountabilitySummaryDto;

  it('builds the idle machines tile linking to its list', () => {
    const tiles = buildTiles(SUMMARY, () => true);
    const idle = tiles.find((t) => t.key === 'idle_machines');
    expect(idle?.to).toBe('/tenant/idle-machines');
    expect(idle?.description).toBe('Longest idle 25 days');
    expect(idle?.rows?.find((r) => r.key === 'idle')?.value).toBe(1);
  });

  it('lists the tile items by name, linking to the record', () => {
    const tiles = buildTiles(SUMMARY, () => true);
    const machine = tiles
      .find((t) => t.key === 'idle_machines')
      ?.rows?.find((r) => r.key === 'machine-m3');
    expect(machine?.label).toBe('GR-03 Grader');
    expect(machine?.valueText).toBe('25 days');
    expect(machine?.to).toBe('/tenant/machines/m3');
    const noAccess = buildTiles(SUMMARY, () => false);
    expect(
      noAccess.find((t) => t.key === 'idle_machines')?.rows?.find((r) => r.key === 'machine-m3')
        ?.to,
    ).toBeUndefined();
  });

  it('drops the tile while its capability is off', () => {
    const off = { ...SUMMARY, disabled_capabilities: [CAPABILITY.idleMachines] };
    const keys = buildTiles(off, () => true).map((t) => t.key);
    expect(keys).not.toContain('idle_machines');
  });
});
