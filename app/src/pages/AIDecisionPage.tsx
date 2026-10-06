import { useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain,
  CheckCircle,
  XCircle,
  Clock,
  Shield,
  AlertTriangle,
  TrendingUp,
  BarChart3,
  ChevronDown,
  ChevronUp,
  Sparkles,
} from 'lucide-react';
import StatusBadge from '@/components/common/StatusBadge';
import { meanOf } from '@/lib/stats';

export default function AIDecisionPage() {
  const {
    aiCandidates,
    acceptCandidate,
    rejectCandidate,
  } = useAppStore();

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'pending' | 'accepted' | 'rejected'>('all');

  const filtered = aiCandidates.filter((c) => {
    if (filter === 'pending') return !c.accepted && !c.rejected;
    if (filter === 'accepted') return c.accepted;
    if (filter === 'rejected') return c.rejected;
    return true;
  });

  const stats = {
    total: aiCandidates.length,
    accepted: aiCandidates.filter((c) => c.accepted).length,
    rejected: aiCandidates.filter((c) => c.rejected).length,
    pending: aiCandidates.filter((c) => !c.accepted && !c.rejected).length,
    // 候选列表为空时不得做除法（0/0 = NaN 会显示到界面上）；统一交给 meanOf（有专门用例固化）
    avgScore: meanOf(aiCandidates.map((c) => c.score || 0)),
    avgLatency: meanOf(aiCandidates.map((c) => c.latency_ms || 0)),
  };

  return (
    <div className="min-h-screen bg-[#020c1b] pt-16 pb-6">
      <div className="px-6 py-6 space-y-6 max-w-6xl">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 className="text-xl font-bold text-slate-100 font-mono tracking-tight flex items-center gap-2">
            <Brain className="w-5 h-5 text-cyan-400" />
            AI 决策中心
          </h1>
          <p className="text-xs text-slate-500 font-mono mt-1">
            AI Decision Engine - 建议、裁决、反馈闭环
          </p>
        </motion.div>

        {/* Stats Cards */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="grid grid-cols-6 gap-4"
        >
          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 text-center">
            <div className="text-xs font-mono text-slate-500 mb-1">总候选</div>
            <div className="text-2xl font-bold text-slate-100 font-mono">{stats.total}</div>
          </div>
          <div className="p-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 text-center">
            <div className="text-xs font-mono text-slate-500 mb-1">已接受</div>
            <div className="text-2xl font-bold text-emerald-400 font-mono">{stats.accepted}</div>
          </div>
          <div className="p-4 rounded-xl border border-red-500/20 bg-red-500/5 text-center">
            <div className="text-xs font-mono text-slate-500 mb-1">已拒绝</div>
            <div className="text-2xl font-bold text-red-400 font-mono">{stats.rejected}</div>
          </div>
          <div className="p-4 rounded-xl border border-amber-500/20 bg-amber-500/5 text-center">
            <div className="text-xs font-mono text-slate-500 mb-1">待处理</div>
            <div className="text-2xl font-bold text-amber-400 font-mono">{stats.pending}</div>
          </div>
          <div className="p-4 rounded-xl border border-cyan-500/20 bg-cyan-500/5 text-center">
            <div className="text-xs font-mono text-slate-500 mb-1">平均评分</div>
            <div className="text-2xl font-bold text-cyan-400 font-mono">{stats.avgScore.toFixed(2)}</div>
          </div>
          <div className="p-4 rounded-xl border border-purple-500/20 bg-purple-500/5 text-center">
            <div className="text-xs font-mono text-slate-500 mb-1">平均延迟</div>
            <div className="text-2xl font-bold text-purple-400 font-mono">{stats.avgLatency.toFixed(0)}ms</div>
          </div>
        </motion.div>

        {/* Filter Tabs */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="flex items-center gap-2"
        >
          {(['all', 'pending', 'accepted', 'rejected'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 text-xs font-mono rounded-lg border transition-all ${
                filter === f
                  ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20'
                  : 'bg-transparent text-slate-500 border-slate-800 hover:text-slate-300'
              }`}
            >
              {f === 'all' ? '全部' : f === 'pending' ? '待处理' : f === 'accepted' ? '已接受' : '已拒绝'}
            </button>
          ))}
        </motion.div>

        {/* Candidate List */}
        <div className="space-y-3">
          <AnimatePresence>
            {filtered.map((candidate, i) => (
              <motion.div
                key={candidate.id}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ delay: i * 0.05 }}
                className={`rounded-xl border overflow-hidden ${
                  candidate.accepted
                    ? 'border-emerald-500/20'
                    : candidate.rejected
                    ? 'border-red-500/20'
                    : 'border-slate-700/40'
                } bg-slate-900/60`}
              >
                {/* Main Row */}
                <div
                  className="p-4 flex items-center gap-4 cursor-pointer hover:bg-slate-800/30 transition-colors"
                  onClick={() => setExpandedId(expandedId === candidate.id ? null : candidate.id)}
                >
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                    candidate.accepted
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : candidate.rejected
                      ? 'bg-red-500/10 text-red-400'
                      : 'bg-cyan-500/10 text-cyan-400'
                  }`}>
                    {candidate.accepted ? (
                      <CheckCircle className="w-4 h-4" />
                    ) : candidate.rejected ? (
                      <XCircle className="w-4 h-4" />
                    ) : (
                      <Sparkles className="w-4 h-4" />
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
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
                      {candidate.risk && (
                        <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                          candidate.risk === '低'
                            ? 'bg-emerald-500/10 text-emerald-400'
                            : candidate.risk === '中'
                            ? 'bg-amber-500/10 text-amber-400'
                            : 'bg-red-500/10 text-red-400'
                        }`}>
                          {candidate.risk}风险
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-[10px] font-mono text-slate-500">
                      <span className="flex items-center gap-1">
                        <BarChart3 className="w-3 h-3" />
                        评分: {candidate.score?.toFixed(2)}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {candidate.latency_ms}ms
                      </span>
                      <span>
                        {new Date(candidate.createdAt).toLocaleTimeString('zh-CN')}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {!candidate.accepted && !candidate.rejected && (
                      <>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            acceptCandidate(candidate.id);
                          }}
                          className="px-3 py-1 text-[11px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-lg hover:bg-emerald-500/20 transition-colors flex items-center gap-1"
                        >
                          <CheckCircle className="w-3 h-3" />
                          接受
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            rejectCandidate(candidate.id, '用户手动拒绝');
                          }}
                          className="px-3 py-1 text-[11px] font-mono bg-red-500/10 text-red-400 border border-red-500/20 rounded-lg hover:bg-red-500/20 transition-colors flex items-center gap-1"
                        >
                          <XCircle className="w-3 h-3" />
                          拒绝
                        </button>
                      </>
                    )}
                    {candidate.accepted && (
                      <StatusBadge label="已采纳·未下发" status="online" />
                    )}
                    {candidate.rejected && (
                      <StatusBadge label="已拒绝" status="error" />
                    )}
                    {expandedId === candidate.id ? (
                      <ChevronUp className="w-4 h-4 text-slate-500" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-slate-500" />
                    )}
                  </div>
                </div>

                {/* Expanded Detail */}
                <AnimatePresence>
                  {expandedId === candidate.id && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                      className="overflow-hidden"
                    >
                      <div className="px-4 pb-4 pt-2 border-t border-slate-700/30 space-y-3">
                        {/* Commands */}
                        <div>
                          <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                            <Shield className="w-3 h-3" />
                            建议命令
                          </div>
                          <div className="space-y-1">
                            {candidate.commands.map((cmd, j) => (
                              <div key={j} className="text-xs font-mono text-cyan-400 bg-cyan-500/5 border border-cyan-500/10 rounded px-2 py-1">
                                $ {cmd}
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Risk Warning */}
                        {candidate.risk && candidate.risk !== '低' && (
                          <div className="flex items-start gap-2 p-2 rounded bg-amber-500/5 border border-amber-500/10">
                            <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
                            <span className="text-[11px] font-mono text-amber-400/80">
                              风险提示: 此操作建议可能带来{candidate.risk}等级的影响，请谨慎评估。
                            </span>
                          </div>
                        )}

                        {/* Rejected Reason */}
                        {candidate.rejectedReason && (
                          <div className="flex items-start gap-2 p-2 rounded bg-red-500/5 border border-red-500/10">
                            <XCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0 mt-0.5" />
                            <span className="text-[11px] font-mono text-red-400/80">
                              拒绝原因: {candidate.rejectedReason}
                            </span>
                          </div>
                        )}

                        {/* Score bar */}
                        <div>
                          <div className="flex justify-between text-[10px] font-mono text-slate-500 mb-1">
                            <span>置信度</span>
                            <span>{((candidate.score || 0) * 100).toFixed(0)}%</span>
                          </div>
                          <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                            <motion.div
                              className="h-full bg-gradient-to-r from-cyan-500 to-emerald-400"
                              initial={{ width: 0 }}
                              animate={{ width: `${(candidate.score || 0) * 100}%` }}
                              transition={{ duration: 0.5 }}
                            />
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>

        {/* Feedback Summary Chart Placeholder */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5"
        >
          <h3 className="text-slate-400 text-xs font-mono uppercase tracking-widest flex items-center gap-2 mb-4">
            <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
            AI 反馈统计
          </h3>
          <div className="grid grid-cols-3 gap-4">
            <div className="p-3 rounded-lg bg-slate-800/30 border border-slate-700/30">
              <div className="text-[10px] font-mono text-slate-500 mb-1">接受率</div>
              <div className="flex items-end gap-2">
                <span className="text-2xl font-bold text-emerald-400 font-mono">
                  {stats.total > 0 ? ((stats.accepted / stats.total) * 100).toFixed(0) : 0}%
                </span>
                <div className="flex-1 h-8 bg-slate-800 rounded overflow-hidden">
                  <motion.div
                    className="h-full bg-emerald-500/30"
                    initial={{ width: 0 }}
                    animate={{ width: `${stats.total > 0 ? (stats.accepted / stats.total) * 100 : 0}%` }}
                    transition={{ duration: 0.8 }}
                  />
                </div>
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-800/30 border border-slate-700/30">
              <div className="text-[10px] font-mono text-slate-500 mb-1">拒绝率</div>
              <div className="flex items-end gap-2">
                <span className="text-2xl font-bold text-red-400 font-mono">
                  {stats.total > 0 ? ((stats.rejected / stats.total) * 100).toFixed(0) : 0}%
                </span>
                <div className="flex-1 h-8 bg-slate-800 rounded overflow-hidden">
                  <motion.div
                    className="h-full bg-red-500/30"
                    initial={{ width: 0 }}
                    animate={{ width: `${stats.total > 0 ? (stats.rejected / stats.total) * 100 : 0}%` }}
                    transition={{ duration: 0.8 }}
                  />
                </div>
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-800/30 border border-slate-700/30">
              <div className="text-[10px] font-mono text-slate-500 mb-1">平均响应时间</div>
              <span className="text-2xl font-bold text-cyan-400 font-mono">
                {stats.avgLatency.toFixed(0)}ms
              </span>
              <div className="text-[10px] font-mono text-slate-600 mt-1">
                目标: &lt;300ms
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
