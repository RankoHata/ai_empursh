import React, { useState, useEffect, useCallback } from 'react';

export default function SettingsPanel({
  config, onUpdateConfig, onLoad,
  compactMode, onToggleCompact,
  personalities, currentPersonalityId, onSetPersonality, onSaveCustom,
}) {
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [modelName, setModelName] = useState('');
  const [maxTokens, setMaxTokens] = useState(4096);
  const [saved, setSaved] = useState(false);

  // Custom personality editor
  const [editModal, setEditModal] = useState(false);
  const [editName, setEditName] = useState('');
  const [editDesc, setEditDesc] = useState('');
  const [editPrompt, setEditPrompt] = useState('');

  const customP = (personalities || []).find(p => p.id === 'custom');

  const openEditor = useCallback(() => {
    if (customP) {
      setEditName(customP.name || '自定义助手');
      setEditDesc(customP.description || '');
      setEditPrompt(customP.system_prompt || '');
    }
    setEditModal(true);
  }, [customP]);

  const saveCustom = useCallback(() => {
    if (onSaveCustom) {
      onSaveCustom({
        name: editName,
        description: editDesc,
        system_prompt: editPrompt,
      });
    }
    setEditModal(false);
  }, [editName, editDesc, editPrompt, onSaveCustom]);

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
        <h3>助理人格</h3>
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
                <div className="personality-info">
                  <div className="personality-name-row">
                    <span className="personality-name">{p.name}</span>
                    {p.id === 'custom' && (
                      <button
                        className="personality-edit-btn"
                        onClick={(e) => { e.preventDefault(); e.stopPropagation(); openEditor(); }}
                      >✏️ 编辑</button>
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

      {/* Custom personality editor modal */}
      {editModal && (
        <div className="modal-overlay" onClick={() => setEditModal(false)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()} style={{ width: 560, maxHeight: '80vh' }}>
            <h3>✏️ 编辑自定义人格</h3>

            <label className="setting-label">
              名称
              <input className="setting-input" value={editName}
                onChange={(e) => setEditName(e.target.value)} />
            </label>
            <label className="setting-label">
              描述
              <input className="setting-input" value={editDesc}
                onChange={(e) => setEditDesc(e.target.value)} />
            </label>
            <label className="setting-label">
              系统 Prompt
              <textarea
                className="setting-textarea"
                value={editPrompt}
                onChange={(e) => setEditPrompt(e.target.value)}
                rows={14}
                placeholder="写给模型的系统 prompt..."
              />
            </label>
            <p className="setting-hint">
              提示：在 prompt 中描述助理的名字、性格、语气、行为准则。支持 Markdown。
            </p>

            <div className="modal-buttons">
              <button className="btn-send" onClick={saveCustom}>保存</button>
              <button className="btn-modal-cancel" onClick={() => setEditModal(false)}>取消</button>
            </div>
          </div>
        </div>
      )}

      <div className="settings-section">
        <h3>模型配置</h3>
        <label className="setting-label">
          API 地址
          <input className="setting-input" type="text" value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)} />
        </label>
        <label className="setting-label">
          API Key {config?.model?.api_key && <span className="setting-hint">(当前: {config.model.api_key})</span>}
          <input className="setting-input" type="password" value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="留空则不修改" />
        </label>
        <label className="setting-label">
          模型名称
          <input className="setting-input" type="text" value={modelName}
            onChange={(e) => setModelName(e.target.value)} />
        </label>
        <label className="setting-label">
          Max Tokens
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
