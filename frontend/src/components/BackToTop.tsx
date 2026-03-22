import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ArrowUp } from "lucide-react";
import { transition } from "@/config";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";

const BackToTop = () => {
  const [visible, setVisible] = useState(false);
  const prefersReducedMotion = useReducedMotionPreference();

  useEffect(() => {
    const handleScroll = () => {
      setVisible(window.scrollY > 400);
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <AnimatePresence>
      {visible && (
        <motion.button
          type="button"
          aria-label="回到顶部"
          onClick={() =>
            window.scrollTo({ top: 0, behavior: prefersReducedMotion ? "auto" : "smooth" })
          }
          className="fixed bottom-6 right-6 z-50 flex h-10 w-10 items-center justify-center rounded-full liquid-glass text-foreground/60 hover:text-foreground transition-colors active:scale-95"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 20 }}
          transition={transition({ duration: 0.25, reducedMotion: prefersReducedMotion })}
        >
          <ArrowUp className="h-4 w-4" />
        </motion.button>
      )}
    </AnimatePresence>
  );
};

export default BackToTop;
