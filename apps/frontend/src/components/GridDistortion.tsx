'use client';

import React, { useRef, useEffect } from 'react';

interface GridDistortionProps {
  gridSize?: number;
  mouseRadius?: number;
  strength?: number;
  text?: string;
}

export default function GridDistortion({
  gridSize = 5, 
  mouseRadius = 120,
  strength = 0.15,
  text = 'vergil',
}: GridDistortionProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouseRef = useRef({ x: -1000, y: -1000, targetX: -1000, targetY: -1000 });
  const animationFrameRef = useRef<number>(0);

  // Store grid data
  const dataRef = useRef<{
    pos: Float32Array;
    origin: Float32Array;
    isVisible: Uint8Array;
    count: number;
    staticCanvas: HTMLCanvasElement;
    scaledGridSize: number;
    scaledMouseRadius: number;
  } | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Alpha: true to support transparency (crucial for hiding the 'punch hole')
    const ctx = canvas.getContext('2d', { alpha: true });
    if (!ctx) return;

    const handleResize = () => {
      // Handle DPI scaling
      const dpr = window.devicePixelRatio || 1;
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
      
      initGrid(dpr);
    };

    const handleMouseMove = (e: MouseEvent) => {
      const dpr = window.devicePixelRatio || 1;
      mouseRef.current.targetX = e.clientX * dpr;
      mouseRef.current.targetY = e.clientY * dpr;
    };

    const initGrid = (dpr: number) => {
      // Scale grid size and font by DPR
      const scaledGridSize = gridSize * dpr;
      const cols = Math.ceil(canvas.width / scaledGridSize);
      const rows = Math.ceil(canvas.height / scaledGridSize);
      const count = cols * rows;

      const pos = new Float32Array(count * 2);
      const origin = new Float32Array(count * 2);
      const isVisible = new Uint8Array(count);

      const fontSize = Math.min(canvas.width / 4, 400 * dpr); 

      // Offscreen canvas for static rendering
      const staticCanvas = document.createElement('canvas');
      staticCanvas.width = canvas.width;
      staticCanvas.height = canvas.height;
      const staticCtx = staticCanvas.getContext('2d');

      if (staticCtx) {
        staticCtx.scale(dpr, dpr); // Scale for drawing text cleanly
        // Transparent background!
        staticCtx.clearRect(0, 0, canvas.width / dpr, canvas.height / dpr);

        // Draw text
        staticCtx.fillStyle = '#ffffff';
        staticCtx.font = `900 ${fontSize / dpr}px "Space Grotesk", sans-serif`;
        staticCtx.textAlign = 'center';
        staticCtx.textBaseline = 'middle';
        staticCtx.fillText(text, canvas.width / dpr / 2, canvas.height / dpr / 2);
        staticCtx.setTransform(1, 0, 0, 1, 0, 0); // Reset scale
      }
      
      const imageData = staticCtx?.getImageData(0, 0, canvas.width, canvas.height).data;

      let index = 0;
      for (let i = 0; i < cols; i++) {
        for (let j = 0; j < rows; j++) {
          const x = i * scaledGridSize;
          const y = j * scaledGridSize;
          
          pos[index * 2] = x;
          pos[index * 2 + 1] = y;
          origin[index * 2] = x;
          origin[index * 2 + 1] = y;

          if (imageData) {
            const centerX = Math.floor(x + scaledGridSize / 2);
            const centerY = Math.floor(y + scaledGridSize / 2);
            const pixelIndex = (centerY * canvas.width + centerX) * 4;
            
            if (imageData[pixelIndex + 3] > 0) {
              isVisible[index] = 1;
            }
          }
          
          index++;
        }
      }

      dataRef.current = { 
        pos, 
        origin, 
        isVisible, 
        count, 
        staticCanvas, 
        scaledGridSize,
        scaledMouseRadius: mouseRadius * dpr 
      };
    };

    const animate = () => {
      // Clear screen to transparent
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Smooth mouse
      mouseRef.current.x += (mouseRef.current.targetX - mouseRef.current.x) * 0.1;
      mouseRef.current.y += (mouseRef.current.targetY - mouseRef.current.y) * 0.1;

      const mouseX = mouseRef.current.x;
      const mouseY = mouseRef.current.y;

      const data = dataRef.current;
      if (!data) {
        animationFrameRef.current = requestAnimationFrame(animate);
        return;
      }

      const { pos, origin, isVisible, count, staticCanvas, scaledGridSize, scaledMouseRadius } = data;
      
      // 1. Draw Static Text Layer
      ctx.drawImage(staticCanvas, 0, 0);

      // 2. Punch hole around mouse
      ctx.globalCompositeOperation = 'destination-out';
      ctx.beginPath();
      ctx.arc(mouseX, mouseY, scaledMouseRadius * 1.3, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalCompositeOperation = 'source-over';

      // 3. Draw Distorted Image Chunks
      const mouseRadiusSq = scaledMouseRadius * scaledMouseRadius;
      const activeRadiusSq = (scaledMouseRadius * 1.6) ** 2; 

      for (let i = 0; i < count; i++) {
        if (isVisible[i] === 0) continue;

        const ix = i * 2;
        const iy = i * 2 + 1;

        const originX = origin[ix];
        const originY = origin[iy];
        
        const dx = mouseX - (originX + scaledGridSize / 2);
        const dy = mouseY - (originY + scaledGridSize / 2);
        const distSq = dx * dx + dy * dy;

        if (distSq > activeRadiusSq) {
          if (Math.abs(pos[ix] - originX) < 0.1 && Math.abs(pos[iy] - originY) < 0.1) {
             continue; 
          }
        }

        let targetX = originX;
        let targetY = originY;

        if (distSq < mouseRadiusSq) {
          const dist = Math.sqrt(distSq);
          const influence = (scaledMouseRadius - dist) / scaledMouseRadius;
          const angle = Math.atan2(dy, dx);
          
          const moveDist = influence * strength * scaledGridSize * 4; 

          targetX -= Math.cos(angle) * moveDist;
          targetY -= Math.sin(angle) * moveDist;
        }

        const ease = 0.15;
        pos[ix] += (targetX - pos[ix]) * ease;
        pos[iy] += (targetY - pos[iy]) * ease;

        const x = pos[ix];
        const y = pos[iy];

        ctx.drawImage(
          staticCanvas,
          originX, originY, scaledGridSize, scaledGridSize,
          Math.floor(x), Math.floor(y), scaledGridSize + 1.0, scaledGridSize + 1.0
        );
      }

      animationFrameRef.current = requestAnimationFrame(animate);
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    window.addEventListener('mousemove', handleMouseMove);
    animate();

    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
      cancelAnimationFrame(animationFrameRef.current);
    };
  }, [gridSize, mouseRadius, strength, text]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 w-full h-full pointer-events-none z-0"
    />
  );
}
