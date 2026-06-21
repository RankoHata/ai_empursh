import React, { useState } from 'react';

/**
 * Reusable modal for creating a new note — shared by public NotesPanel and secret SecretNotesPanel.
 *
 * Props:
 *   onSave(content, tags, title)  — called when user confirms
 *   onCancel()                    — called when user dismisses
 *   secretMode (bool)             — if true, use red-tinted styling and warning
 */
export default function NewNoteModal({ onSave, onCancel, secretMode = false }) {
  const [content, setContent] = useState('');
  const [tags, setTags] = useState('');
  const [title, setTitle] = useState('');

  const handleSave = () => {
    const trimmed = content.trim();
    if (!trimmed) return;
    const tagList = tags
      .split(/[\s,]+/)
      .map((t) => t.trim())
      .filter(Boolean);
    onSave(trimmed, tagList, title.trim());
  };

  const handleKeyDown = (e) => {
    // Ctrl+Enter to save
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSave();
    }
  };

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div
        className={`modal-box new-note-modal ${secretMode ? 'new-note-modal-secret' : ''}`}
        onClick={(e) => e.stopPropagation()}
      >
        <h3>
          {secretMode ? '🔒 ' : '📝 '}
          {secretMode ? '新建秘密笔记' : '新建笔记'}
        </h3>

        {secretMode && (
          <div className="secret-warning-banner">
            🔒 秘密空间 — 此内容不会发送给 AI 模型，仅存储在本地
          </div>
        )}

        <label className="modal-label">标题（可选）</label>
        <input
          className="modal-input"
          type="text"
          placeholder="笔记标题"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={handleKeyDown}
          autoFocus
        />

        <label className="modal-label">内容</label>
        <textarea
          className="modal-textarea"
          placeholder={secretMode ? '输入秘密笔记内容...' : '输入笔记内容，支持 Markdown 格式...'}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={6}
        />

        <label className="modal-label">标签（逗号或空格分隔）</label>
        <input
          className="modal-input"
          type="text"
          placeholder="如: 工作, python, 周报"
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); }}
        />

        <div className="modal-buttons">
          <button
            className={`btn-send ${secretMode ? 'btn-send-secret' : ''}`}
            onClick={handleSave}
            disabled={!content.trim()}
          >
            保存
          </button>
          <button className="btn-modal-cancel" onClick={onCancel}>
            取消
          </button>
        </div>
        <div className="modal-hint">Ctrl+Enter 快速保存</div>
      </div>
    </div>
  );
}
