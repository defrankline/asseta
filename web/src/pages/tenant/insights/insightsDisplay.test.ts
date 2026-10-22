import { describe, expect, it } from 'vitest';
import { factText, insufficientText } from './insightsDisplay';

describe('insufficientText', () => {
  it('ends with exactly one full stop even when server reasons are sentences', () => {
    const text = insufficientText({
      weeks_observed: 0,
      min_weeks_required: 6,
      missing: ['0 complete weeks of cash history; at least 6 needed.'],
    });
    expect(text).toBe(
      'Not enough history yet: 0 of 6 weeks observed. Missing: 0 complete weeks of cash history; at least 6 needed.',
    );
  });

  it('omits the Missing part when nothing is listed', () => {
    expect(insufficientText({ weeks_observed: 2, min_weeks_required: 4, missing: [] })).toBe(
      'Not enough history yet: 2 of 4 weeks observed.',
    );
  });
});

describe('factText', () => {
  it('shows *_fraction minimums as percentages', () => {
    expect(factText(0.5, 'min_present_fraction')).toBe('50%');
    expect(factText(80, 'min_machine_weeks')).toBe('80');
  });
});
