import ReactMarkdown from 'react-markdown';
import './Stage3.css';

export default function Stage3({ finalResponse }) {
  if (!finalResponse) {
    return null;
  }

  const display = finalResponse.display_name
    || (finalResponse.model && (finalResponse.model.split('/')[1] || finalResponse.model))
    || 'Chairman';
  const failed = !finalResponse.response && finalResponse.error;

  return (
    <div className="stage stage3">
      <h3 className="stage-title">Stage 3: Final Council Answer</h3>
      <div className="final-response">
        <div className="chairman-label">
          Chairman: {display}
        </div>
        {failed ? (
          <div className="stage-error">
            <div className="stage-error-title">The chairman did not produce a final answer</div>
            <div className="stage-error-message">{finalResponse.error || 'Unknown error'}</div>
          </div>
        ) : (
          <div className="final-text markdown-content">
            <ReactMarkdown>{finalResponse.response}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
