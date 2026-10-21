/** Landing-page copy. Every claim describes a capability Asseta actually ships; no invented figures. */

export interface Feature {
  title: string;
  body: string;
}

export const HERO = {
  eyebrow: 'Heavy-equipment hire, under control',
  title: 'Know where every machine is, what it worked, and what it earned.',
  body:
    'Asseta connects GPS trackers, field supervisors and your hire records, so every billed hour is ' +
    'backed by a meter photo, a location and a time stamp — even where there is no network.',
};

export const FEATURES: Feature[] = [
  {
    title: 'Live fleet map',
    body:
      'Plug-and-play GPS trackers through a Traccar gateway. See each machine’s position, engine state, ' +
      'site and connectivity, and replay its history.',
  },
  {
    title: 'Meter proof on every reading',
    body:
      'Opening and closing readings by photo with on-device reading, or manual entry — your choice per ' +
      'machine. Each capture attempts GPS and is compared with the tracker.',
  },
  {
    title: 'Works offline in the field',
    body:
      'Native Android and iOS supervisor apps keep encrypted data on the phone, queue work offline and ' +
      'sync exactly once when the network returns.',
  },
  {
    title: 'Jobs, contracts and approvals',
    body:
      'Customers, rental contracts and jobs with approval steps. Disputed readings and meter resets need ' +
      'a second person to approve.',
  },
  {
    title: 'Geofences and alerts',
    body:
      'Draw sites and restricted areas. Get alerted when a machine leaves its site, moves without ' +
      'authorisation, or its tracker goes quiet, loses power or is tampered with.',
  },
  {
    title: 'Built for accountability',
    body:
      'Every sensitive change is audited with who, when and why. Your data is isolated from every other ' +
      'company on the platform.',
  },
];

export const STEPS: Feature[] = [
  {
    title: 'Fit a tracker',
    body: 'Install a supported GPS tracker; it reports through the Asseta gateway.',
  },
  {
    title: 'Register machines',
    body: 'Add machines, sites and supervisors, and set your capture rules.',
  },
  { title: 'Run jobs', body: 'Supervisors record readings and work on site, online or offline.' },
  {
    title: 'Bill with evidence',
    body: 'Hours are backed by photos, GPS and tracker data you can show a customer.',
  },
];

export const PRICING = {
  title: 'Pay only for the machines you track',
  body:
    'Subscriptions are per tracked machine, billed monthly or yearly, with rates agreed for your fleet. ' +
    'Talk to us for a quote.',
};

export const MANAGED = {
  title: 'Short on staff? We can run it for you.',
  body:
    'With your written consent, named Asseta staff can operate your account under a managed-service ' +
    'mandate. You see everything they do and can withdraw access at any time.',
};
