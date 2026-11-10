import React from 'react';
import { createRoot } from 'react-dom/client';
import BodyViewer from './BodyViewer.jsx';
import './styles.css';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BodyViewer />
  </React.StrictMode>
);
