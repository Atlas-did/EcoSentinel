import { motion } from 'framer-motion';
import { useState } from 'react';

interface ControlLeverProps {
  label: string;
  color: 'amber' | 'blue';
  initialOn?: boolean;
  onToggle?: (isOn: boolean) => void;
}

export default function ControlLever({ label, color, initialOn = false, onToggle }: ControlLeverProps) {
  const [isOn, setIsOn] = useState(initialOn);

  const handleToggle = () => {
    const newState = !isOn;
    setIsOn(newState);
    onToggle?.(newState);
  };

  const trackColor = color === 'amber' ? 'bg-amber-900/20' : 'bg-cyan-900/20';
  const ledColor = color === 'amber' ? 'bg-amber-500 shadow-amber-500/50' : 'bg-cyan-500 shadow-cyan-500/50';
  const leverGradient =
    color === 'amber'
      ? 'bg-gradient-to-b from-amber-600 to-amber-800'
      : 'bg-gradient-to-b from-slate-500 to-slate-700';

  return (
    <div className="flex flex-col items-center gap-3 p-4 bg-slate-800/40 rounded-xl border border-slate-700/40">
      <motion.div
        className={`w-2.5 h-2.5 rounded-full ${isOn ? ledColor : 'bg-slate-700'}`}
        animate={{
          opacity: isOn ? 1 : 0.3,
          boxShadow: isOn ? `0 0 10px currentColor` : 'none',
        }}
        transition={{ duration: 0.2 }}
      />
      <div
        className={`relative w-12 h-36 rounded-full ${trackColor} shadow-inner flex justify-center cursor-pointer border border-slate-700/40`}
        onClick={handleToggle}
      >
        <motion.div
          className={`absolute w-10 h-20 rounded-lg shadow-xl border border-slate-600 ${leverGradient}`}
          initial={false}
          animate={{
            y: isOn ? 6 : 80,
            boxShadow: isOn
              ? '0px 10px 25px rgba(0,0,0,0.6)'
              : '0px -3px 10px rgba(0,0,0,0.3)',
          }}
          whileTap={{ scale: 0.95 }}
          transition={{ type: 'spring', stiffness: 500, damping: 30 }}
        >
          {/* Lever grip texture */}
          <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 flex flex-col gap-1 items-center">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="w-6 h-0.5 bg-slate-900/30 rounded-full" />
            ))}
          </div>
        </motion.div>
      </div>
      <span className="text-[10px] font-bold text-slate-400 tracking-widest uppercase text-center w-20 leading-tight">
        {label}
      </span>
    </div>
  );
}
