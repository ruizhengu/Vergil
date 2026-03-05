'use client';

const BackgroundEffects = () => {
  return (
    <div className="fixed inset-0 pointer-events-none z-0">
      {/* Radial gradient from top-right */}
      <div
        className="absolute top-0 right-0 w-[800px] h-[800px] opacity-30"
        style={{
          background: 'radial-gradient(ellipse at center, hsl(199 90% 64% / 0.08) 0%, transparent 70%)',
        }}
      />
      {/* Radial gradient from bottom-left */}
      <div
        className="absolute bottom-0 left-0 w-[600px] h-[600px] opacity-20"
        style={{
          background: 'radial-gradient(ellipse at center, hsl(199 90% 64% / 0.06) 0%, transparent 70%)',
        }}
      />
    </div>
  );
};

export default BackgroundEffects;
