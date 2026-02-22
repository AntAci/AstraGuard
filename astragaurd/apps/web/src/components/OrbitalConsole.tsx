import { useState, useEffect } from "react";

const useAnimatedNumber = (target: number, duration = 2000, decimals = 4) => {
  const [value, setValue] = useState(0);
  useEffect(() => {
    const start = performance.now();
    const tick = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(target * eased);
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [target, duration]);
  return value.toFixed(decimals);
};

const OrbitalConsole = () => {
  const [mode, setMode] = useState<"INSURE" | "MANEUVER">("INSURE");
  const collisionProb = useAnimatedNumber(0.0037, 2200, 6);
  const var95 = useAnimatedNumber(12847.32, 2400, 2);
  const policyBound = useAnimatedNumber(50000.0, 2000, 2);

  const txHash = "7xKp...3fQm";

  return (
    <div className="relative rounded-lg border border-border overflow-hidden" style={{ background: "var(--panel)" }}>
      {/* Scan line */}
      <div className="scan-line absolute inset-0 z-20 pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
          <span className="text-xs font-mono font-semibold tracking-widest uppercase text-primary">
            Live Orbital Risk Console
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-destructive opacity-80" />
          <span className="w-2.5 h-2.5 rounded-full bg-warn opacity-80" />
          <span className="w-2.5 h-2.5 rounded-full bg-primary opacity-80" />
        </div>
      </div>

      {/* Readouts */}
      <div className="px-5 py-4 space-y-4">
        <ReadoutRow label="COLLISION PROB" value={collisionProb} unit="%" variant="danger" />
        <ReadoutRow label="VAR (95%)" value={`$${Number(var95).toLocaleString()}`} variant="warn" />
        <ReadoutRow label="POLICY BOUND" value={`$${Number(policyBound).toLocaleString()}`} variant="accent" />
        <ReadoutRow label="TX HASH" value={txHash} variant="muted" mono />

        {/* Mode toggle */}
        <div className="flex items-center gap-3 pt-2">
          <span className="text-xs font-mono text-muted-foreground uppercase tracking-wider">Mode</span>
          <button
            onClick={() => setMode(mode === "INSURE" ? "MANEUVER" : "INSURE")}
            className="relative flex items-center w-[180px] h-8 rounded-md border border-border overflow-hidden transition-colors"
            style={{ background: "rgba(var(--accent-raw), 0.05)" }}
          >
            <span
              className="absolute top-0.5 bottom-0.5 w-[calc(50%-2px)] rounded bg-primary transition-all duration-300 ease-out"
              style={{ left: mode === "INSURE" ? "2px" : "calc(50% + 2px)" }}
            />
            <span
              className={`relative z-10 flex-1 text-center text-xs font-mono font-semibold uppercase tracking-wider transition-colors duration-300 ${
                mode === "INSURE" ? "text-primary-foreground" : "text-muted-foreground"
              }`}
            >
              Insure
            </span>
            <span
              className={`relative z-10 flex-1 text-center text-xs font-mono font-semibold uppercase tracking-wider transition-colors duration-300 ${
                mode === "MANEUVER" ? "text-primary-foreground" : "text-muted-foreground"
              }`}
            >
              Maneuver
            </span>
          </button>
        </div>
      </div>

      {/* Mini orbit visualization */}
      <div className="px-5 pb-5 pt-2 flex justify-center">
        <MiniOrbit />
      </div>
    </div>
  );
};

const ReadoutRow = ({
  label,
  value,
  unit,
  variant,
  mono,
}: {
  label: string;
  value: string;
  unit?: string;
  variant: "danger" | "warn" | "accent" | "muted";
  mono?: boolean;
}) => {
  const colorMap = {
    danger: "text-destructive",
    warn: "text-warn",
    accent: "text-primary",
    muted: "text-muted-foreground",
  };

  return (
    <div className="flex items-baseline justify-between">
      <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-[0.15em]">
        {label}
      </span>
      <span className={`text-sm font-mono font-semibold tabular-nums ${colorMap[variant]} ${mono ? "tracking-wider" : ""}`}>
        {value}
        {unit && <span className="text-[10px] ml-1 text-muted-foreground">{unit}</span>}
      </span>
    </div>
  );
};

const MiniOrbit = () => {
  const size = 140;
  const cx = size / 2;
  const cy = size / 2;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="opacity-80">
      {/* Orbit rings */}
      {[28, 44, 60].map((r, i) => (
        <circle
          key={i}
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke="hsl(var(--primary))"
          strokeWidth="0.5"
          opacity={0.2 + i * 0.05}
        />
      ))}

      {/* Center body */}
      <circle cx={cx} cy={cy} r={4} fill="hsl(var(--primary))" opacity="0.7">
        <animate attributeName="opacity" values="0.7;1;0.7" dur="2s" repeatCount="indefinite" />
      </circle>

      {/* Orbiting dots */}
      {[
        { r: 28, dur: "6s", color: "hsl(var(--primary))", dotR: 2.5 },
        { r: 44, dur: "9s", color: "hsl(var(--warn))", dotR: 2 },
        { r: 60, dur: "13s", color: "hsl(var(--destructive))", dotR: 1.8 },
      ].map((orbit, i) => (
        <g key={i} style={{ transformOrigin: `${cx}px ${cy}px`, animation: `orbit-${i + 1} ${orbit.dur} linear infinite` }}>
          <circle cx={cx + orbit.r} cy={cy} r={orbit.dotR} fill={orbit.color} opacity="0.9">
            <animate attributeName="opacity" values="0.9;0.5;0.9" dur="2s" repeatCount="indefinite" />
          </circle>
        </g>
      ))}
    </svg>
  );
};

export default OrbitalConsole;
