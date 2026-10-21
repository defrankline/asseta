import SearchIcon from '@mui/icons-material/Search';
import {
  Box,
  InputAdornment,
  List,
  ListItemButton,
  ListItemText,
  MenuItem,
  Paper,
  TextField,
  Typography,
} from '@mui/material';
import type { MachineMapDto } from '../../../api/types';
import { AgeText } from '../../../components/display/AgeText';
import { CONNECTIVITY_INFO, CONNECTIVITY_ORDER } from '../../../components/fleet/connectivity';
import { ConnectivityChip } from '../../../components/fleet/ConnectivityChip';
import { EmptyState } from '../../../components/feedback/EmptyState';
import { hasPosition, type ConnectivityFilter } from './fleetFilter';

interface FleetMachineListProps {
  all: readonly MachineMapDto[];
  machines: readonly MachineMapDto[];
  search: string;
  onSearch: (value: string) => void;
  connectivity: ConnectivityFilter;
  onConnectivity: (value: ConnectivityFilter) => void;
  selectedId: string | null;
  onSelect: (machineId: string) => void;
  now: number;
  timeZone: string;
}

/** Searchable, connectivity-filtered machine list beside the fleet map. */
export function FleetMachineList({
  all,
  machines,
  search,
  onSearch,
  connectivity,
  onConnectivity,
  selectedId,
  onSelect,
  now,
  timeZone,
}: FleetMachineListProps) {
  const count = (c: ConnectivityFilter) =>
    c === 'ALL' ? all.length : all.filter((m) => m.connectivity === c).length;
  return (
    <Paper variant="outlined" className="flex flex-col">
      <Box className="flex flex-col gap-2 p-3">
        <TextField
          size="small"
          value={search}
          onChange={(e) => {
            onSearch(e.target.value);
          }}
          placeholder="Search machines"
          slotProps={{
            htmlInput: { 'aria-label': 'Search machines' },
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            },
          }}
        />
        <TextField
          select
          size="small"
          label="Connectivity"
          value={connectivity}
          onChange={(e) => {
            onConnectivity(e.target.value as ConnectivityFilter);
          }}
        >
          <MenuItem value="ALL">All ({count('ALL')})</MenuItem>
          {CONNECTIVITY_ORDER.map((c) => (
            <MenuItem key={c} value={c}>
              {CONNECTIVITY_INFO[c].label} ({count(c)})
            </MenuItem>
          ))}
        </TextField>
      </Box>
      {machines.length === 0 ? (
        <EmptyState title="No machines match" />
      ) : (
        <List dense aria-label="Machines" className="max-h-[32rem] overflow-y-auto">
          {machines.map((m) => (
            <ListItemButton
              key={m.machine_id}
              selected={m.machine_id === selectedId}
              onClick={() => {
                onSelect(m.machine_id);
              }}
            >
              <ListItemText
                primary={`${m.asset_code} · ${m.name}`}
                secondary={
                  <Box component="span" className="mt-1 flex flex-wrap items-center gap-2">
                    <ConnectivityChip connectivity={m.connectivity} isLive={m.is_live} />
                    {hasPosition(m) ? (
                      <Typography component="span" variant="caption">
                        <AgeText at={m.position_time} now={now} timeZone={timeZone} />
                      </Typography>
                    ) : (
                      <Typography component="span" variant="caption">
                        No position
                      </Typography>
                    )}
                  </Box>
                }
                slotProps={{ secondary: { component: 'span' } }}
              />
            </ListItemButton>
          ))}
        </List>
      )}
    </Paper>
  );
}
