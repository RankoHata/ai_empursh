import React, { useState, useEffect } from 'react';

export default function SettingsPanel({ config, onUpdateConfig, onLoad, compactMode, onToggleCompact }) {
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [modelName, setModelName] = useState('');
  const [maxTokens, setMaxTokens] = useState(4096);
  const [saved, setSaved] = useState(false);

  useEffect(() => { onLoad(); }, []); // eslint-disable-line

  useEffect(() => {
    if (config) {
      setBaseUrl(config.model?.base_url || '');
      setModelName(config.model?.model_name || '');
      setMaxTokens(config.model?.max_tokens || 4096);
      setApiKey(''); // always start empty for security
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
        <p className="setting-hint">STT 模型: faster-whisper base · TTS: zh-CN-XiaoxiaoNeural</p>
      </div>

      <button className="btn-send" onClick={handleSave}>
        {saved ? '✅ 已保存' : '💾 保存设置'}
      </button>
    </div>
  );
}
