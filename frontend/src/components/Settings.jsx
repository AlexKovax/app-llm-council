import { useState, useEffect } from 'react';
import './Settings.css';

export default function Settings({ onLoadPrompts }) {
  const [prompts, setPrompts] = useState(null);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState({});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await onLoadPrompts();
        if (!cancelled) setPrompts(data.prompts || []);
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load prompts');
      }
    })();
    return () => { cancelled = true; };
  }, [onLoadPrompts]);

  const toggle = (id) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="settings-view">
      <div className="settings-header">
        <h2>Settings</h2>
        <p className="settings-subtitle">
          Master prompts sent by the council during the 3-stage deliberation.
          Read-only for now — editing will come later.
        </p>
      </div>

      {error && <div className="settings-error">{error}</div>}

      {!prompts && !error && (
        <div className="settings-loading">Loading prompts…</div>
      )}

      {prompts && prompts.length === 0 && (
        <div className="settings-empty">No prompts found.</div>
      )}

      {prompts && prompts.map((p) => (
        <div key={p.id} className="prompt-card">
          <div className="prompt-card-header" onClick={() => toggle(p.id)}>
            <div className="prompt-card-label">{p.label}</div>
            <button type="button" className="prompt-toggle">
              {expanded[p.id] ? 'Hide' : 'Show'}
            </button>
          </div>
          <div className="prompt-card-description">{p.description}</div>
          {expanded[p.id] && (
            <pre className="prompt-template">{p.template}</pre>
          )}
        </div>
      ))}
    </div>
  );
}
