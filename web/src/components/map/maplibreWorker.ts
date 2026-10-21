/**
 * MapLibre 6 resolves its web worker relative to its own module URL, which breaks once Vite bundles it into a
 * chunk (the worker file is never emitted; maps render blank with "Worker failed to load"). Bundle the worker
 * with Vite and point MapLibre at it explicitly, before any map is created.
 */
import { setWorkerUrl } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';

setWorkerUrl(workerUrl);
