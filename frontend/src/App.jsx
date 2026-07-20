import { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import Personalities from './components/Personalities';
import Settings from './components/Settings';
import { api } from './api';
import './App.css';

function App() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [config, setConfig] = useState(null);
  const [view, setView] = useState('conversations');
  const [personalities, setPersonalities] = useState([]);
  const [models, setModels] = useState([]);

  const loadConversations = async () => {
    try {
      const convs = await api.listConversations();
      setConversations(convs);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const loadConfig = async () => {
    try {
      const cfg = await api.getConfig();
      setConfig(cfg);
    } catch (error) {
      console.error('Failed to load config:', error);
    }
  };

  const loadPersonalities = async () => {
    try {
      const ps = await api.listPersonalities();
      setPersonalities(ps);
    } catch (error) {
      console.error('Failed to load personalities:', error);
    }
  };

  const loadModels = async () => {
    try {
      const data = await api.listModels();
      setModels(data.models || []);
    } catch (error) {
      console.error('Failed to load models:', error);
    }
  };

  const loadConversation = async (id) => {
    try {
      const conv = await api.getConversation(id);
      setCurrentConversation(conv);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  // Load conversations and council config on mount
  useEffect(() => {
    loadConversations();
    loadConfig();
    loadPersonalities();
    loadModels();
  }, []);

  // Load conversation details when selected
  useEffect(() => {
    if (currentConversationId) {
      loadConversation(currentConversationId);
    }
  }, [currentConversationId]);

  const handleNewConversation = async () => {
    try {
      const newConv = await api.createConversation();
      setConversations([
        { id: newConv.id, created_at: newConv.created_at, message_count: 0, mode: 'classic' },
        ...conversations,
      ]);
      setCurrentConversationId(newConv.id);
      setCurrentConversation(newConv);
      setView('conversations');
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleSelectConversation = (id) => {
    setCurrentConversationId(id);
    setView('conversations');
  };

  const handleDeleteConversation = async (id) => {
    try {
      await api.deleteConversation(id);

      setConversations((prev) => {
        const remaining = prev.filter((c) => c.id !== id);
        if (id === currentConversationId) {
          setCurrentConversationId(remaining.length > 0 ? remaining[0].id : null);
          setCurrentConversation(null);
        }
        return remaining;
      });
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  };

  const handleRenameConversation = async (id, title) => {
    try {
      await api.renameConversation(id, title);
      setConversations((prev) =>
        prev.map((c) => (c.id === id ? { ...c, title } : c))
      );
    } catch (error) {
      console.error('Failed to rename conversation:', error);
    }
  };

  const handleSetLineup = async (conversationId, { mode, lineup, chairman }) => {
    const updated = await api.setConversationLineup(conversationId, { mode, lineup, chairman });
    setCurrentConversation(updated);
    setConversations((prev) =>
      prev.map((c) => (c.id === conversationId ? { ...c, mode: updated.mode } : c))
    );
    return updated;
  };

  const handleCreatePersonality = async (data) => {
    const created = await api.createPersonality(data);
    await loadPersonalities();
    return created;
  };

  const handleUpdatePersonality = async (id, fields) => {
    const updated = await api.updatePersonality(id, fields);
    await loadPersonalities();
    return updated;
  };

  const handleDeletePersonality = async (id) => {
    await api.deletePersonality(id);
    await loadPersonalities();
  };

  const handleRefreshModels = async () => {
    const data = await api.refreshModels();
    setModels(data.models || []);
    return data;
  };

  const handleLoadPrompts = async () => api.getSettingsPrompts();

  const handleSendMessage = async (content) => {
    if (!currentConversationId) return;

    setIsLoading(true);
    try {
      // Optimistically add user message to UI
      const userMessage = { role: 'user', content };
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
      }));

      // Create a partial assistant message that will be updated progressively
      const assistantMessage = {
        role: 'assistant',
        stage1: null,
        stage2: null,
        stage3: null,
        metadata: null,
        loading: {
          stage1: false,
          stage2: false,
          stage3: false,
        },
      };

      // Add the partial assistant message
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
      }));

      // Send message with streaming
      await api.sendMessageStream(currentConversationId, content, (eventType, event) => {
        switch (eventType) {
          case 'stage1_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.stage1 = true;
              return { ...prev, messages };
            });
            break;

          case 'stage1_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.stage1 = event.data;
              lastMsg.loading.stage1 = false;
              return { ...prev, messages };
            });
            break;

          case 'stage2_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.stage2 = true;
              return { ...prev, messages };
            });
            break;

          case 'stage2_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.stage2 = event.data;
              lastMsg.metadata = event.metadata;
              lastMsg.loading.stage2 = false;
              return { ...prev, messages };
            });
            break;

          case 'stage3_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.stage3 = true;
              return { ...prev, messages };
            });
            break;

          case 'stage3_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.stage3 = event.data;
              lastMsg.loading.stage3 = false;
              return { ...prev, messages };
            });
            break;

          case 'title_complete':
            // Reload conversations to get updated title
            loadConversations();
            break;

          case 'complete':
            // Stream complete, reload conversations list
            loadConversations();
            setIsLoading(false);
            break;

          case 'error':
            console.error('Stream error:', event.message);
            setIsLoading(false);
            break;

          default:
            console.log('Unknown event type:', eventType);
        }
      });
    } catch (error) {
      console.error('Failed to send message:', error);
      // Remove optimistic messages on error
      setCurrentConversation((prev) => ({
        ...prev,
        messages: prev.messages.slice(0, -2),
      }));
      setIsLoading(false);
    }
  };

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onDeleteConversation={handleDeleteConversation}
        onRenameConversation={handleRenameConversation}
        view={view}
        onViewChange={setView}
      />
      {view === 'personalities' ? (
        <Personalities
          personalities={personalities}
          models={models}
          onRefreshModels={handleRefreshModels}
          onCreate={handleCreatePersonality}
          onUpdate={handleUpdatePersonality}
          onDelete={handleDeletePersonality}
        />
      ) : view === 'settings' ? (
        <Settings onLoadPrompts={handleLoadPrompts} />
      ) : (
        <ChatInterface
          conversation={currentConversation}
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
          config={config}
          personalities={personalities}
          onSetLineup={handleSetLineup}
        />
      )}
    </div>
  );
}

export default App;
