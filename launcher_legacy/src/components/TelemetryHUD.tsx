import React, { useState, useEffect } from 'react';

const TelemetryHUD: React.FC = () => {
  const [cpu, setCpu] = useState(0);
  const [ram, setRam] = useState(0);
  const [net, setNet] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setCpu(Math.floor(Math.random() * 20) + 5);
      setRam(Math.floor(Math.random() * 10) + 40);
      setNet(Math.floor(Math.random() * 1000));
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <>
      <div className="hud-data hud-top-left">
        CORE_STATE: OPTIMAL<br />
        V_LINK: ACTIVE<br />
        SYNC: {new Date().getSeconds()}%
      </div>
      <div className="hud-data hud-top-right">
        PROCESSOR_LOAD: {cpu}%<br />
        MEMORY_USAGE: {ram}%<br />
        LATENCY: 12ms
      </div>
      <div className="hud-data hud-bottom-left">
        UPLINK: {net} KB/S<br />
        DOWNLINK: {Math.floor(net * 1.5)} KB/S<br />
        LOC: HYDERABAD_HUB
      </div>
      <div className="hud-data hud-bottom-right">
        VERSION: 2.6.0-EVO<br />
        ENGINE: GEMINI_FLASH<br />
        IDENTITY: FRIDAY
      </div>
    </>
  );
};

export default TelemetryHUD;
