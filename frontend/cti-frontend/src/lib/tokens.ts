export const tokens = {
  bg: '#fafaf8',
  surface: '#ffffff',
  rail: '#fcfcfa',
  border: '#ececea',
  divider: '#f1f1ec',
  text: '#0d0f12',
  textMute: '#3a3d44',
  textSubtle: '#6b6f78',
  textGhost: '#9ea1a9',

  accent: '#3b5bdb',

  high_confidence: { fg: '#0a5d2b', bg: '#dcf5e6', dot: '#10b981' },
  medium_confidence: { fg: '#8a5a00', bg: '#fff3d6', dot: '#f59e0b' },
  low_confidence: { fg: '#9c3a1b', bg: '#fde2d6', dot: '#ea580c' },
  insufficient: { fg: '#3a3d44', bg: '#ececea', dot: '#9ca0b0' },

  src_graph: { fg: '#3b1a8f', bg: '#ede9fc' },
  src_rag: { fg: '#0a5078', bg: '#dfecf6' },
  src_llm: { fg: '#6b6f78', bg: '#ececea' },

  status_success: '#10b981',
  status_empty: '#9ca0b0',
  status_error: '#dc2626',
  status_no_match: '#f59e0b',
} as const;

export const radius = {
  xs: 4,
  sm: 6,
  md: 7,
  lg: 8,
  xl: 10,
  xxl: 12,
  xxxl: 14,
} as const;

export const fonts = {
  sans: "'Geist', -apple-system, BlinkMacSystemFont, sans-serif",
  mono: "'Geist Mono', 'SF Mono', 'Fira Code', monospace",
} as const;
