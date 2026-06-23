import { useState, useCallback, useRef } from 'react';

/**
 * useSettings — 配置 + 人格 + 显示 + TTS + 紧凑模式
 *
 * Provides settingsRefs to useChat for cross-hook communication
 * (emotionFollow, ttsEnabled, emotionTimer).
 */
export default function useSettings(send) {
  // ── Config ──
  const [config, setConfig] = useState(null);

  // ── Personality ──
  const [personalities, setPersonalities] = useState([]);
  const [groupedPersonalities, setGroupedPersonalities] = useState([]);
  const [currentPersonalityId, setCurrentPersonalityId] = useState(null);

  // ── Display / User ──
  const [emotionFollowEnabled, setEmotionFollowEnabled] = useState(() =>
    localStorage.getItem('emotionFollowEnabled') !== 'false'
  );
  const [userName, setUserName] = useState('');
  const [compactMode, setCompactMode] = useState(() =>
    localStorage.getItem('compactMode') === '1'
  );
  const [wallpaper, setWallpaper] = useState(() =>
    localStorage.getItem('wallpaper') || ''
  );
  const [ttsEnabled, setTtsEnabled] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  // ── Refs for useChat ──
  const emotionTimerRef = useRef(null);
  const ttsEnabledRef = useRef(ttsEnabled);
  ttsEnabledRef.current = ttsEnabled;
  const emotionFollowRef = useRef(emotionFollowEnabled);
  emotionFollowRef.current = emotionFollowEnabled;

  /** Shared refs object passed to useChat for cross-hook communication. */
  const settingsRefs = { emotionFollowRef, ttsEnabledRef, emotionTimerRef };

  // ── Handlers ──

  const handleGetConfig = useCallback(() => send('get_config', {}), [send]);
  const handleUpdateConfig = useCallback((updates) => send('update_config', { updates }), [send]);
  const handleUserNameChange = useCallback((name) => {
    setUserName(name);
    send('update_config', { updates: { user: { name } } });
  }, [send]);

  const handleToggleTts = useCallback((on, stopAudio) => {
    setTtsEnabled(on);
    if (!on && stopAudio) stopAudio();
    send('tts_enabled', { enabled: on });
  }, [send]);

  // ── WS message handler ──

  const onMessage = useCallback((type, payload) => {
    switch (type) {
      case 'config':
        setConfig(payload);
        if (payload.user?.name !== undefined) setUserName(payload.user.name);
        return true;
      case 'config_updated':
        return true;
      case 'personalities_list':
      case 'personalities_reseeded':
        setPersonalities(payload.personalities || []);
        setGroupedPersonalities(payload.grouped || []);
        if (payload.current) setCurrentPersonalityId(payload.current);
        return true;
      case 'personality_set':
        setCurrentPersonalityId(payload.id);
        return true;
      case 'personality_created':
      case 'personality_updated':
      case 'personality_deleted':
        send('get_personalities', {});
        return true;
      default:
        return false;
    }
  }, [send]);

  return {
    // state
    config,
    personalities,
    groupedPersonalities,
    currentPersonalityId,
    emotionFollowEnabled,
    userName,
    compactMode,
    wallpaper,
    ttsEnabled,
    settingsOpen,
    setSettingsOpen,
    setEmotionFollowEnabled,
    setCompactMode,
    setWallpaper,
    // refs for useChat
    settingsRefs,
    emotionTimerRef,
    // handlers
    handleGetConfig,
    handleUpdateConfig,
    handleUserNameChange,
    handleToggleTts,
    // message handler
    onMessage,
  };
}
