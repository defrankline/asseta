import { act, render, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { lastMap } from '../../test/maplibreMock';
import { closeRing, lineFromVertices, polygonFromVertices, verticesFromRing } from './drawing';
import { DrawPolygonControl } from './DrawPolygonControl';
import type { LonLat } from './geo';
import { MapView } from './MapView';

vi.mock('maplibre-gl', () => import('../../test/maplibreMock'));

describe('drawing helpers', () => {
  it('closes a ring by repeating the first vertex once', () => {
    const v: LonLat[] = [
      [39, -6],
      [39.1, -6],
      [39.1, -6.1],
    ];
    expect(closeRing(v)).toEqual([...v, [39, -6]]);
    expect(closeRing(closeRing(v))).toEqual([...v, [39, -6]]);
    expect(polygonFromVertices(v)).toEqual({ type: 'Polygon', coordinates: [[...v, [39, -6]]] });
    expect(verticesFromRing(closeRing(v))).toEqual(v);
    expect(lineFromVertices(v)).toEqual({ type: 'LineString', coordinates: v });
  });
});

function Harness({ onChange }: { onChange: (v: LonLat[]) => void }) {
  const [vertices, setVertices] = useState<LonLat[]>([]);
  return (
    <MapView center={[39, -6]} ariaLabel="Draw map">
      <DrawPolygonControl
        mode="polygon"
        vertices={vertices}
        closed={false}
        onAddVertex={(p) => {
          setVertices((current) => {
            const next = [...current, p];
            onChange(next);
            return next;
          });
        }}
      />
    </MapView>
  );
}

describe('DrawPolygonControl', () => {
  it('adds a vertex per map click and previews them', async () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    await waitFor(() => {
      expect(lastMap().getSource('draw-preview')).toBeDefined();
    });
    act(() => {
      lastMap().click(39, -6);
      lastMap().click(39.1, -6);
    });
    await waitFor(() => {
      expect(onChange).toHaveBeenLastCalledWith([
        [39, -6],
        [39.1, -6],
      ]);
    });
  });
});
