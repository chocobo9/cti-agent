export interface IconProps {
  name: string;
  size?: number;
  color?: string;
  strokeWidth?: number;
}

export function Icon({ name, size = 16, color = 'currentColor', strokeWidth = 1.6 }: IconProps) {
  const p: React.SVGProps<SVGSVGElement> = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: color,
    strokeWidth,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
  };

  switch (name) {
    case 'globe':
      return <svg {...p}><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 010 18M12 3a14 14 0 000 18" /></svg>;
    case 'hash':
      return <svg {...p}><path d="M4 9h16M4 15h16M10 3L8 21M16 3l-2 18" /></svg>;
    case 'shield':
      return <svg {...p}><path d="M12 3l8 3v6c0 5-3.5 8.5-8 9-4.5-.5-8-4-8-9V6l8-3z" /></svg>;
    case 'target':
      return <svg {...p}><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1" /></svg>;
    case 'send':
      return <svg {...p}><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" /></svg>;
    case 'attach':
      return <svg {...p}><path d="M21 11.5l-9 9a5 5 0 01-7-7l9-9a3.5 3.5 0 015 5l-9 9a2 2 0 01-3-3l8-8" /></svg>;
    case 'plus':
      return <svg {...p}><path d="M12 5v14M5 12h14" /></svg>;
    case 'check':
      return <svg {...p}><path d="M4 12l5 5L20 6" /></svg>;
    case 'x':
      return <svg {...p}><path d="M5 5l14 14M19 5L5 19" /></svg>;
    case 'spark':
      return <svg {...p}><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l3 3M15 15l3 3M6 18l3-3M15 9l3-3" /></svg>;
    case 'chevron':
      return <svg {...p}><path d="M9 18l6-6-6-6" /></svg>;
    case 'down':
      return <svg {...p}><path d="M6 9l6 6 6-6" /></svg>;
    case 'ext':
      return <svg {...p}><path d="M14 4h6v6M20 4l-8 8M14 12v6H4V8h6" /></svg>;
    case 'copy':
      return <svg {...p}><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V5a2 2 0 012-2h10" /></svg>;
    case 'graph':
      return <svg {...p}><circle cx="6" cy="6" r="2.5" /><circle cx="18" cy="7" r="2.5" /><circle cx="17" cy="18" r="2.5" /><circle cx="5" cy="17" r="2.5" /><circle cx="12" cy="12" r="2.5" /><path d="M8 7l2 4M16 8l-3 3M15 17l-2-3M7 16l3-3" /></svg>;
    case 'doc':
      return <svg {...p}><path d="M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9l-6-6z" /><path d="M14 3v6h6M8 13h8M8 17h5" /></svg>;
    case 'time':
      return <svg {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>;
    case 'cpu':
      return <svg {...p}><rect x="5" y="5" width="14" height="14" rx="2" /><rect x="9" y="9" width="6" height="6" /><path d="M9 3v2M15 3v2M9 19v2M15 19v2M3 9h2M3 15h2M19 9h2M19 15h2" /></svg>;
    case 'flame':
      return <svg {...p}><path d="M12 3c2 4-1 5-1 8a4 4 0 008 0c0-1-1-2-2-3 1 3-1 4-2 4 0-2-1-3-3-9z" /></svg>;
    case 'menu':
      return <svg {...p}><path d="M4 6h16M4 12h16M4 18h16" /></svg>;
    case 'search':
      return <svg {...p}><circle cx="11" cy="11" r="7" /><path d="M21 21l-5-5" /></svg>;
    case 'play':
      return <svg {...p}><path d="M6 4l14 8-14 8V4z" /></svg>;
    case 'side':
      return <svg {...p}><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M9 4v16" /></svg>;
    case 'flag':
      return <svg {...p}><path d="M5 21V4h12l-2 4 2 4H5" /></svg>;
    case 'pin':
      return <svg {...p}><path d="M12 2v6l4 3v3H8v-3l4-3V2zM12 14v8" /></svg>;
    case 'spinner':
      return <svg {...p}><path d="M12 3a9 9 0 019 9" opacity="0.3" /><path d="M12 3a9 9 0 00-9 9" /></svg>;
    case 'bolt':
      return <svg {...p}><path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z" /></svg>;
    case 'eye':
      return <svg {...p}><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z" /><circle cx="12" cy="12" r="3" /></svg>;
    case 'lock':
      return <svg {...p}><rect x="4" y="11" width="16" height="10" rx="2" /><path d="M8 11V7a4 4 0 018 0v4" /></svg>;
    case 'arrowR':
      return <svg {...p}><path d="M5 12h14M13 6l6 6-6 6" /></svg>;
    case 'sort':
      return <svg {...p}><path d="M7 4v16M7 4l-3 3M7 4l3 3M17 20V4M17 20l-3-3M17 20l3-3" /></svg>;
    case 'history':
      return <svg {...p}><path d="M3 12a9 9 0 109-9 9 9 0 00-6.4 2.6L3 8M3 3v5h5M12 7v5l3 2" /></svg>;
    case 'fingerprint':
      return <svg {...p}><path d="M12 11v3a6 6 0 01-1 3M9 11a3 3 0 016 0v2a8 8 0 01-1 4M6 11a6 6 0 0110-4M18 13v1a10 10 0 01-.5 3M4 14v-3a8 8 0 0114-5" /></svg>;
    default:
      return null;
  }
}
