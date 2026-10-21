import { geofenceService } from '../../../api/services/geofenceService';
import { machineService } from '../../../api/services/machineService';
import { trackerService } from '../../../api/services/trackerService';
import type { AreaDto, CategoryDto, JobSiteDto, TrackerModelDto } from '../../../api/types';

/**
 * Server lookups for tenant reference data used by autocompletes. Each `search*` passes the typed
 * text to the API (`q`); the result is never filtered in the browser.
 *
 * These reference lists have no get-by-id endpoint, so `resolve*` (used only to show the label of
 * an id already stored in an edit form) reads the list once and picks the id.
 */

export const optionId = (o: { id: string }): string => o.id;

export const categoryLabel = (c: CategoryDto): string => c.name;
export const searchCategories = (q: string, signal: AbortSignal) =>
  machineService.listCategories(signal, q);
export const resolveCategory = async (id: string, signal: AbortSignal) =>
  (await machineService.listCategories(signal, undefined, true)).find((c) => c.id === id) ?? null;

export const areaLabel = (a: AreaDto): string => `${a.code} · ${a.name}`;
export const searchAreas = (q: string, signal: AbortSignal) => machineService.listAreas(signal, q);
export const resolveArea = async (id: string, signal: AbortSignal) =>
  (await machineService.listAreas(signal, undefined, true)).find((a) => a.id === id) ?? null;

export const jobSiteLabel = (s: JobSiteDto): string => `${s.code} · ${s.name}`;
export const searchJobSites = (q: string, signal: AbortSignal) =>
  geofenceService.listJobSites(signal, q);
export const resolveJobSite = async (id: string, signal: AbortSignal) =>
  (await geofenceService.listJobSites(signal, undefined, true)).find((s) => s.id === id) ?? null;

export const trackerModelLabel = (m: TrackerModelDto): string => `${m.manufacturer} ${m.model}`;
export const searchTrackerModels = (q: string, signal: AbortSignal) =>
  trackerService.listModels(signal, q);
