import { useEffect } from 'react';
import { Routes, Route } from 'react-router-dom';
import TopBar from '@/components/layout/TopBar';
import SideNav from '@/components/layout/SideNav';
import ToastContainer from '@/components/common/ToastContainer';
import DashboardPage from '@/pages/DashboardPage';
import RealtimePage from '@/pages/RealtimePage';
import AIDecisionPage from '@/pages/AIDecisionPage';
import EnergyAnalysisPage from '@/pages/EnergyAnalysisPage';
import HealthPage from '@/pages/HealthPage';
import SimulationPage from '@/pages/SimulationPage';
import { useAppStore, startAutoRefresh, stopAutoRefresh } from '@/store/useAppStore';

function AppLayout({ children }: { children: React.ReactNode }) {
  const { sidebarOpen } = useAppStore();

  // 轮询统一在这里启动（评审 §8 第 4 步）：此前只有 DashboardPage / RealtimePage 各自启停，
  // 切到 AI/能源/健康/仿真页就停止刷新。行为不变量不变 —— 仍是 3s 轮询 + 手动刷新 + autoRefresh 开关。
  useEffect(() => {
    startAutoRefresh();
    return () => stopAutoRefresh();
  }, []);

  return (
    <div className="min-h-screen bg-[#020c1b]">
      <TopBar />
      <SideNav />
      <main
        className={`transition-all duration-300 ${
          sidebarOpen ? 'pl-56' : 'pl-14'
        }`}
      >
        {children}
      </main>
      <ToastContainer />
    </div>
  );
}

export default function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/realtime" element={<RealtimePage />} />
        <Route path="/ai" element={<AIDecisionPage />} />
        <Route path="/energy" element={<EnergyAnalysisPage />} />
        <Route path="/health" element={<HealthPage />} />
        <Route path="/simulation" element={<SimulationPage />} />
      </Routes>
    </AppLayout>
  );
}
