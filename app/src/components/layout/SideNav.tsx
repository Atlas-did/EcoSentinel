import { useLocation, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  LayoutDashboard,
  Activity,
  Brain,
  Zap,
  HeartPulse,
  BarChart3,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useAppStore } from '@/store/useAppStore';

const navItems = [
  { path: '/', label: '总览', icon: LayoutDashboard, description: 'Dashboard' },
  { path: '/realtime', label: '实时曲线', icon: Activity, description: 'Real-time' },
  { path: '/ai', label: 'AI 决策', icon: Brain, description: 'AI Engine' },
  { path: '/energy', label: '能耗分析', icon: Zap, description: 'Energy' },
  { path: '/health', label: '系统健康', icon: HeartPulse, description: 'Health' },
  { path: '/simulation', label: '仿真', icon: BarChart3, description: 'Sim' },
];

export default function SideNav() {
  const location = useLocation();
  const navigate = useNavigate();
  const { sidebarOpen, toggleSidebar } = useAppStore();

  return (
    <aside
      className={`fixed left-0 top-16 h-[calc(100vh-4rem)] bg-[#0a192f]/95 border-r border-slate-800/60 backdrop-blur-xl z-40 transition-all duration-300 ${
        sidebarOpen ? 'w-56' : 'w-14'
      }`}
    >
      {/* Toggle Button */}
      <button
        onClick={toggleSidebar}
        className="absolute -right-3 top-4 w-6 h-6 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-400 hover:text-slate-200 transition-colors z-50"
      >
        {sidebarOpen ? (
          <ChevronLeft className="w-3 h-3" />
        ) : (
          <ChevronRight className="w-3 h-3" />
        )}
      </button>

      <nav className="p-3 pt-6 space-y-1">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          const Icon = item.icon;

          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all relative group ${
                isActive
                  ? 'text-cyan-400'
                  : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              {isActive && (
                <motion.div
                  layoutId="navIndicator"
                  className="absolute inset-0 bg-cyan-500/5 border border-cyan-500/10 rounded-lg"
                  transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                />
              )}
              <Icon className="w-4.5 h-4.5 flex-shrink-0 relative z-10" />
              {sidebarOpen && (
                <div className="relative z-10 text-left">
                  <div className="text-xs font-medium">{item.label}</div>
                  <div className="text-[9px] font-mono text-slate-600 uppercase tracking-wider">
                    {item.description}
                  </div>
                </div>
              )}
              {!sidebarOpen && (
                <div className="absolute left-full ml-2 px-2 py-1 bg-slate-800 border border-slate-700 rounded text-xs font-mono text-slate-300 whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
                  {item.label}
                </div>
              )}
            </button>
          );
        })}
      </nav>

      {/* Bottom Status */}
      {sidebarOpen && (
        <div className="absolute bottom-4 left-3 right-3 p-3 rounded-lg bg-slate-800/30 border border-slate-700/20">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[9px] font-mono text-slate-600 uppercase">System</span>
            <span className="text-[9px] font-mono text-emerald-400">ONLINE</span>
          </div>
          <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-emerald-500/50"
              animate={{ width: ['60%', '80%', '60%'] }}
              transition={{ duration: 3, repeat: Infinity }}
            />
          </div>
        </div>
      )}
    </aside>
  );
}
