// Hafnarvaktins single source of design tokens.
// imported directly by every screen — no React Context,

const colors = {
  background: '#000000',
  surface: '#1c1c1e',
  surfaceElevated: '#2c2c2e',
  text: '#ffffff',
  textSecondary: '#8e8e93',
  textMuted: '#636366',
  separator: '#38383a',
  inputBorder: '#48484a',
  accent: '#0a84ff',
  accentMuted: '#1e3a5f',
  success: '#30d158',
  danger: '#ff453a',
  scrim: 'rgba(0,0,0,0.55)',
};

const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 20, xxl: 24 };
const radius = { sm: 10, md: 14, lg: 18, pill: 999 };
const fontSize = { caption: 11, small: 13, body: 15, label: 16, title: 22, large: 26, hero: 28 };
const weight = { regular: '400', medium: '600', bold: '700' };

export const theme = { ...colors, colors, space, radius, fontSize, weight };
