import ReactMarkdown from 'react-markdown';
import './Stage3.css';

export default function Stage3({ finalResponse }) {
  if (!finalResponse) {
    return null;
  }

  const display = finalResponse.display_name
    || (finalResponse.model && (finalResponse.model.split('/')[1] || finalResponse.model))
    || 'Chairman';

  return (
    <div className="stage stage3">
      <h3 className="stage-title">Stage 3: Final Council Answer</h3>
      <div className="final-response">
        <div className="chairman-label">
          Chairman: {display}
        </div>
        <div className="final-text markdown-content">
          <ReactMarkdown>{finalResponse.response}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
