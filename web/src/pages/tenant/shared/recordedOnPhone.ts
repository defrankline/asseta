import type { KeyValueItem } from '../../../components/display/KeyValueGrid';
import { formatInstantIn } from '../../../utils/time';

/** When the phone created the record (offline capture may reach the server later). Nothing on web records. */
export function recordedOnPhone(
  clientCreatedAt: string | null | undefined,
  timeZone: string,
): KeyValueItem[] {
  return clientCreatedAt == null
    ? []
    : [{ label: 'Recorded on the phone at', value: formatInstantIn(clientCreatedAt, timeZone) }];
}
