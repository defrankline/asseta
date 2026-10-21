import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { Connectivity } from '../../api/types';
import { ConnectivityChip } from './ConnectivityChip';
import { CONNECTIVITY_ORDER, markerStyle } from './connectivity';
import { StatusDimensions } from './StatusDimensions';

describe('markerStyle (connectivity → marker)', () => {
  it('renders a solid live marker only for LIVE with is_live', () => {
    const s = markerStyle('LIVE', true);
    expect(s).toMatchObject({ live: true, hollow: false, fillOpacity: 1, label: 'Live' });
  });

  it('never presents stale/offline data as live, even if is_live were true', () => {
    for (const c of ['STALE', 'OFFLINE', 'NEVER_REPORTED', 'NO_TRACKER'] as Connectivity[]) {
      const s = markerStyle(c, true);
      expect(s.live).toBe(false);
      expect(s.hollow).toBe(true);
      expect(s.fillOpacity).toBe(0);
      expect(s.label).toMatch(/last known/);
    }
  });

  it('treats a LIVE link with an old position (is_live=false) as last known', () => {
    const s = markerStyle('LIVE', false);
    expect(s.live).toBe(false);
    expect(s.hollow).toBe(true);
    expect(s.label).toBe('Live · last known');
  });

  it('fades RECENT and labels it last known', () => {
    const s = markerStyle('RECENT', false);
    expect(s).toMatchObject({ live: false, hollow: false, label: 'Recent · last known' });
    expect(s.fillOpacity).toBeLessThan(1);
  });

  it('gives every state a distinct colour', () => {
    const colors = new Set(CONNECTIVITY_ORDER.map((c) => markerStyle(c, false).color));
    expect(colors.size).toBe(CONNECTIVITY_ORDER.length);
  });

  it('labels the chip "last known" when not live', () => {
    render(<ConnectivityChip connectivity="STALE" isLive={false} />);
    expect(screen.getByText('Stale · last known')).toBeInTheDocument();
  });
});

describe('StatusDimensions', () => {
  it('shows all four dimensions and renders UNKNOWN explicitly', () => {
    render(
      <StatusDimensions
        reportedWorkStatus="UNKNOWN"
        observedEngine="ON"
        observedMotion="UNKNOWN"
        locationCompliance="NON_COMPLIANT"
      />,
    );
    expect(screen.getByText('Reported work status')).toBeInTheDocument();
    expect(screen.getByText('Engine (sensor)')).toBeInTheDocument();
    expect(screen.getByText('Motion (sensor)')).toBeInTheDocument();
    expect(screen.getByText('Location compliance')).toBeInTheDocument();
    expect(screen.getAllByText('Unknown')).toHaveLength(2);
    expect(screen.getByText('On')).toBeInTheDocument();
    expect(screen.getByText('Non compliant')).toBeInTheDocument();
  });
});
