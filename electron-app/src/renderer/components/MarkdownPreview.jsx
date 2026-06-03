import React, { useState } from 'react';

export default function MarkdownPreview({ content, suggestedFilename, onSave, onCancel }) {
  const [filename, setFilename] = useState(suggestedFilename || 'export.md');

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-box markdown-modal" onClick={(e) => e.stopPropagation()}>
        <h3>📄 生成结果预览</h3>
        <div className="markdown-preview-content">
          <pre>{content}</pre>
        </div>
        <div className="markdown-save-row">
          <input
            className="modal-input"
            type="text"
            value={filename}
            onChange={(e) => setFilename(e.target.value)}
            placeholder="文件名.md"
          />
          <button className="btn-send" onClick={() => onSave(content, filename)}>
            💾 保存
          </button>
          <button className="btn-modal-cancel" onClick={onCancel}>
            取消
          </button>
        </div>
      </div>
    </div>
  );
}
