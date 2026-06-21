import React, { useState, useEffect, useMemo } from 'react';
import NoteCard from './NoteCard';

export default function SecretNotesPanel({ notes, onGetNotes, onSearch, onDelete, onNewNote }) {
  const [query, setQuery] = useState('');
  const [tagFilter, setTagFilter] = useState('');

  // Load notes on mount
  useEffect(() => {
    onGetNotes();
  }, [onGetNotes]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (query.trim() || tagFilter.trim()) {
        onSearch(query, tagFilter ? [tagFilter] : []);
      } else {
        onGetNotes();
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query, tagFilter, onSearch, onGetNotes]);

  // Collect all unique tags for the filter dropdown
  const allTags = useMemo(() => {
    const tagSet = new Set();
    notes.forEach((n) => (n.tags || []).forEach((t) => tagSet.add(t)));
    return Array.from(tagSet).sort();
  }, [notes]);

  return (
    <div className="notes-panel secret-panel">
      {/* Warning banner */}
      <div className="secret-warning-banner secret-warning-top">
        🔒 秘密空间 — 内容不会发送给 AI 模型，仅存储在本地
      </div>

      <div className="notes-toolbar">
        <input
          type="text"
          className="notes-search secret-search"
          placeholder="搜索秘密笔记..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          className="notes-tag-filter"
          value={tagFilter}
          onChange={(e) => setTagFilter(e.target.value)}
        >
          <option value="">全部标签</option>
          {allTags.map((tag) => (
            <option key={tag} value={tag}>#{tag}</option>
          ))}
        </select>
        {onNewNote && (
          <button className="btn-new-note btn-new-secret-note" onClick={onNewNote}>
            + 新建秘密笔记
          </button>
        )}
      </div>

      <div className="notes-list">
        {notes.length === 0 && (
          <div className="notes-empty">
            暂无秘密笔记。点击"+ 新建秘密笔记"添加，或在聊天中让 AI 帮你检索秘密空间。
          </div>
        )}
        {notes.map((note) => (
          <NoteCard
            key={note.id}
            note={note}
            selected={false}
            onSelect={() => {}}
            onDelete={onDelete}
            secretMode={true}
          />
        ))}
      </div>
    </div>
  );
}
