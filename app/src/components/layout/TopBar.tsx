import { useAppStore } from '@/store/useAppStore';
import {
  Activity,
  RefreshCw,
  Download,
  Maximize2,
  Cpu,
  Leaf,
  Wifi,
  WifiOff,
  Clock,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';

export default function TopBar() {
  const {
    mode,
    runLabel,
    autoRefresh,
    aiStatus,
    latestSnapshot,
    isRefreshing,
    setMode,
    setRunLabel,
    setAutoRefresh,
    refreshData,
  } = useAppStore();

  const isConnected = latestSnapshot !== null;

  const aiStatusConfig = {
    enabled: { label: 'AI 已启用', color: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30' },
    degraded: { label: 'AI 降级', color: 'text-amber-400 bg-amber-400/10 border-amber-400/30' },
    disconnected: { label: 'AI 未连接', color: 'text-red-400 bg-red-400/10 border-red-400/30' },
  };

  const aiConfig = aiStatusConfig[aiStatus];

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-16 border-b border-slate-800/60 bg-[#020c1b]/90 backdrop-blur-xl">
      <div className="flex items-center justify-between h-full px-6">
        {/* Left: Logo & System Info */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
              <Leaf className="w-4 h-4 text-white" />
            </div>
            <span className="text-lg font-bold text-slate-100 tracking-tight">
              EcoSentinel
            </span>
          </div>

          <div className="h-6 w-px bg-slate-700 mx-2" />

          {/* Mode Toggle */}
          <div className="flex items-center bg-slate-800/60 rounded-lg p-0.5 border border-slate-700/50">
            <button
              onClick={() => setMode('real-time')}
              className={`px-3 py-1 text-xs font-mono rounded-md transition-all ${
                mode === 'real-time'
                  ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <span className="flex items-center gap-1.5">
                <Cpu className="w-3 h-3" />
                实时硬件
              </span>
            </button>
            <button
              onClick={() => setMode('simulation')}
              className={`px-3 py-1 text-xs font-mono rounded-md transition-all ${
                mode === 'simulation'
                  ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              仿真模式
            </button>
          </div>

          {/* Run Label Toggle */}
          <div className="flex items-center bg-slate-800/60 rounded-lg p-0.5 border border-slate-700/50">
            <button
              onClick={() => setRunLabel('baseline')}
              className={`px-3 py-1 text-xs font-mono rounded-md transition-all ${
                runLabel === 'baseline'
                  ? 'bg-slate-600 text-slate-200'
                  : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              baseline
            </button>
            <button
              onClick={() => setRunLabel('saving')}
              className={`px-3 py-1 text-xs font-mono rounded-md transition-all ${
                runLabel === 'saving'
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              saving
            </button>
          </div>
        </div>

        {/* Center: Connection & Time */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            {isConnected ? (
              <Wifi className="w-4 h-4 text-emerald-400" />
            ) : (
              <WifiOff className="w-4 h-4 text-red-400" />
            )}
            <span className="text-xs font-mono text-slate-400">
              {isConnected ? '系统在线' : '离线'}
            </span>
          </div>

          {latestSnapshot && (
            <div className="flex items-center gap-2">
              <Clock className="w-3.5 h-3.5 text-slate-500" />
              <span className="text-xs font-mono text-slate-500">
                {new Date(latestSnapshot.timestamp).toLocaleTimeString('zh-CN')}
              </span>
            </div>
          )}

          <div className={`px-2.5 py-1 text-xs font-mono rounded-md border ${aiConfig.color}`}>
            {aiConfig.label}
          </div>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-2">
          {/* Auto Refresh Toggle */}
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded-lg border transition-all ${
              autoRefresh
                ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30'
                : 'bg-slate-800/50 text-slate-500 border-slate-700/50 hover:text-slate-300'
            }`}
          >
            <Activity className="w-3 h-3" />
            自动刷新
          </button>

          {/* Refresh Once */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => refreshData()}
            disabled={isRefreshing}
            className="bg-slate-800/50 border-slate-700/50 text-slate-400 hover:text-slate-100 hover:bg-slate-700/50"
          >
            <motion.div
              animate={isRefreshing ? { rotate: 360 } : {}}
              transition={{ duration: 1, repeat: isRefreshing ? Infinity : 0, ease: 'linear' }}
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </motion.div>
          </Button>

          {/* Export */}
          <Button
            variant="outline"
            size="sm"
            className="bg-slate-800/50 border-slate-700/50 text-slate-400 hover:text-slate-100 hover:bg-slate-700/50"
          >
            <Download className="w-3.5 h-3.5 mr-1" />
            导出
          </Button>

          {/* Fullscreen */}
          <Button
            variant="outline"
            size="sm"
            className="bg-slate-800/50 border-slate-700/50 text-slate-400 hover:text-slate-100 hover:bg-slate-700/50"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>
    </header>
  );
}
