import { createTheme, type PaletteMode, type Theme } from '@mui/material/styles';

export const BRAND = {
  slate: '#0F2A3D',
  amber: '#F5A300',
  offWhite: '#F7F8FA',
} as const;

export function buildTheme(mode: PaletteMode): Theme {
  const dark = mode === 'dark';
  return createTheme({
    palette: {
      mode,
      primary: dark
        ? { main: '#7FA7C4', contrastText: BRAND.slate }
        : { main: BRAND.slate, contrastText: '#FFFFFF' },
      secondary: { main: BRAND.amber, contrastText: BRAND.slate },
      background: dark
        ? { default: '#0A1C29', paper: '#11293B' }
        : { default: BRAND.offWhite, paper: '#FFFFFF' },
    },
    shape: { borderRadius: 8 },
    typography: {
      fontFamily: "Inter, 'Segoe UI', Helvetica, Arial, sans-serif",
      button: { textTransform: 'none', fontWeight: 600 },
    },
    components: {
      MuiAppBar: {
        styleOverrides: {
          root: { backgroundColor: BRAND.slate, color: '#FFFFFF' },
        },
      },
    },
  });
}
