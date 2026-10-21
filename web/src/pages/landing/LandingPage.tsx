import DarkMode from '@mui/icons-material/DarkMode';
import LightMode from '@mui/icons-material/LightMode';
import { Box, Button, Container, IconButton, Paper, Stack, Typography } from '@mui/material';
import { useAuth } from '../../auth/useAuth';
import { appConfig } from '../../config/env';
import { Logo } from '../../layout/Logo';
import { useColorMode } from '../../theme/ColorModeContext';
import { FEATURES, HERO, MANAGED, PRICING, STEPS, type Feature } from './landingContent';

const AMBER = '#F5A300';
const SLATE = '#0F2A3D';

function DemoButton({ size = 'large' }: { size?: 'medium' | 'large' }) {
  if (appConfig.contactEmail === null) return null;
  const subject = encodeURIComponent('Asseta demo request');
  return (
    <Button
      variant="outlined"
      size={size}
      color="inherit"
      href={`mailto:${appConfig.contactEmail}?subject=${subject}`}
    >
      Request a demo
    </Button>
  );
}

function FeatureCard({ title, body }: Feature) {
  return (
    <Paper variant="outlined" className="h-full p-5" sx={{ borderTop: `3px solid ${AMBER}` }}>
      <Typography variant="h6" component="h3" gutterBottom>
        {title}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {body}
      </Typography>
    </Paper>
  );
}

/** Public business face of Asseta, shown to signed-out visitors at the site root. */
export function LandingPage() {
  const { login } = useAuth();
  const { mode, toggle } = useColorMode();
  return (
    <Box className="min-h-screen" sx={{ bgcolor: 'background.default' }}>
      <Box component="header" sx={{ bgcolor: SLATE, color: '#F7F8FA' }}>
        <Container className="flex items-center justify-between py-3">
          <Logo height={36} />
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
            <IconButton color="inherit" aria-label="Toggle colour mode" onClick={toggle}>
              {mode === 'dark' ? <LightMode /> : <DarkMode />}
            </IconButton>
            <Button
              variant="contained"
              onClick={login}
              sx={{ bgcolor: AMBER, color: SLATE, '&:hover': { bgcolor: '#FFB627' } }}
            >
              Sign in
            </Button>
          </Stack>
        </Container>
      </Box>

      <Box
        component="section"
        aria-labelledby="hero-title"
        sx={{
          color: '#F7F8FA',
          background: `radial-gradient(circle at 15% 20%, rgba(245,163,0,0.18), transparent 45%), linear-gradient(160deg, ${SLATE} 0%, #081A27 100%)`,
        }}
      >
        <Container className="py-16 md:py-24">
          <Typography variant="overline" sx={{ color: AMBER, letterSpacing: 2 }}>
            {HERO.eyebrow}
          </Typography>
          <Typography
            id="hero-title"
            variant="h3"
            component="h1"
            className="max-w-3xl"
            sx={{ fontWeight: 800, fontSize: { xs: '2rem', md: '3rem' } }}
          >
            {HERO.title}
          </Typography>
          <Typography variant="h6" component="p" className="mt-4 max-w-2xl" sx={{ opacity: 0.85 }}>
            {HERO.body}
          </Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} className="mt-8">
            <Button
              variant="contained"
              size="large"
              onClick={login}
              sx={{ bgcolor: AMBER, color: SLATE, '&:hover': { bgcolor: '#FFB627' } }}
            >
              Sign in to your console
            </Button>
            <DemoButton />
          </Stack>
        </Container>
      </Box>

      <Container component="section" aria-labelledby="features-title" className="py-16">
        <Typography id="features-title" variant="h4" component="h2" gutterBottom>
          Everything a hire business needs to trust its numbers
        </Typography>
        <Box className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <FeatureCard key={f.title} {...f} />
          ))}
        </Box>
      </Container>

      <Box component="section" aria-labelledby="steps-title" sx={{ bgcolor: 'action.hover' }}>
        <Container className="py-16">
          <Typography id="steps-title" variant="h4" component="h2" gutterBottom>
            How it works
          </Typography>
          <Box
            component="ol"
            className="mt-6 grid list-none gap-4 p-0 sm:grid-cols-2 lg:grid-cols-4"
          >
            {STEPS.map((s, i) => (
              <Box component="li" key={s.title}>
                <Typography variant="h3" component="span" sx={{ color: AMBER, fontWeight: 800 }}>
                  {i + 1}
                </Typography>
                <Typography variant="h6" component="h3">
                  {s.title}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {s.body}
                </Typography>
              </Box>
            ))}
          </Box>
        </Container>
      </Box>

      <Container component="section" className="grid gap-4 py-16 md:grid-cols-2">
        {[PRICING, MANAGED].map((b) => (
          <Paper key={b.title} variant="outlined" className="p-6">
            <Typography variant="h5" component="h2" gutterBottom>
              {b.title}
            </Typography>
            <Typography color="text.secondary">{b.body}</Typography>
          </Paper>
        ))}
      </Container>

      <Box component="footer" sx={{ bgcolor: SLATE, color: '#F7F8FA' }}>
        <Container className="flex flex-col items-start justify-between gap-4 py-8 sm:flex-row sm:items-center">
          <Logo height={28} />
          <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}>
            <DemoButton size="medium" />
            <Typography variant="body2" sx={{ opacity: 0.7 }}>
              © {new Date().getFullYear()} Asseta
            </Typography>
          </Stack>
        </Container>
      </Box>
    </Box>
  );
}
