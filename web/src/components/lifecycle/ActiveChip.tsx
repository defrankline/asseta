import { StatusChip, type StatusTone } from '../display/StatusChip';

const TONES: Readonly<Record<string, StatusTone>> = { ACTIVE: 'success', INACTIVE: 'default' };

interface ActiveChipProps {
  active: boolean;
  activeLabel?: string;
  /** Domain wording, e.g. `Closed`, `Retired`, `Withdrawn` (default `Inactive`). */
  inactiveLabel?: string;
}

/** Active / inactive state as text plus tone (never colour alone). */
export function ActiveChip({
  active,
  activeLabel = 'Active',
  inactiveLabel = 'Inactive',
}: ActiveChipProps) {
  return (
    <StatusChip
      status={active ? 'ACTIVE' : 'INACTIVE'}
      tones={TONES}
      label={active ? activeLabel : inactiveLabel}
    />
  );
}
