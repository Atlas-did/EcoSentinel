import { useAppStore } from '@/store/useAppStore';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, AlertCircle, AlertTriangle, Info, X } from 'lucide-react';

const iconMap = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const colorMap = {
  success: 'text-emerald-400 border-emerald-500/20 bg-emerald-500/5',
  error: 'text-red-400 border-red-500/20 bg-red-500/5',
  warning: 'text-amber-400 border-amber-500/20 bg-amber-500/5',
  info: 'text-cyan-400 border-cyan-500/20 bg-cyan-500/5',
};

export default function ToastContainer() {
  const { toasts, removeToast } = useAppStore();

  return (
    <div className="fixed bottom-6 right-6 z-[100] flex flex-col gap-2">
      <AnimatePresence>
        {toasts.map((toast) => {
          const Icon = iconMap[toast.type];
          return (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, x: 50, scale: 0.9 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 50, scale: 0.9 }}
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg border ${colorMap[toast.type]} backdrop-blur-sm min-w-[280px]`}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span className="text-xs font-mono flex-1">{toast.message}</span>
              <button
                onClick={() => removeToast(toast.id)}
                className="text-slate-500 hover:text-slate-300 transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
