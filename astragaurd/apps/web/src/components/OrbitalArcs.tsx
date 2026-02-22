const OrbitalArcs = () => {
  return (
    <svg
      className="absolute inset-0 w-full h-full pointer-events-none"
      viewBox="0 0 1440 900"
      preserveAspectRatio="xMidYMid slice"
      fill="none"
    >
      <defs>
        <linearGradient id="arc-grad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="rgba(25,247,166,0)" />
          <stop offset="50%" stopColor="rgba(25,247,166,0.15)" />
          <stop offset="100%" stopColor="rgba(25,247,166,0)" />
        </linearGradient>
        <linearGradient id="arc-grad-warn" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="rgba(255,176,32,0)" />
          <stop offset="50%" stopColor="rgba(255,176,32,0.1)" />
          <stop offset="100%" stopColor="rgba(255,176,32,0)" />
        </linearGradient>
      </defs>

      {/* Large orbital arcs */}
      <ellipse
        cx="1100"
        cy="450"
        rx="500"
        ry="320"
        stroke="url(#arc-grad)"
        strokeWidth="1"
        opacity="0.5"
        transform="rotate(-15 1100 450)"
      />
      <ellipse
        cx="1050"
        cy="400"
        rx="380"
        ry="240"
        stroke="url(#arc-grad)"
        strokeWidth="0.8"
        opacity="0.35"
        transform="rotate(-8 1050 400)"
      />
      <ellipse
        cx="1150"
        cy="500"
        rx="600"
        ry="400"
        stroke="url(#arc-grad-warn)"
        strokeWidth="0.6"
        opacity="0.2"
        transform="rotate(-20 1150 500)"
      />

      {/* Small debris dots */}
      {[
        { cx: 900, cy: 200, r: 1.5, opacity: 0.6 },
        { cx: 1200, cy: 300, r: 1, opacity: 0.4 },
        { cx: 800, cy: 600, r: 1.2, opacity: 0.3 },
        { cx: 1300, cy: 550, r: 0.8, opacity: 0.5 },
        { cx: 700, cy: 350, r: 1, opacity: 0.25 },
      ].map((dot, i) => (
        <circle
          key={i}
          cx={dot.cx}
          cy={dot.cy}
          r={dot.r}
          fill="hsl(var(--primary))"
          opacity={dot.opacity}
        >
          <animate
            attributeName="opacity"
            values={`${dot.opacity};${dot.opacity * 0.3};${dot.opacity}`}
            dur={`${3 + i * 0.7}s`}
            repeatCount="indefinite"
          />
        </circle>
      ))}
    </svg>
  );
};

export default OrbitalArcs;
