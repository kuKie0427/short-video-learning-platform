import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Home, BookOpen, PlusSquare, Bell, User } from 'lucide-react';
import clsx from 'clsx';

export const BottomNav: React.FC = () => {
  const location = useLocation();
  const isHome = location.pathname === '/';

  const navItems = [
    { to: '/', icon: Home, label: '首页' },
    { to: '/courses', icon: BookOpen, label: '课程' },
    { to: '/upload', icon: PlusSquare, label: '创作', isAction: true },
    { to: '/inbox', icon: Bell, label: '消息' },
    { to: '/profile', icon: User, label: '我' },
  ];

  return (
    <nav className={clsx(
      "fixed bottom-0 left-0 right-0 z-50 flex items-center justify-around pb-safe pt-2 px-2 transition-colors duration-300",
      isHome ? "bg-black/20 backdrop-blur-sm text-white border-t border-white/10" : "bg-white text-gray-500 border-t border-gray-200"
    )}>
      {navItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) => clsx(
            "flex flex-col items-center justify-center w-full h-12 gap-1",
            isActive && !isHome ? "text-black" : "",
            isActive && isHome ? "text-white font-bold" : "",
            !isActive && isHome ? "text-white/70" : "",
            item.isAction ? "transform -translate-y-2" : ""
          )}
        >
          {({ isActive }) => (
            item.isAction ? (
              <div className={clsx(
                "p-2 rounded-xl",
                isHome ? "bg-white text-black" : "bg-black text-white"
              )}>
                <item.icon size={24} />
              </div>
            ) : (
              <>
                <item.icon size={24} strokeWidth={isActive ? 2.5 : 2} />
                <span className="text-[10px]">{item.label}</span>
              </>
            )
          )}
        </NavLink>
      ))}
    </nav>
  );
};
