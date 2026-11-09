import React, { useState } from 'react';
import { Outlet, useParams } from 'react-router-dom';
import Sidebar from './Sidebar';
import { PrathikshaProvider } from '../prathiksha/PrathikshaContext';
import PrathikshaWidget from '../prathiksha/PrathikshaWidget';

export default function Layout() {
  const { repoId } = useParams();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  return (
    <PrathikshaProvider>
      <div className="flex h-screen w-screen overflow-hidden bg-[#F5FAFA] text-[#172B35] font-sans">
        <Sidebar
          mobileOpen={mobileSidebarOpen}
          onCloseMobile={() => setMobileSidebarOpen(false)}
        />
        <div className="flex-1 flex flex-col min-w-0 overflow-y-auto relative">
          <Outlet context={{ openMobileSidebar: () => setMobileSidebarOpen(true) }} />
          {/* Floating AI Assistant Prathiksha */}
          <PrathikshaWidget />
        </div>
      </div>
    </PrathikshaProvider>
  );
}
