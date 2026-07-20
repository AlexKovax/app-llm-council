import { useState, useRef, useEffect } from 'react';
import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onRenameConversation,
  view,
  onViewChange,
}) {
  const [confirmingDelete, setConfirmingDelete] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const editInputRef = useRef(null);

  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingId]);

  const handleDeleteClick = (e, convId) => {
    e.stopPropagation();
    if (confirmingDelete === convId) {
      onDeleteConversation(convId);
      setConfirmingDelete(null);
    } else {
      setConfirmingDelete(convId);
      setEditingId(null);
    }
  };

  const handleCancelDelete = (e) => {
    e.stopPropagation();
    setConfirmingDelete(null);
  };

  const handleDoubleClick = (e, conv) => {
    e.stopPropagation();
    setEditingId(conv.id);
    setEditTitle(conv.title || 'New Conversation');
    setConfirmingDelete(null);
  };

  const handleRenameSubmit = (e, convId) => {
    e.preventDefault();
    e.stopPropagation();
    const trimmed = editTitle.trim();
    if (trimmed) {
      onRenameConversation(convId, trimmed);
    }
    setEditingId(null);
  };

  const handleRenameKeyDown = (e) => {
    if (e.key === 'Escape') {
      e.stopPropagation();
      setEditingId(null);
    }
  };

  const filteredConversations = searchQuery.trim()
    ? conversations.filter((conv) =>
        (conv.title || '').toLowerCase().includes(searchQuery.toLowerCase())
      )
    : conversations;

  const formatDate = (isoString) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    } catch {
      return '';
    }
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>LLM Council</h1>
        <div className="sidebar-subtitle">by PANTOMENO</div>
        <div className="view-toggle">
          <button
            className={`view-toggle-btn ${view === 'conversations' ? 'active' : ''}`}
            onClick={() => onViewChange('conversations')}
          >
            Conversations
          </button>
          <button
            className={`view-toggle-btn ${view === 'personalities' ? 'active' : ''}`}
            onClick={() => onViewChange('personalities')}
          >
            Personalities
          </button>
        </div>
        {view === 'conversations' && (
          <>
            <button className="new-conversation-btn" onClick={onNewConversation}>
              + New Conversation
            </button>
            <input
              className="search-input"
              type="text"
              placeholder="Search conversations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </>
        )}
      </div>

      {view === 'conversations' && (
        <div className="conversation-list">
          {conversations.length === 0 ? (
            <div className="no-conversations">No conversations yet</div>
          ) : filteredConversations.length === 0 ? (
            <div className="no-conversations">No matching conversations</div>
          ) : (
            filteredConversations.map((conv) => (
              <div
                key={conv.id}
                className={`conversation-item ${
                  conv.id === currentConversationId ? 'active' : ''
                }`}
                onClick={() => {
                  setConfirmingDelete(null);
                  setEditingId(null);
                  onSelectConversation(conv.id);
                }}
              >
                <div
                  className="conversation-item-content"
                  onDoubleClick={(e) => handleDoubleClick(e, conv)}
                >
                  {editingId === conv.id ? (
                    <form
                      className="rename-form"
                      onSubmit={(e) => handleRenameSubmit(e, conv.id)}
                    >
                      <input
                        ref={editInputRef}
                        className="rename-input"
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onKeyDown={handleRenameKeyDown}
                        onBlur={() => setEditingId(null)}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </form>
                  ) : (
                    <>
                      <div className="conversation-title">
                        {conv.title || 'New Conversation'}
                      </div>
                      <div className="conversation-meta">
                        <span>{conv.message_count} messages</span>
                        {conv.created_at && (
                          <>
                            <span className="meta-sep">·</span>
                            <span>{formatDate(conv.created_at)}</span>
                          </>
                        )}
                        {conv.mode === 'personalities' && (
                          <>
                            <span className="meta-sep">·</span>
                            <span className="mode-tag">personalities</span>
                          </>
                        )}
                      </div>
                    </>
                  )}
                </div>
                {confirmingDelete === conv.id ? (
                  <div className="delete-confirm">
                    <span className="delete-confirm-text">Delete?</span>
                    <button
                      className="delete-confirm-btn delete-yes"
                      onClick={(e) => handleDeleteClick(e, conv.id)}
                    >
                      Yes
                    </button>
                    <button
                      className="delete-confirm-btn delete-no"
                      onClick={handleCancelDelete}
                    >
                      No
                    </button>
                  </div>
                ) : (
                  <button
                    className="delete-btn"
                    onClick={(e) => handleDeleteClick(e, conv.id)}
                    title="Delete conversation"
                  >
                    ×
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
