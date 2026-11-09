import SearchIcon from '@mui/icons-material/Search';
import { InputAdornment, TextField } from '@mui/material';
import { useState, type SyntheticEvent } from 'react';
import { useNavigate } from 'react-router';
import { PERMISSIONS } from '../access/permissionCodes';
import { lookupPath } from '../navigation/routes';
import { useSession } from '../session/useSession';

/** Top-bar "Find a reference" (tenant.lookup.read): opens the result list of any number or reference. */
export function TransactionLookup() {
  const { hasPermission } = useSession();
  const navigate = useNavigate();
  const [text, setText] = useState('');
  if (!hasPermission(PERMISSIONS.tenantLookupRead)) return null;
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    const reference = text.trim();
    if (reference !== '') void navigate(lookupPath(reference));
  };
  return (
    <form role="search" onSubmit={submit} className="hidden md:block">
      <TextField
        size="small"
        placeholder="Find a reference"
        value={text}
        onChange={(e) => {
          setText(e.target.value);
        }}
        sx={{
          width: 240,
          '& .MuiOutlinedInput-root': { color: 'inherit', bgcolor: 'action.hover' },
        }}
        slotProps={{
          htmlInput: { 'aria-label': 'Find a reference', maxLength: 120 },
          input: {
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
          },
        }}
      />
    </form>
  );
}
