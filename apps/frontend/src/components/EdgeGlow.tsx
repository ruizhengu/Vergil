'use client';

const EdgeGlow = () => {
  return (
    <>
      {/* Left edge */}
      <div
        className="fixed top-0 left-0 h-full pointer-events-none animate-edge-breathe"
        style={{
          width: 80,
          zIndex: 5,
          background: 'linear-gradient(90deg, rgba(79,195,247,0.5) 0px, rgba(79,195,247,0.15) 2px, transparent 80px)',
          maskImage: 'linear-gradient(to bottom, transparent 0%, white 30%, white 70%, transparent 100%)',
          WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, white 30%, white 70%, transparent 100%)',
        }}
      />
      {/* Right edge */}
      <div
        className="fixed top-0 right-0 h-full pointer-events-none animate-edge-breathe"
        style={{
          width: 80,
          zIndex: 5,
          background: 'linear-gradient(270deg, rgba(79,195,247,0.5) 0px, rgba(79,195,247,0.15) 2px, transparent 80px)',
          maskImage: 'linear-gradient(to bottom, transparent 0%, white 30%, white 70%, transparent 100%)',
          WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, white 30%, white 70%, transparent 100%)',
        }}
      />
      {/* Top edge */}
      <div
        className="fixed top-0 left-0 w-full pointer-events-none"
        style={{
          height: 50,
          zIndex: 5,
          background: 'linear-gradient(180deg, rgba(201,168,76,0.35) 0px, rgba(201,168,76,0.1) 2px, transparent 50px)',
          maskImage: 'linear-gradient(to right, transparent 0%, white 20%, white 80%, transparent 100%)',
          WebkitMaskImage: 'linear-gradient(to right, transparent 0%, white 20%, white 80%, transparent 100%)',
        }}
      />
      {/* Bottom edge */}
      <div
        className="fixed bottom-0 left-0 w-full pointer-events-none"
        style={{
          height: 30,
          zIndex: 5,
          background: 'linear-gradient(0deg, rgba(79,195,247,0.15) 0px, transparent 30px)',
        }}
      />
    </>
  );
};

export default EdgeGlow;
