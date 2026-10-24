import { engineHoursService } from '../../../api/services/engineHoursService';
import { meterService } from '../../../api/services/meterService';
import type {
  EngineHourReasonDto,
  EngineHourReasonKind,
  MeterCaptureDto,
} from '../../../api/types';
import { LOOKUP_PAGE_SIZE } from '../../../components/data/AsyncAutocomplete';
import { humanize } from '../../../utils/text';

/** Server-backed lookups for engine-hour forms (the typed text is passed to the API as `q`). */

export const reasonLabel = (r: EngineHourReasonDto): string => `${r.code} · ${r.name}`;

/** Active entries of one tenant list (activity categories or variance reasons). */
export const searchReasons =
  (kind: EngineHourReasonKind) =>
  async (q: string, signal: AbortSignal): Promise<EngineHourReasonDto[]> =>
    (
      await engineHoursService.listReasons(
        { page: 1, page_size: LOOKUP_PAGE_SIZE, q, filters: { kind } },
        signal,
      )
    ).items;

export const resolveReason = async (
  id: string,
  signal: AbortSignal,
): Promise<EngineHourReasonDto | null> => engineHoursService.getReason(id, signal);

/** A machine's live (accepted) readings, latest first; `q` is passed to the server search. */
export const searchMachineReadings =
  (machineId: string) =>
  async (q: string, signal: AbortSignal): Promise<MeterCaptureDto[]> =>
    (
      await meterService.listAllCaptures(
        {
          page: 1,
          page_size: LOOKUP_PAGE_SIZE,
          q,
          filters: { machine_id: machineId, state: 'ACCEPTED' },
        },
        signal,
      )
    ).items;

export const readingOptionLabel = (c: MeterCaptureDto, format: (iso: string) => string): string =>
  `${c.reading} h · ${humanize(c.kind)} · ${format(c.captured_at)}`;
