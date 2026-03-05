'use client';

interface VergilSigilProps {
  size?: number;
}

const VergilSigil = ({ size = 24 }: VergilSigilProps) => {
  return (
    <div
      className="flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      <div
        className="rounded-full flex items-center justify-center"
        style={{
          width: size,
          height: size,
          border: '1px solid hsl(199 90% 64% / 0.3)',
          background: 'hsl(199 90% 64% / 0.05)',
        }}
      >
        <span
          className="font-cinzel"
          style={{
            fontSize: size * 0.4,
            color: 'hsl(199 90% 64%)',
          }}
        >
          V
        </span>
      </div>
    </div>
  );
};

export default VergilSigil;
