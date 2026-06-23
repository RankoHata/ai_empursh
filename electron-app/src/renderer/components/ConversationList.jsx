import React, { useState, useRef } from 'react';

export default function ConversationList({ conversations, activeId, onNew, onSelect, onDelete, onRename, collapsed = false, onToggleCollapse = () => {}, onOpenSettings = () => {} }) {
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

  if (collapsed) {
    return (
      <div className="conv-list collapsed">
        <button className="conv-collapse-toggle" onClick={onToggleCollapse} title="展开侧边栏">
          ▶
        </button>
        <button className="conv-icon-btn" onClick={onNew} title="新对话">+</button>
        <div className="conv-collapsed-spacer" />
        <button className="conv-icon-btn" onClick={onOpenSettings} title="设置">⚙️</button>
      </div>
    );
  }

  return (
    <div className="conv-list">
      <div className="conv-header">
        <span className="conv-header-title">对话</span>
        <div className="conv-header-actions">
          <button className="conv-icon-btn" onClick={onNew} title="新对话">+</button>
          <button className="conv-collapse-toggle" onClick={onToggleCollapse} title="收起侧边栏">◀</button>
        </div>
      </div>
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
      <div className="conv-footer">
        <span className="conv-version">v1.0</span>
        <button className="conv-icon-btn" onClick={onOpenSettings} title="设置">⚙️</button>
      </div>
    </div>
  );
}
