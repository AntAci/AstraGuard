import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import OrbitalConsole from "./OrbitalConsole";
import OrbitalArcs from "./OrbitalArcs";

const Hero = () => {
  return (
    <section className="relative min-h-screen flex items-center overflow-hidden bg-background">
      {/* Animated grid */}
      <div className="absolute inset-0 animated-grid" />

      {/* Orbital arcs SVG background */}
      <OrbitalArcs />

      {/* Radial vignette */}
      <div className="absolute inset-0 radial-vignette pointer-events-none" />

      {/* Content */}
      <div className="relative z-10 w-full max-w-[1400px] mx-auto px-6 md:px-12 py-16 grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-16 items-center">
        {/* Left column */}
        <div className="flex flex-col gap-8">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="flex items-center gap-2"
          >
            <span className="inline-block w-2 h-2 rounded-full bg-primary animate-pulse" />
            <span className="text-xs font-mono tracking-widest uppercase text-primary">
              44,870+ Objects Tracked
            </span>
          </motion.div>

          <div className="flex flex-col gap-4">
            {["Autonomous", "Maneuver-Tax", "Optimization."].map(
              (word, i) => (
                <motion.span
                  key={word}
                  initial={{ opacity: 0, y: 30, filter: "blur(8px)" }}
                  animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                  transition={{ duration: 0.6, delay: 0.2 + i * 0.12 }}
                  className="block font-display font-bold text-foreground leading-[0.95] tracking-[-0.03em]"
                  style={{ fontSize: "clamp(2.8rem, 6vw, 5.2rem)" }}
                >
                  {word}
                </motion.span>
              )
            )}
          </div>

          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.8 }}
            className="max-w-lg text-sm md:text-base font-mono text-muted-foreground leading-relaxed"
          >
            AstraGuard screens 44,870+ tracked objects, forecasts conjunctions
            72 hours out, and runs a deterministic decision loop—IGNORE, DEFER,
            INSURE, or MANEUVER—to minimize recurring operations cost with
            auditable economics.
          </motion.p>

          {/* Stats row */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.9 }}
            className="flex flex-wrap gap-6"
          >
            {[
              { value: "72h", label: "Forecast Horizon" },
              { value: "4", label: "Decision Modes" },
              { value: "<0.5 m/s", label: "Max Δv Budget" },
            ].map((stat) => (
              <div key={stat.label} className="flex flex-col">
                <span className="text-lg font-display font-bold text-primary">
                  {stat.value}
                </span>
                <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest">
                  {stat.label}
                </span>
              </div>
            ))}
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 1.0 }}
            className="flex flex-wrap gap-4"
          >
            <Link to="/app" className="group relative px-7 py-3 rounded-md bg-primary text-primary-foreground font-display font-semibold text-sm tracking-wide uppercase transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_0_30px_rgba(var(--accent-raw),0.35)]">
              Open Mission Control
              <span className="absolute inset-0 rounded-md bg-primary opacity-0 group-hover:opacity-20 blur-xl transition-opacity duration-300" />
            </Link>
            <a
              href="https://github.com/AntAci/Antlikeswinninghackeurope"
              target="_blank"
              rel="noopener noreferrer"
              className="px-7 py-3 rounded-md border border-border text-foreground font-display font-semibold text-sm tracking-wide uppercase transition-all duration-300 hover:border-primary hover:text-primary hover:-translate-y-0.5 hover:shadow-[0_0_20px_rgba(var(--accent-raw),0.15)]"
            >
              View on GitHub
            </a>
          </motion.div>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 1.2 }}
            className="text-xs font-mono text-muted-foreground"
          >
            Powered by{" "}
            <span className="text-primary">SGP4 Propagation</span> ·{" "}
            <span className="text-primary">Claude + Gemini</span> ·{" "}
            <span className="text-warn">Stripe</span> ·{" "}
            <span className="text-primary">Solana</span>
          </motion.p>
        </div>

        {/* Right column - Console */}
        <motion.div
          initial={{ opacity: 0, x: 40, scale: 0.96 }}
          animate={{ opacity: 1, x: 0, scale: 1 }}
          transition={{ duration: 0.7, delay: 1.1, ease: "easeOut" }}
        >
          <OrbitalConsole />
        </motion.div>
      </div>
    </section>
  );
};

export default Hero;
