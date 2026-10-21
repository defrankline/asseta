import { CssBaseline, type PaletteMode } from '@mui/material';
import { StyledEngineProvider, ThemeProvider } from '@mui/material/styles';
import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { ColorModeContext } from './ColorModeContext';
import { buildTheme } from './theme';

const KEY = 'asseta.colorMode';

function initialMode(): PaletteMode {
  try {
    const stored = window.localStorage.getItem(KEY);
    if (stored === 'light' || stored === 'dark') return stored;
  } catch {
    // ignore unavailable storage
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

/**
 * MUI + Tailwind coexistence: MUI (Emotion) styles are emitted into the CSS cascade layer
 * `mui` (enableCssLayer); Tailwind's preflight is NOT loaded (CssBaseline is the reset), and
 * index.css orders layers `theme, base, mui, components, utilities` so Tailwind utilities
 * override MUI component styles without `!important`.
 */
export function AppThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<PaletteMode>(initialMode);
  const toggle = useCallback(() => {
    setMode((m) => {
      const next = m === 'light' ? 'dark' : 'light';
      try {
        window.localStorage.setItem(KEY, next);
      } catch {
        // ignore
      }
      return next;
    });
  }, []);
  const theme = useMemo(() => buildTheme(mode), [mode]);
  const value = useMemo(() => ({ mode, toggle }), [mode, toggle]);

  return (
    <StyledEngineProvider enableCssLayer>
      <ColorModeContext.Provider value={value}>
        <ThemeProvider theme={theme}>
          <CssBaseline />
          {children}
        </ThemeProvider>
      </ColorModeContext.Provider>
    </StyledEngineProvider>
  );
}
