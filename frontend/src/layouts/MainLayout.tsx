import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { BottomNav } from '../components/BottomNav';
import clsx from 'clsx';

export const MainLayout: React.FC = () => {
  const location = useLocation();
  const isHome = location.pathname === '/';

  return (
    <div className={clsx(
      "flex flex-col h-screen w-full overflow-hidden",
      isHome ? "bg-black" : "bg-gray-50"
    )}>
      <main className="flex-1 overflow-y-auto no-scrollbar relative">
        <Outlet />
      </main>
      <BottomNav />
    </div>
  );
};
