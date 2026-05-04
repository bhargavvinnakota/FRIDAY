import React, { useState, useEffect } from 'react';
import Orb from './components/Orb';
import TelemetryHUD from './components/TelemetryHUD';
import { motion, AnimatePresence } from 'framer-motion';

declare global {
  interface Window {
    electron: {
      onFridayStatus: (callback: (status: string) => void) => void;
      onFridayInput: (callback: (text: string) => void) => void;
      onFridayOutput: (callback: (text: string) => void) => void;
    };
  }
}

const App: React.FC = () => {
  const [status, setStatus] = useState<string>('idle');
  const [userInput, setUserInput] = useState<string>('');
  const [fridayOutput, setFridayOutput] = useState<string>('');

  useEffect(() => {
    if (window.electron) {
      window.electron.onFridayStatus((newStatus) => {
        setStatus(newStatus);
        if (newStatus === 'listening') {
          setUserInput('');
          setFridayOutput('');
        }
      });

      window.electron.onFridayInput((text) => {
        if (!text) return;
        setUserInput(text);
        setStatus('thinking');
      });

      window.electron.onFridayOutput((text) => {
        if (!text) return;
        setFridayOutput((prev) => prev + text);
        setStatus('speaking');
      });
    }
  }, []);

  return (
    <>
      <div className="scanline" />
      <TelemetryHUD />
      
      <div className="floating-orb">
        <Orb status={status} />
      </div>

      <div className="transcript-area pointer-events-none">
        <AnimatePresence mode="wait">
          {userInput && (
            <motion.div 
              key={`user-${userInput.slice(0, 10)}-${Date.now()}`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="user-capture font-mono tracking-widest"
            >
              DETECTED_INPUT: {userInput}
            </motion.div>
          )}
          {fridayOutput && (
            <motion.div 
              key={`friday-${fridayOutput.slice(0, 10)}-${Date.now()}`}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="friday-stream"
            >
              {fridayOutput}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      
      <div className="visualizer-container">
        {[...Array(60)].map((_, i) => (
          <motion.div 
            key={`bar-${i}`} 
            className="visualizer-bar" 
            animate={{ 
              height: (status === 'speaking' || status === 'listening') 
                ? [2, Math.random() * 30 + 5, 2] 
                : 2 
            }}
            transition={{ duration: 0.5, repeat: Infinity, ease: "easeInOut" }}
          />
        ))}
      </div>
    </>
  );
};

export default App;
