/**
 * Test double for the `maplibre-gl` module (WebGL is unavailable in jsdom). Use at the module
 * boundary only: `vi.mock('maplibre-gl', () => import('<path>/test/maplibreMock'))`.
 * It records sources/layers and lets tests fire map / layer clicks.
 */

type Handler = (event: unknown) => void;

interface FakeSource {
  data: unknown;
  setData: (data: unknown) => Promise<void>;
}

interface LayerHandler {
  layer: string;
  handler: Handler;
}

export class Map {
  readonly sources: Record<string, FakeSource> = {};
  readonly layers: { id: string }[] = [];
  private readonly handlers: Record<string, Handler[]> = {};
  private readonly layerHandlers: Record<string, LayerHandler[]> = {};
  private readonly canvas = { style: { cursor: '' } };

  constructor() {
    instances.push(this);
    queueMicrotask(() => {
      this.emit('load', {});
    });
  }

  on(type: string, layerOrHandler: string | Handler, maybeHandler?: Handler): this {
    if (typeof layerOrHandler === 'string' && maybeHandler !== undefined) {
      (this.layerHandlers[type] ??= []).push({ layer: layerOrHandler, handler: maybeHandler });
    } else if (typeof layerOrHandler === 'function') {
      (this.handlers[type] ??= []).push(layerOrHandler);
    }
    return this;
  }

  off(type: string, layerOrHandler: string | Handler, maybeHandler?: Handler): this {
    if (typeof layerOrHandler === 'string') {
      this.layerHandlers[type] = (this.layerHandlers[type] ?? []).filter(
        (h) => h.handler !== maybeHandler,
      );
    } else {
      this.handlers[type] = (this.handlers[type] ?? []).filter((h) => h !== layerOrHandler);
    }
    return this;
  }

  emit(type: string, event: unknown): void {
    for (const h of [...(this.handlers[type] ?? [])]) h(event);
  }

  /** Simulate a click on the map background at [lon, lat]. */
  click(lon: number, lat: number): void {
    this.emit('click', { lngLat: { lng: lon, lat } });
  }

  /** Simulate a click on a rendered feature of `layer`. */
  clickLayer(layer: string, properties: Record<string, unknown>): void {
    for (const h of this.layerHandlers.click ?? []) {
      if (h.layer === layer) h.handler({ features: [{ properties }] });
    }
  }

  addControl(): this {
    return this;
  }
  addSource(id: string, spec: { data: unknown }): this {
    const source: FakeSource = {
      data: spec.data,
      setData: (data: unknown) => {
        source.data = data;
        return Promise.resolve();
      },
    };
    this.sources[id] = source;
    return this;
  }
  getSource(id: string): FakeSource | undefined {
    return this.sources[id];
  }
  removeSource(id: string): this {
    // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
    delete this.sources[id];
    return this;
  }
  addLayer(layer: { id: string }): this {
    this.layers.push(layer);
    return this;
  }
  getLayer(id: string): { id: string } | undefined {
    return this.layers.find((l) => l.id === id);
  }
  removeLayer(id: string): this {
    const i = this.layers.findIndex((l) => l.id === id);
    if (i >= 0) this.layers.splice(i, 1);
    return this;
  }
  getCanvas() {
    return this.canvas;
  }
  jumpTo(): this {
    return this;
  }
  fitBounds(): this {
    return this;
  }
  flyTo(): this {
    return this;
  }
  remove(): void {
    const i = instances.indexOf(this);
    if (i >= 0) instances.splice(i, 1);
  }
}

export class NavigationControl {
  readonly kind = 'navigation';
}

export class LngLatBounds {
  constructor(
    readonly sw: [number, number],
    readonly ne: [number, number],
  ) {}
  extend(): this {
    return this;
  }
}

/** Live fake maps (most recent last). */
export const instances: Map[] = [];

export function lastMap(): Map {
  const map = instances[instances.length - 1];
  if (map === undefined) throw new Error('No map has been created.');
  return map;
}

/** Worker configuration is a no-op in jsdom (no WebGL/workers). */
export function setWorkerUrl(url: string): void {
  workerUrls.push(url);
}
export const workerUrls: string[] = [];
