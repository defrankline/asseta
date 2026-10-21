import { createContext, useContext } from 'react';
import type { PaletteMode } from '@mui/material';

export interface ColorModeValue {
  mode: PaletteMode;
  toggle: () => void;
}

export const ColorModeContext = createContext<ColorModeValue>({
  mode: 'light',
  toggle: () => undefined,
});

export function useColorMode(): ColorModeValue {
  return useContext(ColorModeContext);
}
