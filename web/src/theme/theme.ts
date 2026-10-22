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
      // Status chips and contained buttons pick text that meets WCAG AA (4.5:1) on their fill:
      // e.g. warning/info in light mode and error in dark mode get dark text.
      contrastThreshold: 4.5,
      // Lighter red in dark mode so outlined chips and error text reach 4.5:1 on dark paper.
      ...(dark ? { error: { main: '#E57373' } } : {}),
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
      // Phones (360px): dialogs keep a 16px gutter instead of 32px so forms are not squeezed.
      MuiDialog: {
        styleOverrides: {
          paper: ({ theme }) => ({
            [theme.breakpoints.down('sm')]: { margin: 16, maxHeight: 'calc(100% - 32px)' },
          }),
          paperFullWidth: ({ theme }) => ({
            [theme.breakpoints.down('sm')]: { width: 'calc(100% - 32px)' },
          }),
        },
      },
      // Keyboard focus is visible as an outline, not only a faint background tint.
      MuiListItemButton: {
        styleOverrides: {
          root: ({ theme }) => ({
            '&.Mui-focusVisible': {
              outline: `2px solid ${theme.palette.primary.main}`,
              outlineOffset: -2,
            },
          }),
        },
      },
    },
  });
}
