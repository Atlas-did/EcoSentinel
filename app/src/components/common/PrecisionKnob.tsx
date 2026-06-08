import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, useMotionValue, useTransform } from 'framer-motion';

interface PrecisionKnobProps {
  value: number;
  min?: number;
  max?: number;
  onChange: (v: number) => void;
  label?: string;
  unit?: string;
  size?: number;
}

export default function PrecisionKnob({
  value,
  min = 15,
  max = 40,
  onChange,
  label = 'Target Temp',
  unit = '°C',
  size = 200,
}: PrecisionKnobProps) {
  const knobRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const rotation = useMotionValue(0);
  const rotate = useTransform(rotation, (v) => `${v}deg`);
  const lastAngleRef = useRef<number | null>(null);

  const percent = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));

  const handlePointerMove = useCallback(
    (e: PointerEvent) => {
      if (!isDragging || !knobRef.current) return;
      const rect = knobRef.current.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      const angle = Math.atan2(e.clientY - centerY, e.clientX - centerX) * (180 / Math.PI);

      if (lastAngleRef.current !== null) {
        let delta = angle - lastAngleRef.current;
        if (delta > 180) delta -= 360;
        if (delta < -180) delta += 360;
        const newVal = Math.max(min, Math.min(max, value + delta * 0.05));
        onChange(newVal);
      }
      lastAngleRef.current = angle;
      rotation.set(angle + 90);
    },
    [isDragging, value, min, max, onChange, rotation]
  );

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('pointermove', handlePointerMove);
      window.addEventListener('pointerup', () => {
        setIsDragging(false);
        lastAngleRef.current = null;
      });
      return () => {
        window.removeEventListener('pointermove', handlePointerMove);
        window.removeEventListener('pointerup', () => {
          setIsDragging(false);
          lastAngleRef.current = null;
        });
      };
    }
  }, [isDragging, handlePointerMove]);

  const circumference = 2 * Math.PI * ((size * 0.42));
  const strokeDashoffset = circumference - (percent / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-4">
      {label && (
        <div className="text-xs font-mono text-cyan-400 tracking-widest uppercase">
          {label}
        </div>
      )}
      <div
        ref={knobRef}
        className={`relative rounded-full bg-slate-900 border-[6px] border-slate-800 shadow-[0_0_40px_rgba(8,112,184,0.15)] flex items-center justify-center cursor-grab active:cursor-grabbing ${isDragging ? 'scale-[1.02]' : ''} transition-transform`}
        style={{ width: size, height: size }}
        onPointerDown={() => setIsDragging(true)}
      >
        {/* Progress Ring SVG */}
        <svg
          className="absolute inset-0 w-full h-full -rotate-90 pointer-events-none"
          style={{ padding: 4 }}
        >
          <circle
            cx="50%"
            cy="50%"
            r="42%"
            fill="none"
            stroke="#1e293b"
            strokeWidth="10"
          />
          <motion.circle
            cx="50%"
            cy="50%"
            r="42%"
            fill="none"
            stroke="#0ea5e9"
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={circumference}
            animate={{ strokeDashoffset }}
            transition={{ duration: 0.15 }}
          />
        </svg>

        {/* Rotating Handle Indicator */}
        <motion.div
          style={{ rotate }}
          className="absolute inset-0 pointer-events-none"
        >
          <div
            className="w-3 h-3 bg-white rounded-full absolute shadow-[0_0_10px_rgba(255,255,255,0.8)]"
            style={{
              top: '10%',
              left: '50%',
              transform: 'translateX(-50%)',
            }}
          />
        </motion.div>

        {/* Center Value */}
        <div className="text-center z-10 pointer-events-none">
          <div className="text-4xl font-bold text-slate-100 font-mono">
            {value.toFixed(1)}
            <span className="text-lg text-slate-400 ml-0.5">{unit}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
