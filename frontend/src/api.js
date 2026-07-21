/**
 * API client for the LLM Council backend.
 */

const API_BASE = '';

export const api = {
  /**
   * Get the council configuration (models and chairman).
   */
  async getConfig() {
    const response = await fetch(`${API_BASE}/api/config`);
    if (!response.ok) {
      throw new Error('Failed to get config');
    }
    return response.json();
  },

  /**
   * List all conversations.
   */
  async listConversations() {
    const response = await fetch(`${API_BASE}/api/conversations`);
    if (!response.ok) {
      throw new Error('Failed to list conversations');
    }
    return response.json();
  },

  /**
   * Create a new conversation.
   */
  async createConversation() {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    if (!response.ok) {
      throw new Error('Failed to create conversation');
    }
    return response.json();
  },

  /**
   * Get a specific conversation.
   */
  async getConversation(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}`
    );
    if (!response.ok) {
      throw new Error('Failed to get conversation');
    }
    return response.json();
  },

  /**
   * Send a message in a conversation.
   */
  async sendMessage(conversationId, content) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
      }
    );
    if (!response.ok) {
      throw new Error('Failed to send message');
    }
    return response.json();
  },

  /**
   * Delete a conversation.
   */
  async deleteConversation(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}`,
      {
        method: 'DELETE',
      }
    );
    if (!response.ok) {
      throw new Error('Failed to delete conversation');
    }
    return response.json();
  },

  /**
   * Rename a conversation.
   */
  async renameConversation(conversationId, title) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}`,
      {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ title }),
      }
    );
    if (!response.ok) {
      throw new Error('Failed to rename conversation');
    }
    return response.json();
  },

  /**
   * Get the export URL for a conversation.
   */
  getExportUrl(conversationId) {
    return `${API_BASE}/api/conversations/${conversationId}/export`;
  },

  /**
   * List all personalities.
   */
  async listPersonalities() {
    const response = await fetch(`${API_BASE}/api/personalities`);
    if (!response.ok) {
      throw new Error('Failed to list personalities');
    }
    return response.json();
  },

  /**
   * Get the cached list of OpenRouter models (filtered by provider).
   */
  async listModels() {
    const response = await fetch(`${API_BASE}/api/models`);
    if (!response.ok) {
      throw new Error('Failed to list models');
    }
    return response.json();
  },

  /**
   * Refresh the OpenRouter model cache (calls the live API).
   */
  async refreshModels() {
    const response = await fetch(`${API_BASE}/api/models/refresh`, {
      method: 'POST',
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to refresh models');
    }
    return response.json();
  },

  /**
   * Get the council master prompts (read-only).
   */
  async getSettingsPrompts() {
    const response = await fetch(`${API_BASE}/api/settings/prompts`);
    if (!response.ok) {
      throw new Error('Failed to load settings prompts');
    }
    return response.json();
  },

  /**
   * Create a new personality.
   */
  async createPersonality({ name, model, system_prompt, description }) {
    const response = await fetch(`${API_BASE}/api/personalities`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, model, system_prompt, description }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to create personality');
    }
    return response.json();
  },

  /**
   * Update a personality (partial).
   */
  async updatePersonality(id, fields) {
    const response = await fetch(`${API_BASE}/api/personalities/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(fields),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to update personality');
    }
    return response.json();
  },

  /**
   * Delete a personality.
   */
  async deletePersonality(id) {
    const response = await fetch(`${API_BASE}/api/personalities/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('Failed to delete personality');
    }
    return response.json();
  },

  /**
   * Regenerate the SVG avatar for a personality via an LLM call.
   * Returns the updated personality (with the new avatar_svg field).
   * Pass { signal } in opts to support cancellation/timeout.
   */
  async regeneratePersonalityAvatar(id, opts = {}) {
    const response = await fetch(
      `${API_BASE}/api/personalities/${id}/avatar`,
      { method: 'POST', signal: opts.signal }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to regenerate avatar');
    }
    return response.json();
  },

  /**
   * Upload an image file as the avatar for a personality.
   * The file is read as a base64 data URL on the client side and POSTed
   * as JSON. No LLM call is made. Returns the updated personality.
   */
  async uploadPersonalityAvatar(id, file) {
    const dataUri = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(new Error('Failed to read file'));
      reader.readAsDataURL(file);
    });
    const response = await fetch(
      `${API_BASE}/api/personalities/${id}/avatar/upload`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data_uri: dataUri }),
      }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to upload avatar');
    }
    return response.json();
  },

  /**
   * Set the mode and personality lineup of a conversation.
   */
  async setConversationLineup(conversationId, { mode, lineup, chairman }) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/lineup`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode,
          lineup,
          chairman,
        }),
      }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to set conversation lineup');
    }
    return response.json();
  },

  /**
   * Send a message and receive streaming updates.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {function} onEvent - Callback function for each event: (eventType, data) => void
   * @returns {Promise<void>}
   */
  async sendMessageStream(conversationId, content, onEvent) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
      }
    );

    if (!response.ok) {
      throw new Error('Failed to send message');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          try {
            const event = JSON.parse(data);
            onEvent(event.type, event);
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
    }
  },
};
