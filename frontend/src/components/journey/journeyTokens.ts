export const T = {
  bgDeep:   '#0a0e1a',
  bgCard:   '#111827',
  bgSurface:'#1a2236',
  cyan:     '#00f0ff',
  magenta:  '#ff2d78',
  green:    '#39ff14',
  yellow:   '#ffe156',
  orange:   '#ff8c42',
  purple:   '#a855f7',
  text:     '#f0f4ff',
  textSec:  '#8892a8',
  textDim:  '#4a5568',
  border:   'rgba(0,240,255,0.12)',
} as const;

export const groupColor = {
  PREMIUM:  '#a855f7',
  MATCHING: '#00f0ff',
  BELOW:    '#ff8c42',
} as const;

export const groupBg = {
  PREMIUM:  'rgba(168,85,247,0.08)',
  MATCHING: 'rgba(0,240,255,0.08)',
  BELOW:    'rgba(255,140,66,0.08)',
} as const;

export const groupBorder = {
  PREMIUM:  'rgba(168,85,247,0.25)',
  MATCHING: 'rgba(0,240,255,0.25)',
  BELOW:    'rgba(255,140,66,0.25)',
} as const;

export const groupLabel = {
  PREMIUM:  '💎 PREMIUM — 목표가 이하',
  MATCHING: '✅ MATCHING — 목표가 부합',
  BELOW:    '📦 BELOW — 목표가 초과',
} as const;
