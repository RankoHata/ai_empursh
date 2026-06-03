import React, { useState, useEffect, useMemo } from 'react';
import NoteCard from './NoteCard';

export default function NotesPanel({ notes, onGetNotes, onSearch, onDelete, onExport }) {
  const [query, setQuery] = useState('');
  const [tagFilter, setTagFilter] = useState('');
  const [selectedIds, setSelectedIds] = useState(new Set());

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

  const toggleSelect = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedIds.size === notes.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(notes.map((n) => n.id)));
    }
  };

  const handleExport = () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    onExport(ids);
    setSelectedIds(new Set());
  };

  // Collect all unique tags for the filter dropdown
  const allTags = useMemo(() => {
    const tagSet = new Set();
    notes.forEach((n) => (n.tags || []).forEach((t) => tagSet.add(t)));
    return Array.from(tagSet).sort();
  }, [notes]);

  return (
    <div className="notes-panel">
      <div className="notes-toolbar">
        <input
          type="text"
          className="notes-search"
          placeholder="搜索笔记..."
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
      </div>

      <div className="notes-list">
        {notes.length === 0 && (
          <div className="notes-empty">暂无笔记。在聊天中右键消息可保存为笔记。</div>
        )}
        {notes.map((note) => (
          <NoteCard
            key={note.id}
            note={note}
            selected={selectedIds.has(note.id)}
            onSelect={toggleSelect}
            onDelete={onDelete}
          />
        ))}
      </div>

      {notes.length > 0 && (
        <div className="notes-footer">
          <label className="select-all">
            <input type="checkbox" checked={selectedIds.size === notes.length} onChange={toggleAll} />
            <span>全选 ({selectedIds.size}/{notes.length})</span>
          </label>
          <button
            className="btn-export"
            disabled={selectedIds.size === 0}
            onClick={handleExport}
          >
            📥 导出选中为 Markdown
          </button>
        </div>
      )}
    </div>
  );
}
