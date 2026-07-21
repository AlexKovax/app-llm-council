import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import Avatar from './Avatar';
import './Stage1.css';

function displayName(resp) {
  if (resp.display_name) return resp.display_name;
  const m = resp.model || '';
  return m.split('/')[1] || m;
}

export default function Stage1({ responses }) {
  const [activeTab, setActiveTab] = useState(0);

  if (!responses || responses.length === 0) {
    return null;
  }

  // Clamp active tab in case the previously active one got removed
  const safeTab = Math.min(activeTab, responses.length - 1);
  const active = responses[safeTab];

  return (
    <div className="stage stage1">
      <h3 className="stage-title">Stage 1: Individual Responses</h3>

      <div className="tabs">
        {responses.map((resp, index) => {
          const failed = !resp.response && resp.error;
          return (
            <button
              key={index}
              className={`tab ${safeTab === index ? 'active' : ''} ${failed ? 'tab-failed' : ''}`}
              onClick={() => setActiveTab(index)}
              title={failed ? resp.error : undefined}
            >
              <Avatar svg={resp.avatar_svg} name={displayName(resp)} size={16} />
              <span>{displayName(resp)}</span>
              {failed && <span className="tab-error-dot" aria-label="failed">⚠</span>}
            </button>
          );
        })}
      </div>

      <div className="tab-content">
        <div className="model-name">{active.model}</div>
        {active.response ? (
          <div className="response-text markdown-content">
            <ReactMarkdown>{active.response}</ReactMarkdown>
          </div>
        ) : (
          <div className="stage-error">
            <div className="stage-error-title">This model did not respond</div>
            <div className="stage-error-message">{active.error || 'Unknown error'}</div>
          </div>
        )}
      </div>
    </div>
  );
}
