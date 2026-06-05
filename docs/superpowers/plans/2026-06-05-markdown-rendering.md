# Markdown Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Markdown rendering to AI assistant chat messages using react-markdown + remark-gfm.

**Architecture:** Modify `MessageBubble.jsx` to conditionally render assistant messages through `<ReactMarkdown>`, keeping user messages as plain text. Add dark-theme CSS styles for all Markdown elements. Tiny change — 3 files, no structural refactor.

**Tech Stack:** React 18, react-markdown, remark-gfm

**Spec:** `docs/superpowers/specs/2026-06-05-markdown-rendering-design.md`

---

### Task 1: Install Dependencies

**Files:**
- Modify: `electron-app/package.json` (via npm install)

- [ ] **Step 1: Install react-markdown and remark-gfm**

```bash
cd electron-app
npm config set proxy http://127.0.0.1:7890
npm config set https-proxy http://127.0.0.1:7890
npm config set strict-ssl false
npm install react-markdown remark-gfm
```

Expected: Both packages added to `package.json` dependencies, no errors.

- [ ] **Step 2: Verify packages installed**

```bash
node -e "console.log(require('react-markdown/package.json').version); console.log(require('remark-gfm/package.json').version)"
```

Expected: Two version numbers printed, no errors.

- [ ] **Step 3: Commit**

```bash
git add electron-app/package.json electron-app/package-lock.json
git commit -m "deps: add react-markdown + remark-gfm for markdown rendering

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Modify MessageBubble to Render Markdown

**Files:**
- Modify: `electron-app/src/renderer/components/MessageBubble.jsx` (lines 1-28, full rewrite)

- [ ] **Step 1: Replace MessageBubble.jsx with markdown-aware version**

Current file at `electron-app/src/renderer/components/MessageBubble.jsx`:

```jsx
import React from 'react';

export default function MessageBubble({ message }) {
  const { id, role, content, isStreaming, timestamp } = message;
  const label = role === 'user' ? '你' : '助理';

  const bubbleClass = [
    'message-bubble',
    role === 'user' ? 'user' : 'assistant',
  ].join(' ');

  const contentClass = [
    'bubble-content',
    isStreaming ? 'streaming' : '',
  ].filter(Boolean).join(' ');

  const timeStr = timestamp
    ? new Date(timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : '';

  return (
    <div className={bubbleClass} data-msg-id={id}>
      <span className="bubble-label">{label}</span>
      <div className={contentClass}>{content}</div>
      {timeStr && <span className="bubble-timestamp">{timeStr}</span>}
    </div>
  );
}
```

Replace with:

```jsx
import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function MessageBubble({ message }) {
  const { id, role, content, isStreaming, timestamp } = message;
  const label = role === 'user' ? '你' : '助理';

  const bubbleClass = [
    'message-bubble',
    role === 'user' ? 'user' : 'assistant',
  ].join(' ');

  const contentClass = [
    'bubble-content',
    isStreaming ? 'streaming' : '',
  ].filter(Boolean).join(' ');

  const timeStr = timestamp
    ? new Date(timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : '';

  return (
    <div className={bubbleClass} data-msg-id={id}>
      <span className="bubble-label">{label}</span>
      <div className={contentClass}>
        {role === 'assistant' ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {content}
          </ReactMarkdown>
        ) : (
          content
        )}
      </div>
      {timeStr && <span className="bubble-timestamp">{timeStr}</span>}
    </div>
  );
}
```

- [ ] **Step 2: Verify build succeeds**

```bash
cd electron-app
npx vite build --config vite.main.config.mjs 2>&1 | tail -5
```

Expected: Build completes without errors.

- [ ] **Step 3: Commit**

```bash
git add electron-app/src/renderer/components/MessageBubble.jsx
git commit -m "feat: render assistant messages as Markdown via react-markdown + remark-gfm

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Add Markdown CSS Styles

**Files:**
- Modify: `electron-app/src/renderer/App.css` (append after existing `.bubble-content` styles, around line 217)

- [ ] **Step 1: Append Markdown element styles to App.css**

Insert the following block after the `.bubble-timestamp` rule (after line 217 of the current file):

```css
/* === Markdown Content Styles === */
.bubble-content h1,
.bubble-content h2,
.bubble-content h3,
.bubble-content h4,
.bubble-content h5,
.bubble-content h6 {
  margin: 12px 0 6px;
  line-height: 1.3;
}
.bubble-content h1 { font-size: 20px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
.bubble-content h2 { font-size: 17px; border-bottom: 1px solid var(--border); padding-bottom: 4px; }
.bubble-content h3 { font-size: 15px; }
.bubble-content h4 { font-size: 14px; }
.bubble-content h5,
.bubble-content h6 { font-size: 13px; color: var(--text-secondary); }

.bubble-content p {
  margin: 4px 0;
}
.bubble-content p:first-child { margin-top: 0; }
.bubble-content p:last-child { margin-bottom: 0; }

.bubble-content ul,
.bubble-content ol {
  padding-left: 24px;
  margin: 6px 0;
}

.bubble-content li {
  margin: 2px 0;
}

.bubble-content code {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  background: rgba(233, 69, 96, 0.15);
  color: var(--accent);
  padding: 2px 6px;
  border-radius: 4px;
}

.bubble-content pre {
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 12px;
  margin: 8px 0;
  overflow-x: auto;
}

.bubble-content pre code {
  background: none;
  color: #c9d1d9;
  padding: 0;
  border-radius: 0;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre;
}

.bubble-content blockquote {
  border-left: 3px solid var(--accent);
  padding: 6px 12px;
  margin: 8px 0;
  background: rgba(233, 69, 96, 0.06);
  border-radius: 0 6px 6px 0;
  color: var(--text-secondary);
}

.bubble-content blockquote p {
  margin: 4px 0;
}

.bubble-content a {
  color: #4e9fff;
  text-decoration: none;
}
.bubble-content a:hover {
  text-decoration: underline;
}

.bubble-content hr {
  border: none;
  border-top: 1px solid var(--border);
  margin: 12px 0;
}

.bubble-content table {
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 13px;
  width: 100%;
}
.bubble-content th,
.bubble-content td {
  border: 1px solid var(--border);
  padding: 6px 10px;
  text-align: left;
}
.bubble-content th {
  background: rgba(233, 69, 96, 0.1);
  font-weight: 600;
}

.bubble-content img {
  max-width: 100%;
  border-radius: 6px;
}

.bubble-content strong {
  color: #fff;
}

.bubble-content input[type="checkbox"] {
  margin-right: 6px;
  accent-color: var(--accent);
}
```

Do NOT remove `white-space: pre-wrap` from `.bubble-content` — user messages still need it to preserve line breaks. ReactMarkdown renders block elements (`<p>`, `<pre>`, `<h1>`, etc.) which handle their own whitespace correctly even with the inherited `pre-wrap`. The `.bubble-content` rule stays as-is.

- [ ] **Step 2: Verify build succeeds**

```bash
cd electron-app
npx vite build --config vite.main.config.mjs 2>&1 | tail -5
```

Expected: Build completes without errors.

- [ ] **Step 3: Commit**

```bash
git add electron-app/src/renderer/App.css
git commit -m "style: add dark-theme Markdown element styles for chat bubbles

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: End-to-End Verification

- [ ] **Step 1: Start backend and frontend, send a test message**

```bash
# Terminal 1 — start backend
cd backend
python main.py &
```

```bash
# Terminal 2 — start frontend
cd electron-app
npm start
```

- [ ] **Step 2: Send a message that triggers rich Markdown response**

In the chat input, type: `请用markdown格式介绍一下Python的主要特性，包括代码示例、列表和引用。`

- [ ] **Step 3: Verify the response renders correctly**

Check that the assistant's response shows:
- [ ] Headings have larger font and bottom border
- [ ] Bold text is brighter
- [ ] Code blocks have dark background with monospace font
- [ ] Inline code has red accent background
- [ ] Lists have proper indentation
- [ ] Blockquotes have left accent border
- [ ] Links are blue
- [ ] User messages still display as plain text
- [ ] Streaming cursor animation still works
- [ ] Right-click "保存为笔记" still works (saves raw Markdown)
