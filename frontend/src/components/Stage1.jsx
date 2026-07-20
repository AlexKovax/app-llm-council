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

  const active = responses[activeTab];

  return (
    <div className="stage stage1">
      <h3 className="stage-title">Stage 1: Individual Responses</h3>

      <div className="tabs">
        {responses.map((resp, index) => (
          <button
            key={index}
            className={`tab ${activeTab === index ? 'active' : ''}`}
            onClick={() => setActiveTab(index)}
          >
            <Avatar svg={resp.avatar_svg} name={displayName(resp)} size={16} />
            <span>{displayName(resp)}</span>
          </button>
        ))}
      </div>

      <div className="tab-content">
        <div className="model-name">{active.model}</div>
        <div className="response-text markdown-content">
          <ReactMarkdown>{active.response}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
