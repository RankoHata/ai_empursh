import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './App.css';
import './components/Chat.css';
import './components/Notes.css';
import './components/Settings.css';
import './components/Navigation.css';
import './components/Modals.css';
import './components/Avatar.css';

// Live2D pet mode: transparent window
if (window.location.search.includes('mode=live2d')) {
  document.documentElement.classList.add('live2d-pet');
}

const root = createRoot(document.getElementById('root'));
root.render(<App />);
