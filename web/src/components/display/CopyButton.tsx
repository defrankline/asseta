import ContentCopy from '@mui/icons-material/ContentCopy';
import { Button } from '@mui/material';
import { useState } from 'react';

interface CopyButtonProps {
  value: string;
  label?: string;
}

/** Copies a value to the clipboard and confirms inline. */
export function CopyButton({ value, label = 'Copy' }: CopyButtonProps) {
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setState('copied');
    } catch {
      setState('failed');
    }
  };
  return (
    <Button
      size="small"
      variant="outlined"
      startIcon={<ContentCopy fontSize="small" />}
      onClick={() => {
        void copy();
      }}
    >
      {state === 'copied' ? 'Copied' : state === 'failed' ? 'Copy failed — select manually' : label}
    </Button>
  );
}
