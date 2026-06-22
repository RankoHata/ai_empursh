import React, { useState, useEffect, useCallback } from 'react';

export default function SettingsPanel({
  config, onUpdateConfig, onLoad,
  compactMode, onToggleCompact,
  personalities, currentPersonalityId, onSetPersonality,
  onCreatePersonality, onUpdatePersonality, onDeletePersonality,
  wallpaper, onSetWallpaper,
  grouped,
  userName, onUserNameChange,
  emotionFollowEnabled, onSetEmotionFollow,
  ttsEnabled, onToggleTts,
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

  // Local user name state for debounced save
  const [localUserName, setLocalUserName] = useState(userName || '');

  useEffect(() => {
    setLocalUserName(userName || '');
  }, [userName]);

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
    const updates = { model: {} };
    if (baseUrl.trim()) updates.model.base_url = baseUrl.trim();
    if (modelName.trim()) updates.model.model_name = modelName.trim();
    updates.model.max_tokens = parseInt(maxTokens, 10) || 4096;
    if (apiKey.trim()) updates.model.api_key = apiKey.trim();
    onUpdateConfig(updates);
    setSaved(true);
    setApiKey('');
    setTimeout(() => setSaved(false), 2000);
  };

  const handleUserNameBlur = () => {
    if (onUserNameChange) {
      onUserNameChange(localUserName);
    }
  };

  const handlePickWallpaper = useCallback(() => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.onchange = (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onloadend = () => {
        if (onSetWallpaper) onSetWallpaper(reader.result);
      };
      reader.readAsDataURL(file);
    };
    input.click();
  }, [onSetWallpaper]);

  const handleRemoveWallpaper = useCallback(() => {
    if (onSetWallpaper) onSetWallpaper('');
  }, [onSetWallpaper]);

  return (
    <div className="settings-panel">

      {/* ═══ 助理人格 — 下拉选择器 ═══ */}
      <div className="settings-section">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <h3 style={{ margin: 0 }}>助理人格</h3>
          <button className="personality-new-btn" onClick={openNew}>+ 新建</button>
        </div>
        {grouped && grouped.length > 0 ? (
          <select
            className="personality-select"
            value={currentPersonalityId || ''}
            onChange={(e) => {
              const pid = Number(e.target.value);
              if (pid && onSetPersonality) onSetPersonality(pid);
            }}
          >
            {grouped.map((group) =>
              group.is_single ? (
                <option key={group.id} value={group.id}>
                  {group.name}
                </option>
              ) : (
                <optgroup key={group.id} label={group.name}>
                  {/* Include the root personality itself as an option */}
                  {!group.version_tag && (
                    <option value={group.id}>{group.name}</option>
                  )}
                  {group.versions.map((v) => (
                    <option key={v.id} value={v.id}>
                      {group.name} · {v.label}
                    </option>
                  ))}
                </optgroup>
              )
            )}
          </select>
        ) : (
          <p className="setting-hint">加载中...</p>
        )}
        {/* Inline edit / delete for currently selected personality */}
        {currentPersonalityId && personalities && (
          <div className="personality-actions" style={{ marginTop: 6, display: 'flex', gap: 6 }}>
            {(() => {
              const cur = personalities.find(p => p.id === currentPersonalityId);
              if (!cur) return null;
              return (
                <>
                  <button className="personality-edit-btn" onClick={() => openEdit(cur)}>✏️ 编辑</button>
                  {!cur.is_seed && (
                    <button
                      className="personality-delete-btn"
                      onClick={() => onDeletePersonality && onDeletePersonality(cur.id)}
                    >🗑 删除</button>
                  )}
                </>
              );
            })()}
          </div>
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

      {/* ═══ 模型配置 ═══ */}
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

      {/* ═══ 显示 ═══ */}
      <div className="settings-section">
        <h3>显示</h3>
        <label className="setting-label">聊天壁纸</label>
        <div
          className="wallpaper-preview"
          style={wallpaper ? { backgroundImage: `url(${wallpaper})` } : {}}
        >
          {!wallpaper && '未设置壁纸'}
        </div>
        <div className="wallpaper-actions">
          <button className="btn-wallpaper" onClick={handlePickWallpaper}>
            {wallpaper ? '🖼 更换图片' : '🖼 选择图片'}
          </button>
          {wallpaper && (
            <button className="btn-wallpaper btn-wallpaper-danger" onClick={handleRemoveWallpaper}>
              ✕ 移除
            </button>
          )}
        </div>
        <div className="toggle-row" style={{ marginTop: 12 }}>
          <span>紧凑模式<span className="toggle-desc">减少空白行，信息密度更高</span></span>
          <input
            type="checkbox"
            className="toggle"
            checked={compactMode || false}
            onChange={(e) => onToggleCompact && onToggleCompact(e.target.checked)}
          />
        </div>
      </div>

      {/* ═══ 用户信息 ═══ */}
      <div className="settings-section">
        <h3>用户信息</h3>
        <label className="setting-label">
          你的称呼
          <span className="setting-hint">（用于人格 System Prompt 模板变量 {'{{'} user_name {'}}'}）</span>
          <input
            className="setting-input"
            type="text"
            value={localUserName}
            onChange={(e) => setLocalUserName(e.target.value)}
            onBlur={handleUserNameBlur}
            placeholder="输入你的名字或昵称..."
          />
        </label>
        <p className="setting-hint" style={{ marginTop: 2 }}>留空则使用默认值 "用户"</p>
      </div>

      {/* ═══ Avatar 情绪跟随 ═══ */}
      <div className="settings-section">
        <h3>Avatar 情绪跟随</h3>
        <div className="toggle-row">
          <div className="toggle-label">
            <span>Live2D 情绪跟随</span>
            <div className="toggle-desc">AI 根据对话内容生成情绪，驱动 Avatar 表情动画</div>
          </div>
          <input
            type="checkbox"
            className="toggle"
            checked={emotionFollowEnabled}
            onChange={(e) => onSetEmotionFollow && onSetEmotionFollow(e.target.checked)}
          />
        </div>
        <p className="setting-hint" style={{ marginTop: 4 }}>
          关闭后 Avatar 始终保持默认待机状态
        </p>
      </div>

      {/* ═══ 语音配置 ═══ */}
      <div className="settings-section">
        <h3>语音配置</h3>
        <div className="toggle-row">
          <div className="toggle-label">
            <span>🗣️ 语音朗读</span>
            <div className="toggle-desc">AI 回复通过语音播报</div>
          </div>
          <input
            type="checkbox"
            className="toggle"
            checked={ttsEnabled}
            onChange={(e) => onToggleTts && onToggleTts(e.target.checked)}
          />
        </div>
        <p className="setting-hint" style={{ marginTop: 8 }}>STT: faster-whisper base · 引擎: {config?.voice?.tts_engine || 'edge-tts'}</p>
      </div>

      <button className="btn-send" onClick={handleSave}>
        {saved ? '✅ 已保存' : '💾 保存设置'}
      </button>
    </div>
  );
}
