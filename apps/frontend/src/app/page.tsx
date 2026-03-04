'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

export default function LandingPage() {
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    setIsLoaded(true);
  }, []);

  return (
    <main className="min-h-screen w-full bg-[#f8f9fc] text-gray-900 relative overflow-hidden font-sans">
      
      {/* Background Gradients */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-[-20%] right-[-10%] w-[800px] h-[800px] bg-purple-200/40 rounded-full blur-[120px]" />
        <div className="absolute bottom-[-10%] left-[-10%] w-[600px] h-[600px] bg-pink-200/40 rounded-full blur-[100px]" />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-6 pt-32 pb-20 flex flex-col items-center text-center">
        
        {/* Hero Section */}
        <h1 
          className={`text-[120px] md:text-[180px] font-bold tracking-tighter leading-none mb-6 transition-all duration-1000 ${
            isLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-12'
          }`}
          style={{ fontFamily: '"Space Grotesk", sans-serif' }}
        >
          vergil
        </h1>

        <p className={`text-xl md:text-2xl text-gray-600 max-w-2xl font-light mb-12 transition-all duration-1000 delay-200 ${
          isLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
        }`}>
          The autonomous AI agent for creators. Deploy secure smart contracts and launch your NFT collections without writing a single line of code.
        </p>

        {/* CTA Buttons */}
        <div className={`flex flex-col sm:flex-row gap-4 mb-24 transition-all duration-1000 delay-300 ${
          isLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
        }`}>
          <Link
            href="/chat"
            className="px-8 py-4 bg-gradient-to-r from-fuchsia-600 to-purple-600 text-white font-bold text-lg rounded-full transition-all duration-300 hover:scale-105 shadow-lg hover:shadow-xl hover:brightness-110"
          >
            Start Chatting
          </Link>

          <Link
            href="/orchestration"
            className="px-8 py-4 bg-white text-gray-900 font-bold text-lg rounded-full border border-gray-200 transition-all duration-300 hover:scale-105 hover:border-gray-300 shadow-sm hover:shadow-md"
          >
            View Workflow
          </Link>
        </div>

        {/* Features Grid */}
        <div className={`grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-6xl transition-all duration-1000 delay-500 ${
          isLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-12'
        }`}>
          
          {/* Feature 1: Autonomy */}
          <div className="bg-white p-8 rounded-[2rem] shadow-sm border border-gray-100 hover:shadow-md transition-shadow duration-300 text-left h-full flex flex-col">
            <div className="w-14 h-14 bg-[#F5F3FF] rounded-2xl flex items-center justify-center mb-6 text-3xl shrink-0">
              🤖
            </div>
            <h3 className="text-2xl font-bold mb-3 text-gray-900">High Autonomy</h3>
            <p className="text-gray-500 leading-relaxed">
              Vergil handles the heavy lifting. From contract compilation to deployment and verification, the agent manages the entire lifecycle autonomously.
            </p>
          </div>

          {/* Feature 2: Security */}
          <div className="bg-white p-8 rounded-[2rem] shadow-sm border border-gray-100 hover:shadow-md transition-shadow duration-300 text-left h-full flex flex-col">
            <div className="w-14 h-14 bg-[#F5F3FF] rounded-2xl flex items-center justify-center mb-6 text-3xl shrink-0">
              🛡️
            </div>
            <h3 className="text-2xl font-bold mb-3 text-gray-900">High Security</h3>
            <p className="text-gray-500 leading-relaxed">
              Built with safety-first architecture. Every contract is audited against best practices before deployment, ensuring your assets are safe.
            </p>
          </div>

          {/* Feature 3: Creator Friendly */}
          <div className="bg-white p-8 rounded-[2rem] shadow-sm border border-gray-100 hover:shadow-md transition-shadow duration-300 text-left h-full flex flex-col">
            <div className="w-14 h-14 bg-[#F5F3FF] rounded-2xl flex items-center justify-center mb-6 text-3xl shrink-0">
              🎨
            </div>
            <h3 className="text-2xl font-bold mb-3 text-gray-900">For Creators</h3>
            <p className="text-gray-500 leading-relaxed">
              Perfect for artists and newcomers. Whether you're launching an anime collection or digital art, turn your work into NFTs instantly.
            </p>
          </div>

        </div>
      </div>

      <style jsx global>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;700&display=swap');
      `}</style>
    </main>
  );
}
