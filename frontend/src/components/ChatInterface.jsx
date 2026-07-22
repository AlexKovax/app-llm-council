import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import Avatar from './Avatar';
import { api } from '../api';
import './ChatInterface.css';

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
  config,
  personalities,
  onSetLineup,
}) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleExport = () => {
    if (conversation) {
      window.open(api.getExportUrl(conversation.id), '_blank');
    }
  };

  if (!conversation) {
    return (
      <div className="chat-interface">
        <div className="empty-state">
          <h2>LLM Council</h2>
          <p>by PANTOMENO — Create a new conversation to get started</p>
        </div>
      </div>
    );
  }

  const isEmpty = conversation.messages.length === 0;
  const isFresh = isEmpty;
  const lineupApplied = (conversation.lineup?.length || 0) > 0;

  return (
    <div className="chat-interface">
      <div className="messages-container">
        {isEmpty ? (
          <div className="empty-state empty-state--picker">
            <h2>Consult the Council</h2>
            <p>Ask a question — multiple LLMs will deliberate and synthesize an answer</p>

            {isFresh && (
              <LineupPicker
                key={conversation.id}
                conversation={conversation}
                config={config}
                personalities={personalities || []}
                onSetLineup={onSetLineup}
              />
            )}
          </div>
        ) : (
          <>
            <div className="export-bar">
              <button className="export-btn" onClick={handleExport} title="Export as Markdown">
                ⬇ Export Markdown
              </button>
            </div>
            {conversation.messages.map((msg, index) => (
            <div key={index} className="message-group">
              {msg.role === 'user' ? (
                <div className="user-message">
                  <div className="message-label">You</div>
                  <div className="message-content">
                    <div className="markdown-content">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="assistant-message">
                  <div className="message-label">LLM Council</div>

                  {/* Stage 1 */}
                  {msg.loading?.stage1 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Running Stage 1: Collecting individual responses...</span>
                    </div>
                  )}
                  {msg.stage1 && <Stage1 responses={msg.stage1} />}

                  {/* Stage 2 */}
                  {msg.loading?.stage2 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Running Stage 2: Peer rankings...</span>
                    </div>
                  )}
                  {msg.stage2 && (
                    <Stage2
                      rankings={msg.stage2}
                      labelToModel={msg.metadata?.label_to_model}
                      aggregateRankings={msg.metadata?.aggregate_rankings}
                    />
                  )}

                  {/* Stage 3 */}
                  {msg.loading?.stage3 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Running Stage 3: Final synthesis...</span>
                    </div>
                  )}
                  {msg.stage3 && <Stage3 finalResponse={msg.stage3} />}
                </div>
              )}
            </div>
            ))}
          </>
        )}
      </div>

      {isEmpty && (
        <form className="input-form" onSubmit={handleSubmit}>
          <textarea
            className="message-input"
            placeholder={
              lineupApplied
                ? 'Ask your question... (Shift+Enter for new line, Enter to send)'
                : '↑ Choose your council above and apply the lineup to start'
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading || !lineupApplied}
            rows={3}
          />
          <button
            type="submit"
            className="send-button"
            disabled={!input.trim() || isLoading || !lineupApplied}
          >
            Send
          </button>
        </form>
      )}
    </div>
  );
}

function LineupPicker({ conversation, config, personalities, onSetLineup }) {
  const initialMode = conversation.mode || 'classic';
  const lineup = conversation.lineup || [];
  const initialChairman = conversation.chairman;

  // If the conversation already has a lineup applied (either classic or
  // personalities), start in summary mode. Otherwise start in edit mode.
  const hasAppliedLineup = lineup.length > 0;
  const [isEditing, setIsEditing] = useState(!hasAppliedLineup);

  const [localMode, setLocalMode] = useState(initialMode);

  // Personalities-mode state
  const [selectedIds, setSelectedIds] = useState(
    new Set(lineup.map((p) => p.id))
  );
  const [localChairmanId, setLocalChairmanId] = useState(initialChairman?.id || null);

  // Classic-mode state: default to ALL council models selected, and the
  // configured chairman model as the default judge.
  const classicLineupModels = initialMode === 'classic'
    ? lineup.map((p) => p.model)
    : [];
  const [selectedModels, setSelectedModels] = useState(
    new Set(classicLineupModels.length > 0
      ? classicLineupModels
      : (config?.council_models || []))
  );
  const [localChairmanModel, setLocalChairmanModel] = useState(
    initialChairman?.model || config?.chairman_model || null
  );

  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const togglePersonality = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleModel = (model) => {
    setSelectedModels((prev) => {
      const next = new Set(prev);
      if (next.has(model)) {
        next.delete(model);
      } else {
        next.add(model);
      }
      return next;
    });
  };

  const handleApply = async () => {
    setError('');
    setSaving(true);
    try {
      if (localMode === 'classic') {
        const chosen = (config?.council_models || []).filter((m) => selectedModels.has(m));
        if (chosen.length < 2) {
          setError('Select at least 2 models (or switch to Personalities mode).');
          setSaving(false);
          return;
        }
        if (!localChairmanModel) {
          setError('Pick a chairman model.');
          setSaving(false);
          return;
        }
        const lineupSnapshot = chosen.map((m) => ({
          id: m,
          name: null,
          model: m,
          system_prompt: null,
        }));
        const chairmanSnapshot = {
          id: localChairmanModel,
          name: null,
          model: localChairmanModel,
          system_prompt: null,
        };
        await onSetLineup(conversation.id, {
          mode: 'classic',
          lineup: lineupSnapshot,
          chairman: chairmanSnapshot,
        });
      } else {
        const chosen = personalities.filter((p) => selectedIds.has(p.id));
        if (chosen.length < 2) {
          setError('Select at least 2 personalities (or switch to Classic mode).');
          setSaving(false);
          return;
        }
        if (!localChairmanId) {
          setError('Pick a chairman personality.');
          setSaving(false);
          return;
        }
        const lineupSnapshot = chosen.map((p) => ({
          id: p.id,
          name: p.name,
          model: p.model,
          system_prompt: p.system_prompt,
          description: p.description || '',
          avatar_svg: p.avatar_svg || '',
        }));
        const chairmanP = personalities.find((p) => p.id === localChairmanId);
        const chairmanSnapshot = chairmanP
          ? {
              id: chairmanP.id,
              name: chairmanP.name,
              model: chairmanP.model,
              system_prompt: chairmanP.system_prompt,
              description: chairmanP.description || '',
              avatar_svg: chairmanP.avatar_svg || '',
            }
          : null;
        await onSetLineup(conversation.id, {
          mode: 'personalities',
          lineup: lineupSnapshot,
          chairman: chairmanSnapshot,
        });
      }
      setIsEditing(false);
    } catch (err) {
      setError(err.message || 'Failed to apply lineup');
    } finally {
      setSaving(false);
    }
  };

  const shortName = (m) => (m ? (m.split('/')[1] || m) : m);

  // ---- Summary view (after Apply or when lineup already set) ----
  if (!isEditing) {
    const isPersonalities = conversation.mode === 'personalities' && lineup.length > 0;
    const chairman = conversation.chairman;

    return (
      <div className="council-config lineup-summary">
        <div className="config-section">
          <div className="config-label">
            {isPersonalities
              ? 'Stage 1 & 2 — Personalities'
              : 'Stage 1 & 2 — Council Members'}
          </div>
          <div className="config-models">
            {isPersonalities
              ? lineup.map((p) => (
                  <span key={p.id} className="config-model">
                    <Avatar svg={p.avatar_svg} name={p.name} size={18} />
                    <span className="config-model-name">{p.name}</span>
                  </span>
                ))
              : lineup.map((p) => (
                  <span key={p.model} className="config-model">
                    {shortName(p.model)}
                  </span>
                ))
            }
          </div>
        </div>
        <div className="config-section">
          <div className="config-label">Stage 3 — Chairman</div>
          <div className="config-models">
            <span className="config-model chairman">
              {isPersonalities
                ? (
                  <>
                    {chairman && (
                      <Avatar svg={chairman.avatar_svg} name={chairman.name} size={18} />
                    )}
                    <span className="config-model-name">{chairman?.name || '—'}</span>
                  </>
                )
                : (chairman ? shortName(chairman.model) : '—')
              }
            </span>
          </div>
        </div>
        <button
          type="button"
          className="apply-lineup-btn"
          onClick={() => { setIsEditing(true); setError(''); }}
        >
          Edit lineup
        </button>
      </div>
    );
  }

  // ---- Edit view (picker) ----
  return (
    <div className="council-config lineup-picker">
      <div className="config-section lineup-mode-section">
        <div className="config-label">Council mode</div>
        <div className="mode-buttons">
          <button
            type="button"
            className={`mode-btn ${localMode === 'classic' ? 'active' : ''}`}
            onClick={() => { setLocalMode('classic'); setError(''); }}
            disabled={saving}
          >
            Classic
          </button>
          <button
            type="button"
            className={`mode-btn ${localMode === 'personalities' ? 'active' : ''}`}
            onClick={() => { setLocalMode('personalities'); setError(''); }}
            disabled={saving}
          >
            Personalities
          </button>
        </div>
      </div>

      {localMode === 'classic' ? (
        <>
          <div className="config-section">
            <div className="config-label">
              Stage 1 & 2 — Council Members ({selectedModels.size} selected)
            </div>
            <div className="personality-picker-grid">
              {(config?.council_models || []).map((model) => {
                const selected = selectedModels.has(model);
                return (
                  <label
                    key={model}
                    className={`picker-card ${selected ? 'selected' : ''}`}
                  >
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => toggleModel(model)}
                      disabled={saving}
                    />
                    <div className="picker-card-header-row">
                      <div className="picker-card-name">{shortName(model)}</div>
                    </div>
                    <div className="picker-card-model mono">{model}</div>
                  </label>
                );
              })}
            </div>
          </div>

          <div className="config-section">
            <div className="config-label">Stage 3 — Chairman (any model)</div>
            <div className="chairman-radio-list">
              {(config?.council_models || []).map((model) => {
                const inLineup = selectedModels.has(model);
                return (
                  <label
                    key={model}
                    className={`picker-radio ${localChairmanModel === model ? 'selected' : ''}`}
                  >
                    <input
                      type="radio"
                      name="chairman-classic"
                      checked={localChairmanModel === model}
                      onChange={() => setLocalChairmanModel(model)}
                      disabled={saving}
                    />
                    <span className="picker-radio-name">{shortName(model)}</span>
                    {inLineup && <span className="picker-radio-tag mono">in lineup</span>}
                    <span className="picker-radio-model mono">{model}</span>
                  </label>
                );
              })}
            </div>
          </div>
        </>
      ) : (
        <>
          <div className="config-section">
            <div className="config-label">
              Stage 1 & 2 — Personalities ({selectedIds.size} selected)
            </div>
            {personalities.length === 0 ? (
              <p className="picker-empty">No personalities yet. Create some in the Personalities view.</p>
            ) : (
              <div className="personality-picker-grid">
                {personalities.map((p) => {
                  const selected = selectedIds.has(p.id);
                  return (
                    <label
                      key={p.id}
                      className={`picker-card ${selected ? 'selected' : ''}`}
                    >
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => togglePersonality(p.id)}
                        disabled={saving}
                      />
                      <div className="picker-card-header-row">
                        <Avatar svg={p.avatar_svg} name={p.name} size={28} />
                        <div className="picker-card-name">{p.name}</div>
                      </div>
                      <div className="picker-card-model mono">{p.model}</div>
                      {p.description && (
                        <div className="picker-card-desc">{p.description}</div>
                      )}
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          {personalities.length > 0 && (
            <div className="config-section">
              <div className="config-label">Stage 3 — Chairman (any personality)</div>
              <div className="chairman-radio-list">
                {personalities.map((p) => {
                  const inLineup = selectedIds.has(p.id);
                  return (
                    <label key={p.id} className={`picker-radio ${localChairmanId === p.id ? 'selected' : ''}`}>
                      <input
                        type="radio"
                        name="chairman"
                        checked={localChairmanId === p.id}
                        onChange={() => setLocalChairmanId(p.id)}
                        disabled={saving}
                      />
                      <Avatar svg={p.avatar_svg} name={p.name} size={22} />
                      <span className="picker-radio-name">{p.name}</span>
                      {inLineup && <span className="picker-radio-tag mono">in lineup</span>}
                      <span className="picker-radio-model mono">{p.model}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}

      {error && <div className="picker-error">{error}</div>}
      <button
        type="button"
        className="apply-lineup-btn"
        onClick={handleApply}
        disabled={saving || (localMode === 'classic'
          ? selectedModels.size < 2 || !localChairmanModel
          : selectedIds.size < 2 || !localChairmanId)}
      >
        {saving ? 'Applying…' : 'Apply lineup'}
      </button>
      <p className="picker-hint">
        {localMode === 'classic'
          ? 'Pick which models deliberate in rounds 1 & 2, and which one judges the final synthesis in round 3.'
          : 'The lineup is snapshot-saved on this conversation. Editing a personality later won\u2019t change conversations that already use it.'}
      </p>
    </div>
  );
}
