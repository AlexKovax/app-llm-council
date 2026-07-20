import { useState, useEffect, useRef } from 'react';
import Avatar from './Avatar';
import './Personalities.css';

const EMPTY_FORM = { name: '', model: '', system_prompt: '', description: '' };
const AVATAR_TIMEOUT_MS = 90_000;

export default function Personalities({ personalities, models, onRefreshModels, onCreate, onUpdate, onDelete, onRegenerateAvatar }) {
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [confirmingDelete, setConfirmingDelete] = useState(null);
  const [expandedPrompt, setExpandedPrompt] = useState(null);
  const [error, setError] = useState('');
  const [refreshingModels, setRefreshingModels] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState('');
  const [regeneratingAvatar, setRegeneratingAvatar] = useState(null);
  const [avatarError, setAvatarError] = useState('');
  const [avatarElapsed, setAvatarElapsed] = useState(0);
  const avatarTimerRef = useRef(null);

  const modelsByProvider = (() => {
    const groups = {};
    for (const m of models || []) {
      if (!groups[m.provider]) groups[m.provider] = [];
      groups[m.provider].push(m);
    }
    return groups;
  })();

  const handleRefreshModels = async () => {
    setRefreshingModels(true);
    setRefreshMessage('');
    try {
      const data = await onRefreshModels();
      setRefreshMessage(`Refreshed: ${data.count} models cached.`);
    } catch (err) {
      setRefreshMessage(err.message || 'Failed to refresh models');
    } finally {
      setRefreshingModels(false);
      setTimeout(() => setRefreshMessage(''), 4000);
    }
  };

  const startCreate = () => {
    setEditingId('new');
    setForm(EMPTY_FORM);
    setError('');
  };

  const startEdit = (p) => {
    setEditingId(p.id);
    setForm({
      name: p.name || '',
      model: p.model || '',
      system_prompt: p.system_prompt || '',
      description: p.description || '',
    });
    setError('');
  };

  const cancel = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!form.name.trim() || !form.model.trim() || !form.system_prompt.trim()) {
      setError('Name, model and system prompt are required.');
      return;
    }

    try {
      if (editingId === 'new') {
        await onCreate({
          name: form.name.trim(),
          model: form.model.trim(),
          system_prompt: form.system_prompt.trim(),
          description: form.description.trim(),
        });
      } else {
        await onUpdate(editingId, {
          name: form.name.trim(),
          model: form.model.trim(),
          system_prompt: form.system_prompt.trim(),
          description: form.description.trim(),
        });
      }
      cancel();
    } catch (err) {
      setError(err.message || 'Save failed');
    }
  };

  const handleDeleteClick = (e, id) => {
    e.stopPropagation();
    if (confirmingDelete === id) {
      onDelete(id);
      setConfirmingDelete(null);
      if (editingId === id) cancel();
    } else {
      setConfirmingDelete(id);
    }
  };

  const cancelDelete = (e) => {
    e.stopPropagation();
    setConfirmingDelete(null);
  };

  const handleRegenerateAvatar = async (e, p) => {
    e.stopPropagation();
    setRegeneratingAvatar(p.id);
    setAvatarError('');
    setAvatarElapsed(0);
    avatarTimerRef.current = setInterval(() => {
      setAvatarElapsed((s) => s + 1);
    }, 1000);
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), AVATAR_TIMEOUT_MS);
      await onRegenerateAvatar(p.id, { signal: controller.signal });
      clearTimeout(timeout);
    } catch (err) {
      const msg = err.name === 'AbortError'
        ? `Avatar generation timed out (>${Math.round(AVATAR_TIMEOUT_MS / 1000)}s). Try again.`
        : (err.message || 'Failed to regenerate avatar');
      setAvatarError(msg);
      setTimeout(() => setAvatarError(''), 6000);
    } finally {
      clearInterval(avatarTimerRef.current);
      avatarTimerRef.current = null;
      setRegeneratingAvatar(null);
      setAvatarElapsed(0);
    }
  };

  useEffect(() => {
    return () => {
      if (avatarTimerRef.current) clearInterval(avatarTimerRef.current);
    };
  }, []);

  return (
    <div className="personalities-view">
      <div className="personalities-header">
        <div>
          <h2>Personalities</h2>
          <p className="personalities-subtitle">
            Named LLM personas combining a model, a system prompt, and a description.
            Use them in a conversation to make the council deliberate in character.
          </p>
        </div>
        <div className="personalities-header-actions">
          <button
            className="refresh-models-btn"
            onClick={handleRefreshModels}
            disabled={refreshingModels}
            title="Refresh the model list from OpenRouter"
          >
            {refreshingModels ? 'Refreshing…' : '↻ Refresh models'}
          </button>
          <button className="new-personality-btn" onClick={startCreate}>
            + New Personality
          </button>
        </div>
      </div>

      {refreshMessage && <div className="refresh-message">{refreshMessage}</div>}
      {avatarError && <div className="refresh-message avatar-error">{avatarError}</div>}

      {editingId && (
        <form className="personality-form" onSubmit={handleSubmit}>
          <div className="form-row">
            <label>
              <span className="form-label">Name</span>
              <input
                type="text"
                className="form-input"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. The Skeptic"
                autoFocus
              />
            </label>
            <label>
              <span className="form-label">Model</span>
              <select
                className="form-input mono"
                value={form.model}
                onChange={(e) => setForm({ ...form, model: e.target.value })}
              >
                <option value="" disabled>
                  Select a model…
                </option>
                {Object.entries(modelsByProvider).map(([provider, list]) => (
                  <optgroup key={provider} label={provider}>
                    {list.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name} — {m.id}
                      </option>
                    ))}
                  </optgroup>
                ))}
                {/* If the current value isn't in the cache (e.g. edited), show it */}
                {form.model && !models.some((m) => m.id === form.model) && (
                  <optgroup label="Other">
                    <option value={form.model}>{form.model}</option>
                  </optgroup>
                )}
              </select>
            </label>
          </div>
          <label>
            <span className="form-label">System prompt</span>
            <textarea
              className="form-input form-textarea"
              value={form.system_prompt}
              onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
              placeholder="Instructions that define the persona's voice, stance, and reasoning style."
              rows={5}
            />
          </label>
          <label>
            <span className="form-label">Description (optional)</span>
            <input
              type="text"
              className="form-input"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="One-line summary shown in the lineup picker."
            />
          </label>
          {error && <div className="form-error">{error}</div>}
          <div className="form-actions">
            <button type="submit" className="form-btn form-btn-primary">
              {editingId === 'new' ? 'Create' : 'Save'}
            </button>
            <button type="button" className="form-btn form-btn-secondary" onClick={cancel}>
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="personalities-list">
        {personalities.length === 0 ? (
          <div className="no-personalities">
            No personalities yet. Click “+ New Personality” to create one.
          </div>
        ) : (
          personalities.map((p) => (
            <div key={p.id} className="personality-card">
              <div className="personality-card-header">
                <div className="personality-identity">
                  <Avatar
                    svg={p.avatar_svg}
                    name={p.name}
                    size={36}
                    spinning={regeneratingAvatar === p.id}
                  />
                  <div className="personality-name">
                    {p.name}
                  </div>
                </div>
                <div className="personality-actions">
                  <button
                    className="personality-action-btn personality-regenerate"
                    onClick={(e) => handleRegenerateAvatar(e, p)}
                    disabled={regeneratingAvatar === p.id}
                    title="Regenerate avatar (calls DeepSeek V4 Pro, may take 30-90s)"
                  >
                    {regeneratingAvatar === p.id
                      ? `Generating… ${avatarElapsed}s`
                      : '↻ Avatar'}
                  </button>
                  <button
                    className="personality-action-btn"
                    onClick={() => startEdit(p)}
                    title="Edit"
                  >
                    Edit
                  </button>
                  {confirmingDelete === p.id ? (
                    <>
                      <span className="personality-delete-confirm-text">Delete?</span>
                      <button
                        className="personality-action-btn personality-delete-yes"
                        onClick={(e) => handleDeleteClick(e, p.id)}
                      >
                        Yes
                      </button>
                      <button
                        className="personality-action-btn"
                        onClick={cancelDelete}
                      >
                        No
                      </button>
                    </>
                  ) : (
                    <button
                      className="personality-action-btn personality-delete"
                      onClick={(e) => handleDeleteClick(e, p.id)}
                      title="Delete"
                    >
                      Delete
                    </button>
                  )}
                </div>
              </div>
              <div className="personality-model mono">{p.model}</div>
              {p.description && (
                <div className="personality-description">{p.description}</div>
              )}
              <button
                type="button"
                className="personality-prompt-toggle"
                onClick={() =>
                  setExpandedPrompt(expandedPrompt === p.id ? null : p.id)
                }
              >
                {expandedPrompt === p.id ? 'Hide prompt' : 'Show prompt'}
              </button>
              {expandedPrompt === p.id && (
                <div className="personality-prompt">{p.system_prompt}</div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
