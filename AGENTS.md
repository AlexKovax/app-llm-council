# CLAUDE.md - Technical Notes for LLM Council

This file contains technical details, architectural decisions, and important implementation notes for future development sessions.

## Project Overview

LLM Council is a 3-stage deliberation system where multiple LLMs collaboratively answer user questions. The key innovation is anonymized peer review in Stage 2, preventing models from playing favorites.

## Architecture

### Backend Structure (`backend/`)

**`config.py`**
- Contains `COUNCIL_MODELS` (list of OpenRouter model identifiers)
- Contains `CHAIRMAN_MODEL` (model that synthesizes final answer)
- Uses environment variable `OPENROUTER_API_KEY` from `.env`
- Backend runs on **port 8001** (NOT 8000 - user had another app on 8000)

**`openrouter.py`**
- `query_model()`: Single async model query
- `query_models_parallel()`: Parallel queries using `asyncio.gather()`
- Returns dict with 'content' and optional 'reasoning_details'
- Graceful degradation: returns None on failure, continues with successful responses

**`council.py`** - The Core Logic
- `stage1_collect_responses()`: Parallel queries to all council models
- `stage2_collect_rankings()`:
  - Anonymizes responses as "Response A, B, C, etc."
  - Creates `label_to_model` mapping for de-anonymization
  - Prompts models to evaluate and rank (with strict format requirements)
  - Returns tuple: (rankings_list, label_to_model_dict)
  - Each ranking includes both raw text and `parsed_ranking` list
- `stage3_synthesize_final()`: Chairman synthesizes from all responses + rankings
- `parse_ranking_from_text()`: Extracts "FINAL RANKING:" section, handles both numbered lists and plain format
- `calculate_aggregate_rankings()`: Computes average rank position across all peer evaluations

**`storage.py`**
- JSON-based conversation storage in `data/conversations/`
- Each conversation: `{id, created_at, title, messages[]}`
- Assistant messages contain: `{role, stage1, stage2, stage3}`
- Note: metadata (label_to_model, aggregate_rankings) is NOT persisted to storage, only returned via API
- `delete_conversation()`: Removes the JSON file from disk permanently (not soft-delete)
- `update_conversation_title()`: Updates the title of an existing conversation

**`main.py`**
- FastAPI app with CORS enabled for localhost:5173 and localhost:3000
- API Endpoints:
  - `GET /` — Health check
  - `GET /api/config` — Council configuration (council_models + chairman_model), used by the frontend to display the model lineup on new conversations
  - `GET /api/conversations` — List all conversations (metadata only)
  - `POST /api/conversations` — Create new conversation
  - `GET /api/conversations/{id}` — Get full conversation
  - `PATCH /api/conversations/{id}` — Rename conversation (body: `{title: "..."}`)
  - `DELETE /api/conversations/{id}` — Delete conversation permanently
  - `GET /api/conversations/{id}/export` — Export conversation as Markdown download
  - `POST /api/conversations/{id}/message` — Send message (non-streaming)
  - `POST /api/conversations/{id}/message/stream` — Send message (SSE streaming)
- POST `/api/conversations/{id}/message` returns metadata in addition to stages
- Metadata includes: label_to_model mapping and aggregate_rankings

### Frontend Structure (`frontend/src/`)

**`App.jsx`**
- Main orchestration: manages conversations list and current conversation
- Handles message sending, renaming, deletion, and metadata storage
- `handleDeleteConversation(id)`: Deletes via API, updates conversation list, switches to next conversation if current was deleted
- `handleRenameConversation(id, title)`: Renames via PATCH API, updates sidebar optimistically
- Important: metadata is stored in the UI state for display but not persisted to backend JSON

**`components/ChatInterface.jsx`**
- Multiline textarea (3 rows, resizable)
- Enter to send, Shift+Enter for new line
- User messages wrapped in markdown-content class for padding
- Export button (⬇ Export Markdown) appears in top-right when a conversation has messages, triggers download via `GET /api/.../export`
- Empty state (new conversation, no messages) displays the council lineup fetched from `GET /api/config`: council members (Stages 1 & 2) as mono chips on cream card, chairman chip with emerald background (matching Stage 3 styling)

**`components/Sidebar.jsx`**
- Conversation list with active highlighting
- "+ New Conversation" button at top
- Search bar to filter conversations by title (client-side)
- Double-click on a conversation title to rename inline (Enter to confirm, Escape to cancel)
- Delete with confirmation: first click on × shows "Delete? Yes / No", second click confirms

**`components/Stage1.jsx`**
- Tab view of individual model responses
- ReactMarkdown rendering with markdown-content wrapper

**`components/Stage2.jsx`**
- **Critical Feature**: Tab view showing RAW evaluation text from each model
- De-anonymization happens CLIENT-SIDE for display (models receive anonymous labels)
- Shows "Extracted Ranking" below each evaluation so users can validate parsing
- Aggregate rankings shown with average position and vote count
- Explanatory text clarifies that boldface model names are for readability only

**`components/Stage3.jsx`**
- Final synthesized answer from chairman
- Emerald-tinted background (Pantomeno design system) to highlight conclusion

## Design System

The UI adopts the **PANTOMENO** brand identity (https://www.pantomeno.com/).

### Color Palette (CSS Custom Properties in `index.css`)

| Token | Value | Usage |
|-------|-------|-------|
| `--carbon` | `#1A1A1A` | Primary text, sidebar background, send button |
| `--ivory` | `#FFFEF1` | Page background, card backgrounds |
| `--cream` | `#F2F1E4` | Section backgrounds (stages, input form, code blocks) |
| `--cream-light` | `#E5E1CF` | Borders, disabled states |
| `--blush` | `#FFC7CD` | Delete/danger actions |
| `--terracotta` | `#5B2E25` | Button hover state |
| `--azur` | `#A8D8F0` | Primary accent: active tabs, focus rings, spinners, rankings |
| `--azur-light` | `#D6EEF9` | User messages, aggregate rankings background |
| `--emerald` | `#86ECB8` | Stage 3 border |
| `--emerald-light` | `#C2F6D9` | Stage 3 background |
| `--neutral-500` | `#8A8576` | Muted text, monospace labels |
| `--neutral-600` | `#6B6759` | Secondary text, blockquotes |
| `--neutral-700` | `#4D4940` | Export button text |

### Typography

| Role | Font | Usage |
|------|------|-------|
| Headings | `Space Grotesk` (Google Fonts) | Stage titles, app title, rankings, h1-h6 in markdown |
| Body | `Onest` (Google Fonts) | Body text, buttons, inputs, descriptions |
| Monospace | `Inconsolata` (Google Fonts) | Model names, labels, rankings, metadata, code |

Fonts are loaded from Google Fonts in `index.html` and declared as CSS custom properties:
- `--font-heading: 'Space Grotesk', sans-serif`
- `--font-body: 'Onest', sans-serif`
- `--font-mono: 'Inconsolata', monospace`

### Layout Principles
- **Sidebar**: Dark theme — carbon (`#1A1A1A`) background, ivory text, azur accents for active state
- **Main area**: Light/ivory background with cream section backgrounds
- **Border radius**: `1rem` (16px) for cards/stages, `0.5rem` (8px) for tabs/buttons
- **No gradients**: Solid colors only, consistent with Pantomeno's design
- **Dark/light contrast**: Sidebar (dark) vs main content (light) mirrors Pantomeno's alternating section themes
- **Branding**: "LLM Council" title with "by PANTOMENO" subtitle in sidebar

### CSS Architecture
All styles use global CSS (no modules, no CSS-in-JS) with these custom properties defined in `index.css:root`. All component CSS files reference `var(--token)` — never hardcoded hex colors. This ensures consistency across the app.

## Key Design Decisions

### Stage 2 Prompt Format
The Stage 2 prompt is very specific to ensure parseable output:
```
1. Evaluate each response individually first
2. Provide "FINAL RANKING:" header
3. Numbered list format: "1. Response C", "2. Response A", etc.
4. No additional text after ranking section
```

This strict format allows reliable parsing while still getting thoughtful evaluations.

### De-anonymization Strategy
- Models receive: "Response A", "Response B", etc.
- Backend creates mapping: `{"Response A": "openai/gpt-5.1", ...}`
- Frontend displays model names in **bold** for readability
- Users see explanation that original evaluation used anonymous labels
- This prevents bias while maintaining transparency

### Error Handling Philosophy
- Continue with successful responses if some models fail (graceful degradation)
- Never fail the entire request due to single model failure
- Log errors but don't expose to user unless all models fail

### UI/UX Transparency
- All raw outputs are inspectable via tabs
- Parsed rankings shown below raw text for validation
- Users can verify system's interpretation of model outputs
- This builds trust and allows debugging of edge cases

## Important Implementation Details

### Relative Imports
All backend modules use relative imports (e.g., `from .config import ...`) not absolute imports. This is critical for Python's module system to work correctly when running as `python -m backend.main`.

### API Base URL (`frontend/src/api.js`)
- `API_BASE` is set to `''` (empty string — relative URLs)
- This is **critical** for production: requests go through Nginx reverse proxy, not directly to `localhost:8001`
- In dev mode, Vite proxies `/api` → `http://localhost:8001` (configured in `vite.config.js`)
- NEVER set `API_BASE` to an absolute URL like `http://localhost:8001` — it breaks production because the browser resolves it to the user's machine, not the server

### Vite Configuration (`frontend/vite.config.js`)
- `server.allowedHosts`: must include `llmcouncil.hosakka.com` for production
- `server.proxy`: proxies `/api` → `http://localhost:8001` for local dev mode (Nginx handles this in production)
- Both settings are safe for local dev and required for prod

### Port Configuration
- Backend: 8001 (changed from 8000 to avoid conflict)
- Frontend: 5173 (Vite default)
- If changing backend port, update: `backend/main.py`, `vite.config.js` proxy, and Nginx config on server

### Markdown Rendering
All ReactMarkdown components must be wrapped in `<div className="markdown-content">` for proper spacing. This class is defined globally in `index.css`.

### Model Configuration
Models are hardcoded in `backend/config.py`. `COUNCIL_MODELS` is the pool of models offered as Stage 1 participants in classic mode (the user picks a subset at conversation creation, default: all). `CHAIRMAN_MODEL` is the default chairman selection in classic mode when the user has not explicitly picked one. Chairman can be the same or different from council members. The current default is `openai/gpt-5.6-sol` as chairman. Classic mode now also snapshots the chosen lineup + chairman onto the conversation (same `lineup`/`chairman` fields as personalities mode, with `name: null` and `system_prompt: null`), so `_resolve_participants` returns the stored lineup for both modes.

## Deployment

### Server Setup
The server runs on a DigitalOcean Droplet (Debian) at `llmcouncil.hosakka.com`. The initial setup was done via a script at `/root/install.sh` on the server which:
- Installs Node.js 20 LTS, Python/uv, Nginx, certbot (Let's Encrypt)
- Clones the repo to `/opt/llm-council`
- Creates systemd services: `llm-council-backend.service` and `llm-council-frontend.service`
- Configures Nginx as reverse proxy with Basic Auth + HTTPS

### Server Architecture
```
Browser (HTTPS)
    ↓
Nginx (:443, :80)
    ├── /api/* → proxy_pass → Backend (:8001)
    └── /*     → proxy_pass → Frontend Vite dev (:5173)
```

### Deploy Script (`deploy.sh`)
Usage: `./deploy.sh`

**IMPORTANT: Always commit (and push) all code changes BEFORE deploying.** Production must never run uncommitted code — this guarantees the deployed state is reproducible and traceable in git history. If `git status` shows modified files, commit them first.

What it does:
1. `rsync` source code to `/opt/llm-council` on the server
2. Excludes: `.venv/`, `node_modules/`, `__pycache__/`, `.git/`, `.env`, `data/`, `CLAUDE.md`
3. Runs `uv sync` on the server to update Python dependencies
4. Restarts both systemd services

### Critical: Never overwrite `.env` or `data/` on server
- `.env` on the server contains the production `OPENROUTER_API_KEY` (set in the systemd service env and .env file)
- `data/` contains production conversation data (JSON files)
- The deploy script excludes both via rsync. If you intentionally change these, deploy them manually.

### Post-deploy checklist
- `systemctl status llm-council-backend llm-council-frontend` — both must be active
- `journalctl -u llm-council-backend -n 20` — check for backend errors
- `journalctl -u llm-council-frontend -n 20` — check for frontend errors
- Visit `https://llmcouncil.hosakka.com` and verify the app loads

## Common Gotchas

1. **Module Import Errors**: Always run backend as `python -m backend.main` from project root, not from backend directory
2. **CORS Issues**: Frontend must match allowed origins in `main.py` CORS middleware
3. **Ranking Parse Failures**: If models don't follow format, fallback regex extracts any "Response X" patterns in order
4. **Missing Metadata**: Metadata is ephemeral (not persisted), only available in API responses
  5. **Deleting active conversation**: When deleting the currently viewed conversation, the UI automatically switches to the next available one or returns to the welcome screen

## Future Enhancement Ideas

- Configurable council/chairman via UI instead of config file
- Delete individual messages from a conversation
- Model performance analytics over time
- Custom ranking criteria (not just accuracy/insight)
- Support for reasoning models (o1, etc.) with special handling
- Dark mode theme

## Testing Notes

Use `test_openrouter.py` to verify API connectivity and test different model identifiers before adding to council. The script tests both streaming and non-streaming modes.

## Data Flow Summary

```
User Query
    ↓
Stage 1: Parallel queries → [individual responses]
    ↓
Stage 2: Anonymize → Parallel ranking queries → [evaluations + parsed rankings]
    ↓
Aggregate Rankings Calculation → [sorted by avg position]
    ↓
Stage 3: Chairman synthesis with full context
    ↓
Return: {stage1, stage2, stage3, metadata}
    ↓
Frontend: Display with tabs + validation UI
```

The entire flow is async/parallel where possible to minimize latency.
