import React, { useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface TranscriptProps {
  userInput: string;
  fridayOutput: string;
}

const Transcript: React.FC<TranscriptProps> = ({ userInput, fridayOutput }) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [userInput, fridayOutput]);

  return (
    <div className="absolute top-0 left-0 w-full h-full pointer-events-none p-8 flex flex-col justify-between overflow-hidden">
      {/* HUD Corner Elements */}
      <div className="flex justify-between items-start">
        <div className="glass-panel p-4 w-64">
          <div className="text-[10px] text-[var(--neon-violet)] opacity-70 mb-2 font-mono tracking-widest">NEURAL_SYNC_LINK</div>
          <div className="flex flex-col gap-1">
            <div className="h-0.5 bg-white/5 w-full overflow-hidden">
              <motion.div 
                className="h-full bg-[var(--neon-violet)]"
                animate={{ width: ["10%", "90%", "40%"] }}
                transition={{ duration: 5, repeat: Infinity }}
              />
            </div>
            <div className="text-[8px] font-mono flex justify-between opacity-50">
              <span>BW: 4.8GBPS</span>
              <span>SYNC: 0.99</span>
            </div>
          </div>
        </div>

        <div className="text-right">
          <div className="text-5xl font-black tracking-tighter italic text-white" style={{ textShadow: '0 0 20px rgba(139, 92, 246, 0.4)' }}>F.R.I.D.A.Y.</div>
          <div className="text-[10px] font-mono text-[var(--neon-violet)] tracking-[0.3em] opacity-60">EVOLUTION_v2.6.0</div>
        </div>
      </div>

      {/* Main Dialogue Console */}
      <div className="flex flex-col items-center gap-6 z-10">
        <AnimatePresence>
          {userInput && (
            <motion.div 
              initial={{ opacity: 0, y: 20, filter: 'blur(10px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
              className="max-w-2xl"
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="w-1.5 h-1.5 bg-[var(--neon-cyan)] rounded-full animate-pulse" />
                <span className="text-[9px] font-mono font-bold text-[var(--neon-cyan)] tracking-widest">VOICE_INPUT_CAPTURE</span>
              </div>
              <div className="glass-panel p-4 border-[var(--neon-cyan)]/20">
                <p className="text-white text-lg font-light tracking-wide">{userInput}</p>
              </div>
            </motion.div>
          )}

          {fridayOutput && (
            <motion.div 
              initial={{ opacity: 0, y: 20, filter: 'blur(10px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
              className="max-w-3xl"
            >
              <div className="flex items-center gap-2 mb-1 justify-end">
                <span className="text-[9px] font-mono font-bold text-[var(--neon-violet)] tracking-widest">INTELLIGENCE_REASONING_STREAM</span>
                <span className="w-1.5 h-1.5 bg-[var(--neon-violet)] rounded-full animate-pulse" />
              </div>
              <div className="glass-panel p-6 border-[var(--neon-violet)]/20">
                <p className="text-white text-xl font-medium leading-relaxed italic" style={{ textShadow: '0 0 10px rgba(255, 255, 255, 0.1)' }}>
                  "{fridayOutput}"
                </p>
                <div className="mt-4 flex gap-1">
                  {[...Array(20)].map((_, i) => (
                    <motion.div 
                      key={i} 
                      className="w-1 h-0.5 bg-[var(--neon-violet)] opacity-20"
                      animate={{ opacity: [0.1, 0.4, 0.1] }}
                      transition={{ delay: i * 0.05, repeat: Infinity }}
                    />
                  ))}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Bottom HUD - Data Stream */}
      <div className="flex justify-between items-end">
        <div className="font-mono text-[8px] text-[var(--neon-violet)] opacity-40 leading-tight tracking-wider">
          SCANNING_CORE_OS... [READY]<br/>
          ENCRYPTING_SECURE_VAULT... [ACTIVE]<br/>
          ORACLE_NODE: ONLINE<br/>
          HIVE_MIND_LINK: STABLE
        </div>
        
        <div className="glass-panel p-3 flex gap-4 items-center">
           <div className="text-[10px] font-mono tracking-widest text-[var(--neon-violet)]">ARC_REACTOR_LINK</div>
           <div className="flex gap-1">
             {[...Array(10)].map((_, i) => (
               <div key={i} className="w-1.5 h-3 bg-[var(--neon-violet)]" style={{ opacity: i < 8 ? 0.8 : 0.1 }} />
             ))}
           </div>
           <div className="text-[10px] font-mono font-bold text-white">92.4%</div>
        </div>
      </div>
    </div>
  );
};

export default Transcript;
