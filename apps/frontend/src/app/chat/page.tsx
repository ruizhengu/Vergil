'use client';

import { useEffect, useState } from 'react';
import { Dashboard } from '@/components/Dashboard';

export default function ChatPage() {
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  if (!isMounted) {
    return (
      <div className="h-screen w-screen bg-[#050810] flex items-center justify-center">
        <div className="text-white/50">Loading...</div>
      </div>
    );
  }

  return <Dashboard />;
}
