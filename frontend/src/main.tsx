import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';
import { applyDomPatch } from './utils/domPatch';

// Apply defensive patch against browser translation extensions (e.g. Google Translate)
applyDomPatch();

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
