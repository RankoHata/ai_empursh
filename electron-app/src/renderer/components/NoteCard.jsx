import React from 'react';

export default function NoteCard({ note, selected, onSelect, onDelete, secretMode = false }) {
  const preview =
    note.content.length > 120 ? note.content.slice(0, 120) + '...' : note.content;

  const timeStr = note.created_at
    ? new Date(note.created_at).toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
    : '';

  return (
    <div className={`note-card ${selected ? 'selected' : ''} ${secretMode ? 'note-card-secret' : ''}`}>
      <input
        type="checkbox"
        className="note-checkbox"
        checked={selected}
        onChange={() => onSelect(note.id)}
      />
      <div className="note-body">
        {note.title && <div className="note-title">{note.title}</div>}
        <div className="note-content">{preview}</div>
        <div className="note-meta">
          {note.tags && note.tags.map((tag) => (
            <span key={tag} className={`note-tag ${secretMode ? 'note-tag-secret' : ''}`}>#{tag}</span>
          ))}
          {timeStr && <span className="note-time">{timeStr}</span>}
        </div>
      </div>
      <button
        className="note-delete-btn"
        onClick={() => onDelete(note.id)}
        title="删除笔记"
      >
        🗑️
      </button>
    </div>
  );
}
