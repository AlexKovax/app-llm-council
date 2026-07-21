import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './Stage2.css';

function displayLabel(rank) {
  if (rank.display_name) return rank.display_name;
  const m = rank.model || '';
  return m.split('/')[1] || m;
}

function deAnonymizeText(text, labelToModel) {
  if (!labelToModel) return text;

  let result = text;
  // Replace each "Response X" with the actual display name (already a display
  // string: personality name if set, otherwise short model name).
  Object.entries(labelToModel).forEach(([label, display]) => {
    result = result.replace(new RegExp(label, 'g'), `**${display}**`);
  });
  return result;
}

export default function Stage2({ rankings, labelToModel, aggregateRankings }) {
  const [activeTab, setActiveTab] = useState(0);

  if (!rankings || rankings.length === 0) {
    return null;
  }

  // Clamp active tab in case the previously active one got removed
  const safeTab = Math.min(activeTab, rankings.length - 1);
  const active = rankings[safeTab];
  const activeFailed = !active.ranking && active.error;

  return (
    <div className="stage stage2">
      <h3 className="stage-title">Stage 2: Peer Rankings</h3>

      <h4>Raw Evaluations</h4>
      <p className="stage-description">
        Each participant evaluated all responses (anonymized as Response A, B, C, etc.) and provided rankings.
        Below, names are shown in <strong>bold</strong> for readability, but the original evaluation used anonymous labels.
      </p>

      <div className="tabs">
        {rankings.map((rank, index) => {
          const failed = !rank.ranking && rank.error;
          return (
            <button
              key={index}
              className={`tab ${safeTab === index ? 'active' : ''} ${failed ? 'tab-failed' : ''}`}
              onClick={() => setActiveTab(index)}
              title={failed ? rank.error : undefined}
            >
              {displayLabel(rank)}
              {failed && <span className="tab-error-dot" aria-label="failed">⚠</span>}
            </button>
          );
        })}
      </div>

      <div className="tab-content">
        <div className="ranking-model">
          {active.display_name || active.model}
        </div>
        {activeFailed ? (
          <div className="stage-error">
            <div className="stage-error-title">This model did not provide a ranking</div>
            <div className="stage-error-message">{active.error || 'Unknown error'}</div>
          </div>
        ) : (
          <>
            <div className="ranking-content markdown-content">
              <ReactMarkdown>
                {deAnonymizeText(active.ranking || '', labelToModel)}
              </ReactMarkdown>
            </div>

            {active.parsed_ranking && active.parsed_ranking.length > 0 && (
              <div className="parsed-ranking">
                <strong>Extracted Ranking:</strong>
                <ol>
                  {active.parsed_ranking.map((label, i) => (
                    <li key={i}>
                      {labelToModel && labelToModel[label]
                        ? labelToModel[label]
                        : label}
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </>
        )}
      </div>

      {aggregateRankings && aggregateRankings.length > 0 && (
        <div className="aggregate-rankings">
          <h4>Aggregate Rankings (Street Cred)</h4>
          <p className="stage-description">
            Combined results across all peer evaluations (lower score is better):
          </p>
          <div className="aggregate-list">
            {aggregateRankings.map((agg, index) => (
              <div key={index} className="aggregate-item">
                <span className="rank-position">#{index + 1}</span>
                <span className="rank-model">
                  {agg.model}
                </span>
                <span className="rank-score">
                  Avg: {agg.average_rank.toFixed(2)}
                </span>
                <span className="rank-count">
                  ({agg.rankings_count} votes)
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
