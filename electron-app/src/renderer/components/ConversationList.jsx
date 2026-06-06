import React from 'react';

export default function ConversationList({ conversations, activeId, onNew, onSelect, onDelete }) {
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
            <div className="conv-item-title">{c.title || '新对话'}</div>
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
