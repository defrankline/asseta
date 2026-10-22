import { describe, expect, it } from 'vitest';
import { ordinalPercentile } from './modelDisplay';

describe('ordinalPercentile', () => {
  it.each([
    [0.25, '25th'],
    [0.98, '98th'],
    [0.01, '1st'],
    [0.02, '2nd'],
    [0.03, '3rd'],
    [0.11, '11th'],
    [0.125, '12.5th'],
    [0.833333, '83.3rd'],
    ['0.208333', '20.8th'],
  ] as const)('%s -> %s', (fraction, text) => {
    expect(ordinalPercentile(fraction)).toBe(text);
  });

  it('shows a dash when there is no value', () => {
    expect(ordinalPercentile(null)).toBe('—');
    expect(ordinalPercentile('x')).toBe('—');
  });
});
