import './Avatar.css';

const TONE_COLORS = {
  ink: '#1A1A1A',
  muted: '#8A8576',
  inverted: '#FFFEF1',
};

function getInitial(name) {
  if (!name) return '?';
  const trimmed = name.trim();
  if (!trimmed) return '?';
  return trimmed[0].toUpperCase();
}

export default function Avatar({ svg, name, size = 32, tone = 'ink', spinning = false, className = '' }) {
  const color = TONE_COLORS[tone] || TONE_COLORS.ink;
  const style = {
    width: `${size}px`,
    height: `${size}px`,
    color,
    ...(spinning ? { animation: 'avatar-spin 1.1s linear infinite' } : {}),
  };

  const raw = svg && svg.trim();
  if (raw) {
    // Uploaded images are stored as `data:image/...;base64,...` URIs and
    // are rendered verbatim. Generated avatars are SVG markup that we
    // themify via currentColor and URL-encode into a data URI.
    const src = raw.startsWith('data:')
      ? raw
      : `data:image/svg+xml;utf8,${encodeURIComponent(raw.replace(/currentColor/g, color))}`;
    return (
      <img
        src={src}
        alt={name ? `${name} avatar` : 'avatar'}
        className={`avatar ${className}`}
        style={style}
        draggable={false}
      />
    );
  }

  return (
    <span
      className={`avatar avatar-fallback ${className}`}
      style={style}
      role="img"
      aria-label={name ? `${name} avatar` : 'avatar'}
    >
      <span className="avatar-fallback-inner">{getInitial(name)}</span>
    </span>
  );
}
