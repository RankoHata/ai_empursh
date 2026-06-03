import React from 'react';

const AVATAR_EMOJI = {
  idle: '😊',
  listening: '👂',
  thinking: '🤔',
  speaking: '🗣️',
};

const AVATAR_LABELS = {
  idle: '待机',
  listening: '倾听中',
  thinking: '思考中',
  speaking: '说话中',
};

export default function AvatarStatus({ state = 'idle' }) {
  return (
    <div className={`avatar-status avatar-${state}`}>
      <span className="avatar-emoji">{AVATAR_EMOJI[state] || '😊'}</span>
      <span className="avatar-label">{AVATAR_LABELS[state] || ''}</span>
    </div>
  );
}
