import { useEffect } from 'react';
import { useAppStore, startAutoRefresh, stopAutoRefresh } from '@/store/useAppStore';
import { motion } from 'framer-motion';
import {
  Thermometer,
  Droplets,
  Sun,
  Wind,
  Zap,
  Battery,
  Activity,
  HardDrive,
  Shield,
  Brain,
} from 'lucide-react';
import HardwarePort from '@/components/common/HardwarePort';
import ControlLever from '@/components/common/ControlLever';
import PrecisionKnob from '@/components/common/PrecisionKnob';
import MetricCard from '@/components/common/MetricCard';
import SensorChart from '@/components/charts/SensorChart';
import TimeRangeSelector from '@/components/common/TimeRangeSelector';
import StatusBadge from '@/components/common/StatusBadge';
import { TARGET_TEMP_C, isSnapshotAlert } from '@/lib/metrics';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export default function DashboardPage() {
  const {
    latestSnapshot,
    chartData,
    aiCandidates,
    resilienceEvents,
    energySummary,
    healthStatus,
    selectedTimeRange,
    setTimeRange,
    acceptCandidate,
    rejectCandidate,
  } = useAppStore();

  useEffect(() => {
    startAutoRefresh();
    return () => stopAutoRefresh();
  }, []);

  const targetTemp = TARGET_TEMP_C;

  return (
    <div className="min-h-screen bg-[#020c1b] pt-16 pb-6 pr-80">
      {/* Main Content Area */}
      <div className="px-6 py-6 space-y-6">
        {/* Hardware Header Row */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="grid grid-cols-3 gap-4 h-28"
        >
          {/* Sensor Ports */}
          <div className="col-span-1 bg-slate-900/50 border border-slate-800 rounded-2xl p-4 flex items-center justify-around relative overflow-hidden">
            <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-30">
              <motion.path
                d="M 30 50 Q 80 20 130 50 T 230 50"
                fill="none"
                stroke="#64ffda"
                strokeWidth="1.5"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
              />
            </svg>
            <HardwarePort label="TMP-01" active={true} />
            <HardwarePort label="HUM-02" active={true} />
            <HardwarePort label="LUX-03" active={true} />
            <HardwarePort label="ECO2" active={true} />
          </div>

          {/* System Status */}
          <div className="col-span-1 bg-slate-900/50 border border-slate-800 rounded-2xl flex items-center justify-center p-6">
            <div className="text-center space-y-2">
              <div className="flex items-center justify-center gap-2">
                <motion.div
                  className="w-2 h-2 rounded-full bg-emerald-400"
                  animate={{ opacity: [1, 0.3, 1] }}
                  transition={{ duration: 2, repeat: Infinity }}
                />
                <h2 className="text-lg font-bold text-slate-100 font-mono tracking-wider">
                  SYSTEM ONLINE
                </h2>
              </div>
              <div className="flex items-center justify-center gap-3">
                <StatusBadge label="传感器正常" status="online" pulse />
                <StatusBadge label="AI运行中" status="processing" pulse />
              </div>
            </div>
          </div>

          {/* Power Ports */}
          <div className="col-span-1 bg-slate-900/50 border border-slate-800 rounded-2xl p-4 flex items-center justify-around">
            <HardwarePort label="AC-IN" active={true} subLabel="220V" />
            <HardwarePort label="PV-ARR" active={true} subLabel="48V" />
            <HardwarePort label="BAT" active={true} subLabel={`${latestSnapshot?.soc_percent?.toFixed(0) ?? '--'}%`} />
          </div>
        </motion.section>

        {/* KPI Cards Grid */}
        <section className="grid grid-cols-6 gap-4">
          <MetricCard
            title="室内温度"
            value={latestSnapshot?.temperature ?? '--'}
            unit="°C"
            icon={<Thermometer className="w-5 h-5" />}
            status={isSnapshotAlert('temperature', latestSnapshot?.temperature) ? 'warning' : 'normal'}
            subtitle={latestSnapshot ? `目标: ${targetTemp}°C` : undefined}
            trend={latestSnapshot && latestSnapshot.temperature! > targetTemp ? 'up' : 'down'}
            delay={0}
          />
          <MetricCard
            title="相对湿度"
            value={latestSnapshot?.humidity ?? '--'}
            unit="%"
            icon={<Droplets className="w-5 h-5" />}
            status="normal"
            delay={0.05}
          />
          <MetricCard
            title="光照强度"
            value={latestSnapshot?.illuminance ?? '--'}
            unit="lx"
            icon={<Sun className="w-5 h-5" />}
            status="normal"
            delay={0.1}
          />
          <MetricCard
            title="eCO2"
            value={latestSnapshot?.eco2 ?? '--'}
            unit="ppm"
            icon={<Wind className="w-5 h-5" />}
            status={isSnapshotAlert('eco2', latestSnapshot?.eco2) ? 'warning' : 'normal'}
            delay={0.15}
          />
          <MetricCard
            title="当前功率"
            value={latestSnapshot?.power_w ?? '--'}
            unit="W"
            icon={<Zap className="w-5 h-5" />}
            status="success"
            subtitle={energySummary ? `节能 ${energySummary.saving_rate.toFixed(1)}%` : undefined}
            delay={0.2}
          />
          <MetricCard
            title="SOC"
            value={latestSnapshot?.soc_percent ?? '--'}
            unit="%"
            icon={<Battery className="w-5 h-5" />}
            status={isSnapshotAlert('soc_percent', latestSnapshot?.soc_percent) ? 'warning' : 'success'}
            delay={0.25}
          />
        </section>

        {/* Main Content: Chart + Controls */}
        <section className="grid grid-cols-12 gap-4">
          {/* Sensor Chart */}
          <div className="col-span-8 bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-slate-400 text-xs font-mono uppercase tracking-widest">
                Environmental History ({selectedTimeRange === '5m' ? '5分钟' : selectedTimeRange === '1h' ? '1小时' : '24小时'})
              </h3>
              <TimeRangeSelector value={selectedTimeRange} onChange={setTimeRange} />
            </div>
            <SensorChart
              data={chartData}
              showTemp
              showHumidity
              showPower
              showSolar
              height={340}
            />
          </div>

          {/* Lever Controls */}
          <div className="col-span-4 bg-slate-900/60 border border-slate-800 rounded-2xl p-5 flex flex-col items-center justify-center gap-4 shadow-xl">
            <h3 className="text-slate-400 text-xs font-mono uppercase tracking-widest w-full text-left">
              Manual Overrides
            </h3>
            <div className="flex gap-6">
              <ControlLever label="Hydraulic" color="amber" />
              <ControlLever label="Thermal" color="blue" initialOn />
            </div>
            <div className="w-full pt-4 border-t border-slate-700/30">
              <div className="flex items-center justify-between text-xs font-mono text-slate-500 mb-2">
                <span className="flex items-center gap-1.5">
                  <HardDrive className="w-3 h-3" />
                  系统模式
                </span>
                <span className="text-cyan-400">AUTO</span>
              </div>
              <div className="flex items-center justify-between text-xs font-mono text-slate-500">
                <span className="flex items-center gap-1.5">
                  <Shield className="w-3 h-3" />
                  安全锁
                </span>
                <span className="text-emerald-400">ENGAGED</span>
              </div>
            </div>
          </div>
        </section>

        {/* AI Decision + Resilience */}
        <section className="grid grid-cols-12 gap-4">
          {/* AI Candidates */}
          <div className="col-span-6 bg-slate-900/60 border border-slate-800 rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-slate-400 text-xs font-mono uppercase tracking-widest flex items-center gap-2">
                <Brain className="w-3.5 h-3.5 text-cyan-400" />
                AI 候选池
              </h3>
              <span className="text-[10px] font-mono text-slate-500">
                {aiCandidates.filter(c => c.accepted).length} 已接受 / {aiCandidates.filter(c => c.rejected).length} 已拒绝
              </span>
            </div>
            <div className="space-y-3">
              {aiCandidates.map((candidate) => (
                <motion.div
                  key={candidate.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  className={`p-3 rounded-lg border ${
                    candidate.accepted
                      ? 'border-emerald-500/20 bg-emerald-500/5'
                      : candidate.rejected
                      ? 'border-red-500/20 bg-red-500/5'
                      : 'border-slate-700/40 bg-slate-800/30'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-200">
                        {candidate.name}
                      </span>
                      <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                        candidate.source === 'cloud'
                          ? 'bg-cyan-500/10 text-cyan-400'
                          : 'bg-amber-500/10 text-amber-400'
                      }`}>
                        {candidate.source}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      {!candidate.accepted && !candidate.rejected && (
                        <>
                          <button
                            onClick={() => acceptCandidate(candidate.id)}
                            className="px-2 py-0.5 text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded hover:bg-emerald-500/20 transition-colors"
                          >
                            接受
                          </button>
                          <button
                            onClick={() => rejectCandidate(candidate.id, '用户手动拒绝')}
                            className="px-2 py-0.5 text-[10px] font-mono bg-red-500/10 text-red-400 border border-red-500/20 rounded hover:bg-red-500/20 transition-colors"
                          >
                            拒绝
                          </button>
                        </>
                      )}
                      {candidate.accepted && (
                        <span className="text-[10px] font-mono text-emerald-400 flex items-center gap-1">
                          <Activity className="w-3 h-3" />
                          已采纳·未下发
                        </span>
                      )}
                      {candidate.rejected && (
                        <span className="text-[10px] font-mono text-red-400">
                          已拒绝
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-4 text-[10px] font-mono text-slate-500">
                    <span>评分: {candidate.score?.toFixed(2)}</span>
                    <span>延迟: {candidate.latency_ms}ms</span>
                    {candidate.risk && <span>风险: {candidate.risk}</span>}
                  </div>
                  {candidate.rejectedReason && (
                    <p className="text-[10px] font-mono text-red-400/80 mt-1.5">
                      原因: {candidate.rejectedReason}
                    </p>
                  )}
                </motion.div>
              ))}
            </div>
          </div>

          {/* Resilience Events */}
          <div className="col-span-6 bg-slate-900/60 border border-slate-800 rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-slate-400 text-xs font-mono uppercase tracking-widest flex items-center gap-2">
                <Shield className="w-3.5 h-3.5 text-emerald-400" />
                自愈事件摘要
              </h3>
              <StatusBadge label={healthStatus?.self_healing_enabled ? '已启用' : '已禁用'} status="online" />
            </div>
            <div className="space-y-2">
              {resilienceEvents.map((event, i) => (
                <motion.div
                  key={event.incident_id}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="flex items-center gap-3 p-2.5 rounded-lg bg-slate-800/30 border border-slate-700/30"
                >
                  <div className={`w-2 h-2 rounded-full ${event.success ? 'bg-emerald-400' : 'bg-red-400'}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono text-slate-300">{event.action}</span>
                      <span className="text-[9px] font-mono text-slate-500">
                        {new Date(event.timestamp).toLocaleTimeString('zh-CN')}
                      </span>
                    </div>
                    <p className="text-[10px] font-mono text-slate-500 truncate">
                      {event.reason || event.state}
                    </p>
                  </div>
                </motion.div>
              ))}
            </div>
            {/* Health Status Grid */}
            {healthStatus && (
              <div className="mt-4 pt-4 border-t border-slate-700/30 grid grid-cols-2 gap-2">
                <div className="text-[10px] font-mono text-slate-500">
                  串口: <span className="text-emerald-400">{healthStatus.serial_connected ? '已连接' : '断开'}</span>
                </div>
                <div className="text-[10px] font-mono text-slate-500">
                  采样率: <span className="text-cyan-400">{healthStatus.sampling_rate_hz}Hz</span>
                </div>
                <div className="text-[10px] font-mono text-slate-500">
                  重试: <span className={healthStatus.retry_count > 0 ? 'text-amber-400' : 'text-emerald-400'}>{healthStatus.retry_count}</span>
                </div>
                <div className="text-[10px] font-mono text-slate-500">
                  Stale: <span className={healthStatus.stale_detected ? 'text-red-400' : 'text-emerald-400'}>{healthStatus.stale_detected ? '检测到' : '正常'}</span>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Bottom Evidence Tabs */}
        <section className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5">
          <Tabs defaultValue="logs" className="w-full">
            <TabsList className="bg-slate-800/40 border border-slate-700/30 mb-4">
              <TabsTrigger value="logs" className="text-xs font-mono data-[state=active]:bg-cyan-500/10 data-[state=active]:text-cyan-400">
                日志证据
              </TabsTrigger>
              <TabsTrigger value="energy" className="text-xs font-mono data-[state=active]:bg-cyan-500/10 data-[state=active]:text-cyan-400">
                能耗分析
              </TabsTrigger>
              <TabsTrigger value="simulation" className="text-xs font-mono data-[state=active]:bg-cyan-500/10 data-[state=active]:text-cyan-400">
                仿真预览
              </TabsTrigger>
            </TabsList>

            <TabsContent value="logs" className="mt-0">
              <div className="bg-black rounded-lg p-4 font-mono text-xs space-y-1 max-h-48 overflow-y-auto border border-slate-800">
                <p className="text-slate-600">// System Logs initialized...</p>
                <p className="text-emerald-500/80">[10:42:01] Fan array speed set to 2400 RPM.</p>
                <p className="text-cyan-500/80">[10:42:15] Thermal lock engaged. Target: 24.5°C.</p>
                <p className="text-amber-500/80">[10:43:00] Humidity drop detected in Zone C.</p>
                <p className="text-emerald-500/80">[10:43:30] AI candidate accepted: 温度微调策略</p>
                <p className="text-slate-500/80">[10:44:00] Sampling cycle complete. 6 sensors read.</p>
                <p className="text-cyan-500/80">[10:44:15] Energy saving rate: 29.9%</p>
                <p className="text-emerald-500/80">[10:45:00] Self-healing check: all systems nominal.</p>
              </div>
            </TabsContent>

            <TabsContent value="energy" className="mt-0">
              {energySummary && (
                <div className="grid grid-cols-4 gap-4">
                  <div className="p-4 rounded-lg bg-slate-800/30 border border-slate-700/30 text-center">
                    <div className="text-xs font-mono text-slate-500 mb-1">基线能耗</div>
                    <div className="text-xl font-bold text-slate-200 font-mono">{energySummary.baseline_kwh.toFixed(1)} <span className="text-xs text-slate-500">kWh</span></div>
                  </div>
                  <div className="p-4 rounded-lg bg-slate-800/30 border border-slate-700/30 text-center">
                    <div className="text-xs font-mono text-slate-500 mb-1">实际能耗</div>
                    <div className="text-xl font-bold text-emerald-400 font-mono">{energySummary.saving_kwh.toFixed(1)} <span className="text-xs text-slate-500">kWh</span></div>
                  </div>
                  <div className="p-4 rounded-lg bg-slate-800/30 border border-emerald-500/20 text-center">
                    <div className="text-xs font-mono text-slate-500 mb-1">节能率</div>
                    <div className="text-xl font-bold text-emerald-400 font-mono">{energySummary.saving_rate.toFixed(1)}%</div>
                  </div>
                  <div className="p-4 rounded-lg bg-slate-800/30 border border-emerald-500/20 text-center">
                    <div className="text-xs font-mono text-slate-500 mb-1">节省电费</div>
                    <div className="text-xl font-bold text-emerald-400 font-mono">¥{energySummary.cost_saved_cny.toFixed(1)}</div>
                  </div>
                </div>
              )}
            </TabsContent>

            <TabsContent value="simulation" className="mt-0">
              <div className="flex items-center justify-between p-4 rounded-lg bg-slate-800/30 border border-slate-700/30">
                <div className="text-xs font-mono text-slate-400">
                  仿真模式: <span className="text-purple-400">READY</span>
                </div>
                <div className="flex items-center gap-4 text-xs font-mono text-slate-500">
                  <span>天数: 7</span>
                  <span>室外温度: 28°C</span>
                  <span>辐射: 1000W/m²</span>
                </div>
                <button className="px-4 py-1.5 text-xs font-mono bg-purple-500/10 text-purple-400 border border-purple-500/20 rounded-lg hover:bg-purple-500/20 transition-colors">
                  运行仿真
                </button>
              </div>
            </TabsContent>
          </Tabs>
        </section>
      </div>

      {/* Right Sidebar */}
      <aside className="fixed right-0 top-16 w-72 h-[calc(100vh-4rem)] bg-slate-900/80 border-l border-slate-800 p-6 flex flex-col items-center gap-8 shadow-2xl z-40 overflow-y-auto">
        {/* Temperature Knob */}
        <PrecisionKnob
          value={targetTemp}
          onChange={() => {}}
          label="Target Temp"
          unit="°C"
          size={180}
        />

        {/* Fan Speed */}
        <div className="w-full space-y-3">
          <div className="flex justify-between text-xs font-mono text-slate-400 uppercase tracking-wider">
            <span className="flex items-center gap-1.5">
              <Activity className="w-3 h-3" />
              Fan Speed
            </span>
            <span className="text-cyan-400">85%</span>
          </div>
          <div className="h-3 bg-slate-800 rounded-full overflow-hidden border border-slate-700/50">
            <motion.div
              className="h-full bg-gradient-to-r from-emerald-600 to-emerald-400"
              initial={{ width: 0 }}
              animate={{ width: '85%' }}
              transition={{ duration: 1, delay: 0.5 }}
              style={{ boxShadow: '0 0 15px rgba(52, 211, 153, 0.4)' }}
            />
          </div>
          <div className="text-[10px] font-mono text-slate-600 text-right">
            2400 RPM
          </div>
        </div>

        {/* Quick Stats */}
        <div className="w-full space-y-3 pt-4 border-t border-slate-700/30">
          <div className="text-xs font-mono text-slate-500 uppercase tracking-wider mb-3">
            Quick Stats
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-slate-500 font-mono">继电器1</span>
            <span className="text-emerald-400 font-mono">ON</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-slate-500 font-mono">继电器2</span>
            <span className="text-slate-600 font-mono">OFF</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-slate-500 font-mono">窗帘</span>
            <span className="text-cyan-400 font-mono">{latestSnapshot?.curtain_steps ?? 0} steps</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-slate-500 font-mono">总线电压</span>
            <span className="text-slate-300 font-mono">{latestSnapshot?.bus_v?.toFixed(2) ?? '--'}V</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-slate-500 font-mono">电流</span>
            <span className="text-slate-300 font-mono">{latestSnapshot?.current_ma?.toFixed(0) ?? '--'}mA</span>
          </div>
        </div>

        {/* Comfort Score */}
        <div className="w-full pt-4 border-t border-slate-700/30">
          <div className="text-xs font-mono text-slate-500 uppercase tracking-wider mb-3">
            Comfort Score
          </div>
          <div className="flex items-center justify-center">
            <div className="relative w-24 h-24">
              <svg className="w-full h-full -rotate-90">
                <circle cx="50%" cy="50%" r="40%" fill="none" stroke="#1e293b" strokeWidth="8" />
                <motion.circle
                  cx="50%" cy="50%" r="40%"
                  fill="none"
                  stroke="#8b5cf6"
                  strokeWidth="8"
                  strokeLinecap="round"
                  strokeDasharray={`${(latestSnapshot?.comfort_score ?? 0) / 100 * 251}, 251`}
                  initial={{ strokeDashoffset: 251 }}
                  animate={{ strokeDashoffset: 0 }}
                  transition={{ duration: 1.5, delay: 0.3 }}
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-lg font-bold text-slate-100 font-mono">
                  {latestSnapshot?.comfort_score?.toFixed(0) ?? '--'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}
