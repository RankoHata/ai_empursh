import React, { useState, useRef } from 'react';

export default function ConversationList({ conversations, activeId, onNew, onSelect, onDelete, onRename }) {
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const editRef = useRef(null);

  const startEdit = (e, conv) => {
    e.stopPropagation();
    setEditingId(conv.id);
    setEditTitle(conv.title || '');
    setTimeout(() => editRef.current?.select(), 50);
  };

  const saveEdit = () => {
    if (editingId && editTitle.trim()) {
      onRename && onRename(editingId, editTitle.trim());
    }
    setEditingId(null);
  };

  const cancelEdit = () => setEditingId(null);

  return (
    <div className="conv-list">
      <button className="conv-new-btn" onClick={onNew}>+ 新对话</button>
      <div className="conv-items">
        {conversations.map(c => (
          <div
            key={c.id}
            className={`conv-item ${c.id === activeId ? 'active' : ''}`}
            onClick={() => onSelect(c.id)}
          >
            {editingId === c.id ? (
              <input
                ref={editRef}
                className="conv-edit-input"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                onBlur={saveEdit}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') saveEdit();
                  if (e.key === 'Escape') cancelEdit();
                }}
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <div
                className="conv-item-title"
                onDoubleClick={(e) => startEdit(e, c)}
                title="双击修改标题"
              >{c.title || '新对话'}</div>
            )}
            <div className="conv-item-meta">
              <span>{c.created_at?.slice(0, 10)}</span>
            </div>
            <button
              className="conv-delete-btn"
              onClick={(e) => { e.stopPropagation(); onDelete(c.id); }}
              title="删除"
            >🗑</button>
          </div>
        ))}
        {conversations.length === 0 && (
          <div className="conv-empty">暂无对话</div>
        )}
      </div>
    </div>
  );
}
