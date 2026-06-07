import React, { useState, useEffect, useCallback } from 'react';

export default function SettingsPanel({
  config, onUpdateConfig, onLoad,
  compactMode, onToggleCompact,
  personalities, currentPersonalityId, onSetPersonality,
  onCreatePersonality, onUpdatePersonality, onDeletePersonality,
}) {
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [modelName, setModelName] = useState('');
  const [maxTokens, setMaxTokens] = useState(4096);
  const [saved, setSaved] = useState(false);

  // Personality editor modal
  const [editModal, setEditModal] = useState(false);
  const [editId, setEditId] = useState(null);
  const [editName, setEditName] = useState('');
  const [editDesc, setEditDesc] = useState('');
  const [editPrompt, setEditPrompt] = useState('');
  const [isNew, setIsNew] = useState(false);

  const openNew = useCallback(() => {
    setEditId(null);
    setEditName('');
    setEditDesc('');
    setEditPrompt('你是用户的私人 AI 桌面助理。使用中文回复。');
    setIsNew(true);
    setEditModal(true);
  }, []);

  const openEdit = useCallback((p) => {
    setEditId(p.id);
    setEditName(p.name || '');
    setEditDesc(p.description || '');
    setEditPrompt(p.system_prompt || '');
    setIsNew(false);
    setEditModal(true);
  }, []);

  const savePersonality = useCallback(() => {
    const data = { name: editName, description: editDesc, system_prompt: editPrompt };
    if (isNew) {
      onCreatePersonality && onCreatePersonality(data);
    } else {
      onUpdatePersonality && onUpdatePersonality(editId, data);
    }
    setEditModal(false);
  }, [editId, editName, editDesc, editPrompt, isNew, onCreatePersonality, onUpdatePersonality]);

  useEffect(() => { onLoad(); }, []); // eslint-disable-line

  useEffect(() => {
    if (config) {
      setBaseUrl(config.model?.base_url || '');
      setModelName(config.model?.model_name || '');
      setMaxTokens(config.model?.max_tokens || 4096);
      setApiKey('');
    }
  }, [config]);

  const handleSave = () => {
    const updates = {
      model: {
        base_url: baseUrl,
        model_name: modelName,
        max_tokens: parseInt(maxTokens, 10),
      },
    };
    if (apiKey.trim()) {
      updates.model.api_key = apiKey.trim();
    }
    onUpdateConfig(updates);
    setSaved(true);
    setApiKey('');
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="settings-panel">
      <h2>⚙️ 设置</h2>

      <div className="settings-section">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <h3 style={{ margin: 0 }}>助理人格</h3>
          <button className="personality-new-btn" onClick={openNew}>+ 新建</button>
        </div>
        {personalities && personalities.length > 0 ? (
          <div className="personality-list">
            {personalities.map((p) => (
              <label
                key={p.id}
                className={`personality-option ${p.id === currentPersonalityId ? 'active' : ''}`}
              >
                <input
                  type="radio"
                  name="personality"
                  checked={p.id === currentPersonalityId}
                  onChange={() => onSetPersonality && onSetPersonality(p.id)}
                />
                <div className="personality-info" style={{ flex: 1 }}>
                  <div className="personality-name-row">
                    <span className="personality-name">{p.name}</span>
                    {p.is_seed ? <span className="personality-badge">预设</span> : null}
                    <button
                      className="personality-edit-btn"
                      onClick={(e) => { e.preventDefault(); e.stopPropagation(); openEdit(p); }}
                    >✏️</button>
                    {!p.is_seed && (
                      <button
                        className="personality-delete-btn"
                        onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDeletePersonality && onDeletePersonality(p.id); }}
                      >🗑</button>
                    )}
                  </div>
                  <span className="personality-desc">{p.description}</span>
                </div>
              </label>
            ))}
          </div>
        ) : (
          <p className="setting-hint">加载中...</p>
        )}
      </div>

      {/* Personality editor modal */}
      {editModal && (
        <div className="modal-overlay" onClick={() => setEditModal(false)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()} style={{ width: 560, maxHeight: '80vh' }}>
            <h3>{isNew ? '➕ 新建人格' : '✏️ 编辑人格'}</h3>

            <label className="setting-label">名称
              <input className="setting-input" value={editName}
                onChange={(e) => setEditName(e.target.value)} />
            </label>
            <label className="setting-label">描述
              <input className="setting-input" value={editDesc}
                onChange={(e) => setEditDesc(e.target.value)} />
            </label>
            <label className="setting-label">系统 Prompt
              <textarea className="setting-textarea" value={editPrompt}
                onChange={(e) => setEditPrompt(e.target.value)} rows={14} />
            </label>

            <div className="modal-buttons">
              <button className="btn-send" onClick={savePersonality}>保存</button>
              <button className="btn-modal-cancel" onClick={() => setEditModal(false)}>取消</button>
            </div>
          </div>
        </div>
      )}

      <div className="settings-section">
        <h3>模型配置</h3>
        <label className="setting-label">API 地址
          <input className="setting-input" type="text" value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)} />
        </label>
        <label className="setting-label">
          API Key {config?.model?.api_key && <span className="setting-hint">(当前: {config.model.api_key})</span>}
          <input className="setting-input" type="password" value={apiKey}
            onChange={(e) => setApiKey(e.target.value)} placeholder="留空则不修改" />
        </label>
        <label className="setting-label">模型名称
          <input className="setting-input" type="text" value={modelName}
            onChange={(e) => setModelName(e.target.value)} />
        </label>
        <label className="setting-label">Max Tokens
          <input className="setting-input" type="number" value={maxTokens}
            onChange={(e) => setMaxTokens(e.target.value)} />
        </label>
      </div>

      <div className="settings-section">
        <h3>显示</h3>
        <label className="setting-label" style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
          <input type="checkbox" checked={compactMode || false}
            onChange={(e) => onToggleCompact && onToggleCompact(e.target.checked)} />
          紧凑模式（减少空白行，信息密度更高）
        </label>
      </div>

      <div className="settings-section">
        <h3>语音配置</h3>
        <p className="setting-hint">STT 模型: faster-whisper base · TTS: {config?.voice?.tts_engine || 'edge-tts'}</p>
      </div>

      <button className="btn-send" onClick={handleSave}>
        {saved ? '✅ 已保存' : '💾 保存设置'}
      </button>
    </div>
  );
}
