import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { captureLocationFeatures } from './captureLocation';
import { HoursComparison } from './HoursComparison';
import { NOT_COMPARED_TEXT, TrackerComparison } from './TrackerComparison';

describe('TrackerComparison', () => {
  it('shows distance, allowed distance and time offset when compared', () => {
    render(
      <TrackerComparison
        comparison={{
          compared: true,
          distance_m: 40.5,
          allowed_m: 162,
          tracker_time: '2026-10-21T05:59:50Z',
          time_offset_s: -3.5,
        }}
        timeZone="UTC"
      />,
    );
    expect(screen.getByText('40.5 m')).toBeInTheDocument();
    expect(screen.getByText('162 m')).toBeInTheDocument();
    expect(screen.getByText('-3.5 s')).toBeInTheDocument();
    expect(screen.getByText('Within allowed distance')).toBeInTheDocument();
  });

  it('states when no tracker position was within the comparison window', () => {
    render(
      <TrackerComparison
        comparison={{ compared: false, reason: 'no tracker position within comparison window' }}
        timeZone="UTC"
      />,
    );
    expect(screen.getByText(new RegExp(NOT_COMPARED_TEXT))).toBeInTheDocument();
  });

  it('distinguishes a missing phone fix', () => {
    render(
      <TrackerComparison
        comparison={{ compared: false, reason: 'no phone GPS fix' }}
        timeZone="UTC"
      />,
    );
    expect(screen.getByText(/the phone had no GPS fix/)).toBeInTheDocument();
  });
});

describe('HoursComparison', () => {
  it('keeps meter and billable hours apart and waits for both readings', () => {
    render(<HoursComparison meterHours={null} nonbillableHours="0.00" billableHours={null} />);
    expect(
      within(screen.getByRole('group', { name: 'Meter hours' })).getByText('Not yet available'),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole('group', { name: 'Billable hours' })).getByText('Not yet available'),
    ).toBeInTheDocument();
    expect(screen.getByText(/Both opening and closing readings are needed/)).toBeInTheDocument();
  });
});

describe('captureLocationFeatures', () => {
  const roles = (fc: ReturnType<typeof captureLocationFeatures>) =>
    fc.features.map((f) => (f.properties as { role: string }).role);

  it('adds the tracker point, its accuracy and a link when a tracker position exists', () => {
    const fc = captureLocationFeatures([39.28, -6.8], 12, 162, {
      latitude: -6.8037,
      longitude: 39.2812,
      accuracyM: 8,
    });
    expect(roles(fc)).toEqual([
      'phone-accuracy',
      'tracker-accuracy',
      'allowed',
      'link',
      'phone',
      'tracker',
    ]);
  });

  it('draws only the phone fix and ring without a tracker position', () => {
    expect(roles(captureLocationFeatures([39.28, -6.8], 12, 162, null))).toEqual([
      'phone-accuracy',
      'allowed',
      'phone',
    ]);
  });
});
