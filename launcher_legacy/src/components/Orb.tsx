import React from 'react';

interface FluidOrbProps {
  status: string;
}

const FluidOrb: React.FC<FluidOrbProps> = ({ status }) => {
  const getColors = () => {
    switch (status) {
      case 'listening': return ['#22d3ee', '#8b5cf6'];
      case 'thinking': return ['#8b5cf6', '#ef4444'];
      case 'speaking': return ['#ef4444', '#f59e0b'];
      default: return ['#8b5cf6', '#4c1d95'];
    }
  };

  const [color1, color2] = getColors();

  return (
    <div className="fluid-orb-container floating">
      <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="orbGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={color1} />
            <stop offset="100%" stopColor={color2} />
          </linearGradient>
          <filter id="goo">
            <feGaussianBlur in="SourceGraphic" stdDeviation="10" result="blur" />
            <feColorMatrix in="blur" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 18 -7" result="goo" />
            <feBlend in="SourceGraphic" in2="goo" />
          </filter>
        </defs>
        
        <g filter="url(#goo)">
          <circle cx="100" cy="100" r="60" fill="url(#orbGradient)">
            <animate attributeName="r" values="58;62;58" dur="3s" repeatCount="indefinite" />
          </circle>
          
          {/* Organic blob layers */}
          <path fill="url(#orbGradient)" opacity="0.6">
            <animate attributeName="d" 
              dur="10s" 
              repeatCount="indefinite"
              values="
                M100,40 C140,40 160,70 160,100 C160,130 140,160 100,160 C60,160 40,130 40,100 C40,70 60,40 100,40;
                M100,50 C130,50 150,80 150,110 C150,140 120,150 100,150 C80,150 50,140 50,110 C50,80 70,50 100,50;
                M100,40 C140,40 160,70 160,100 C160,130 140,160 100,160 C60,160 40,130 40,100 C40,70 60,40 100,40
              " 
            />
          </path>

          <path fill="url(#orbGradient)" opacity="0.4">
            <animate attributeName="d" 
              dur="7s" 
              repeatCount="indefinite"
              values="
                M100,60 C120,60 140,80 140,100 C140,120 120,140 100,140 C80,140 60,120 60,100 C60,80 80,60 100,60;
                M100,45 C150,45 155,90 155,100 C155,110 150,155 100,155 C50,155 45,110 45,100 C45,90 50,45 100,45;
                M100,60 C120,60 140,80 140,100 C140,120 120,140 100,140 C80,140 60,120 60,100 C60,80 80,60 100,60
              " 
            />
          </path>
        </g>
        
        {/* Core glow */}
        <circle cx="100" cy="100" r="20" fill="white" opacity="0.1">
          <animate attributeName="opacity" values="0.1;0.3;0.1" dur="2s" repeatCount="indefinite" />
        </circle>
      </svg>
    </div>
  );
};

export default FluidOrb;
