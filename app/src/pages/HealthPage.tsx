import { useAppStore } from '@/store/useAppStore';
import { motion } from 'framer-motion';
import {
  HeartPulse,
  Wifi,
  WifiOff,
  Clock,
  Activity,
  Shield,
  AlertTriangle,
  CheckCircle,
  RotateCcw,
  Usb,
  Cpu,
  Zap,
  Thermometer,
  Droplets,
  Sun,
  Wind,
} from 'lucide-react';
import StatusBadge from '@/components/common/StatusBadge';

const sensorIcons: Record<string, typeof Thermometer> = {
  temperature: Thermometer,
  humidity: Droplets,
  illuminance: Sun,
  eco2: Wind,
  power: Zap,
  solar: Sun,
};

export default function HealthPage() {
  const { healthStatus, resilienceEvents, latestSnapshot } = useAppStore();

  if (!healthStatus) {
    return (
      <div className="min-h-screen bg-[#020c1b] pt-16 flex items-center justify-center">
        <div className="text-slate-500 font-mono text-sm">加载中...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#020c1b] pt-16 pb-6">
      <div className="px-6 py-6 space-y-6 max-w-6xl">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 className="text-xl font-bold text-slate-100 font-mono tracking-tight flex items-center gap-2">
            <HeartPulse className="w-5 h-5 text-emerald-400" />
            系统健康
          </h1>
          <p className="text-xs text-slate-500 font-mono mt-1">
            System Health - 自愈监控与事件审计
          </p>
        </motion.div>

        {/* Status Overview */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="grid grid-cols-4 gap-4"
        >
          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40">
            <div className="flex items-center gap-2 mb-2">
              <Usb className="w-4 h-4 text-slate-400" />
              <span className="text-xs font-mono text-slate-500">串口连接</span>
            </div>
            <div className="flex items-center gap-2">
              {healthStatus.serial_connected ? (
                <>
                  <Wifi className="w-4 h-4 text-emerald-400" />
                  <span className="text-sm font-mono text-emerald-400">已连接</span>
                </>
              ) : (
                <>
                  <WifiOff className="w-4 h-4 text-red-400" />
                  <span className="text-sm font-mono text-red-400">已断开</span>
                </>
              )}
            </div>
          </div>

          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40">
            <div className="flex items-center gap-2 mb-2">
              <Activity className="w-4 h-4 text-slate-400" />
              <span className="text-xs font-mono text-slate-500">采样频率</span>
            </div>
            <span className="text-sm font-mono text-cyan-400">{healthStatus.sampling_rate_hz} Hz</span>
          </div>

          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="w-4 h-4 text-slate-400" />
              <span className="text-xs font-mono text-slate-500">最后心跳</span>
            </div>
            <span className="text-sm font-mono text-slate-300">
              {new Date(healthStatus.last_heartbeat).toLocaleTimeString('zh-CN')}
            </span>
          </div>

          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40">
            <div className="flex items-center gap-2 mb-2">
              <RotateCcw className="w-4 h-4 text-slate-400" />
              <span className="text-xs font-mono text-slate-500">重试次数</span>
            </div>
            <span className={`text-sm font-mono ${healthStatus.retry_count > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
              {healthStatus.retry_count}
            </span>
          </div>
        </motion.div>

        <div className="grid grid-cols-12 gap-6">
          {/* Sensor Status Grid */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="col-span-5 bg-slate-900/60 border border-slate-800 rounded-2xl p-5"
          >
            <h3 className="text-slate-400 text-xs font-mono uppercase tracking-widest mb-4 flex items-center gap-2">
              <Cpu className="w-3.5 h-3.5 text-cyan-400" />
              传感器状态
            </h3>
            <div className="space-y-2">
              {Object.entries(healthStatus.sensors_online).map(([name, online]) => {
                const Icon = sensorIcons[name] || Activity;
                return (
                  <div
                    key={name}
                    className="flex items-center justify-between p-2.5 rounded-lg bg-slate-800/30 border border-slate-700/20"
                  >
                    <div className="flex items-center gap-2">
                      <Icon className="w-3.5 h-3.5 text-slate-500" />
                      <span className="text-xs font-mono text-slate-400 uppercase">{name}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {online ? (
                        <>
                          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                          <span className="text-[10px] font-mono text-emerald-400">ONLINE</span>
                        </>
                      ) : (
                        <>
                          <div className="w-1.5 h-1.5 rounded-full bg-red-400" />
                          <span className="text-[10px] font-mono text-red-400">OFFLINE</span>
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Self-healing toggle */}
            <div className="mt-4 pt-4 border-t border-slate-700/30">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono text-slate-400 flex items-center gap-1.5">
                  <Shield className="w-3.5 h-3.5" />
                  自愈机制
                </span>
                <StatusBadge
                  label={healthStatus.self_healing_enabled ? '已启用' : '已禁用'}
                  status={healthStatus.self_healing_enabled ? 'online' : 'offline'}
                />
              </div>
              <div className="flex items-center justify-between mt-2">
                <span className="text-xs font-mono text-slate-400">Stale 检测</span>
                <span className={`text-xs font-mono ${healthStatus.stale_detected ? 'text-red-400' : 'text-emerald-400'}`}>
                  {healthStatus.stale_detected ? '检测到' : '正常'}
                </span>
              </div>
            </div>
          </motion.div>

          {/* Resilience Timeline */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="col-span-7 bg-slate-900/60 border border-slate-800 rounded-2xl p-5"
          >
            <h3 className="text-slate-400 text-xs font-mono uppercase tracking-widest mb-4 flex items-center gap-2">
              <RotateCcw className="w-3.5 h-3.5 text-emerald-400" />
              自愈事件时间轴
            </h3>
            <div className="space-y-0">
              {resilienceEvents.map((event, i) => (
                <div key={event.incident_id} className="relative flex gap-4">
                  {/* Timeline line */}
                  {i < resilienceEvents.length - 1 && (
                    <div className="absolute left-[11px] top-6 bottom-0 w-px bg-slate-700/30" />
                  )}

                  {/* Timeline dot */}
                  <div className="flex-shrink-0 mt-1">
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center ${
                      event.success
                        ? 'bg-emerald-500/10 border border-emerald-500/20'
                        : 'bg-red-500/10 border border-red-500/20'
                    }`}>
                      {event.success ? (
                        <CheckCircle className="w-3 h-3 text-emerald-400" />
                      ) : (
                        <AlertTriangle className="w-3 h-3 text-red-400" />
                      )}
                    </div>
                  </div>

                  {/* Event content */}
                  <div className="flex-1 pb-5">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-mono text-slate-300">{event.action}</span>
                      <span className="text-[10px] font-mono text-slate-600">
                        {new Date(event.timestamp).toLocaleString('zh-CN')}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                        event.success
                          ? 'bg-emerald-500/10 text-emerald-400'
                          : 'bg-red-500/10 text-red-400'
                      }`}>
                        {event.success ? '成功' : '失败'}
                      </span>
                      <span className="text-[10px] font-mono text-slate-500">{event.state}</span>
                    </div>
                    {event.reason && (
                      <p className="text-[10px] font-mono text-slate-500 mt-1">{event.reason}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        </div>

        {/* Bottom: Safe Mode Status */}
        {latestSnapshot?.safe_mode && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-amber-500/5 border border-amber-500/20 rounded-2xl p-4 flex items-center gap-3"
          >
            <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0" />
            <div>
              <div className="text-xs font-mono text-amber-400">安全模式已激活</div>
              <p className="text-[10px] font-mono text-amber-400/70 mt-0.5">
                原因: {latestSnapshot.safe_reason || '系统检测到异常，已进入安全运行模式'}
              </p>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}
