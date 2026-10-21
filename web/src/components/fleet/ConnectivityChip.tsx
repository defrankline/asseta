import { Chip, Tooltip } from '@mui/material';
import type { Connectivity } from '../../api/types';
import { CONNECTIVITY_INFO, markerStyle } from './connectivity';

interface ConnectivityChipProps {
  connectivity: Connectivity;
  /** Server `is_live`; without it the chip says "last known". */
  isLive: boolean;
}

/** Connectivity as text + tone; non-live states are explicitly labelled "last known". */
export function ConnectivityChip({ connectivity, isLive }: ConnectivityChipProps) {
  const info = CONNECTIVITY_INFO[connectivity];
  const style = markerStyle(connectivity, isLive);
  return (
    <Tooltip title={info.description}>
      <Chip
        size="small"
        label={style.label}
        color={info.tone}
        variant={style.live ? 'filled' : 'outlined'}
      />
    </Tooltip>
  );
}
