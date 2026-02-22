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
  const missDistance = useAnimatedNumber(847.3, 2400, 1);
  const deltaV = useAnimatedNumber(0.23, 2000, 3);
  const maneuverCost = useAnimatedNumber(5000, 2600, 0);

  return (
    <div className="relative rounded-lg border border-border overflow-hidden" style={{ background: "var(--panel)" }}>
      {/* Scan line */}
      <div className="scan-line absolute inset-0 z-20 pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
          <span className="text-xs font-mono font-semibold tracking-widest uppercase text-primary">
            Autonomy Decision Console
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
        <ReadoutRow label="COLLISION PROB (Pc)" value={collisionProb} unit="%" variant="danger" />
        <ReadoutRow label="MISS DISTANCE" value={`${Number(missDistance).toLocaleString()} m`} variant="warn" />
        <ReadoutRow label="MIN Δv REQUIRED" value={`${deltaV} m/s`} variant="accent" />
        <ReadoutRow label="MANEUVER COST" value={`$${Number(maneuverCost).toLocaleString()}`} variant="muted" />

        {/* Decision mode display */}
        <div className="flex items-center gap-3 pt-2">
          <span className="text-xs font-mono text-muted-foreground uppercase tracking-wider">Decision</span>
          <div className="flex items-center gap-1.5">
            {(["IGNORE", "DEFER", "INSURE", "MANEUVER"] as const).map((d) => (
              <button
                key={d}
                onClick={() => setMode(d === "INSURE" || d === "MANEUVER" ? d : mode)}
                className={`px-2.5 py-1 rounded text-[10px] font-mono font-semibold uppercase tracking-wider border transition-all duration-200 ${(d === "INSURE" && mode === "INSURE") || (d === "MANEUVER" && mode === "MANEUVER")
                    ? "bg-primary text-primary-foreground border-primary"
                    : d === "IGNORE"
                      ? "border-primary/20 text-primary/40"
                      : d === "DEFER"
                        ? "border-warn/20 text-warn/40"
                        : "border-border text-muted-foreground hover:border-primary/40"
                  }`}
              >
                {d}
              </button>
            ))}
          </div>
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
