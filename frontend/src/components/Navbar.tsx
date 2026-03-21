import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { ChevronDown, Menu, X } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import ThemeToggle from "@/components/ThemeToggle";
import { siteConfig, transition } from "@/config";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";

type NavItem = (typeof siteConfig.navigation)[number];

const NavDropdown = ({
  item,
  navigate,
}: {
  item: NavItem;
  navigate: (path: string) => void;
}) => {
  const [open, setOpen] = useState(false);
  const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0 });
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const triggerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const updateMenuPosition = useCallback(() => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    setMenuPosition({
      top: rect.bottom,
      left: rect.left + rect.width / 2,
    });
  }, []);

  const getPortalThemeClass = () => {
    if (typeof document === "undefined") return "";

    const themedAncestor = triggerRef.current?.closest(".dark, .light");
    if (themedAncestor?.classList.contains("dark")) return "dark";
    if (themedAncestor?.classList.contains("light")) return "light";

    return document.documentElement.classList.contains("dark") ? "dark" : "light";
  };

  useEffect(() => {
    if (!open) return;

    updateMenuPosition();
    window.addEventListener("scroll", updateMenuPosition, true);
    window.addEventListener("resize", updateMenuPosition);

    return () => {
      window.removeEventListener("scroll", updateMenuPosition, true);
      window.removeEventListener("resize", updateMenuPosition);
    };
  }, [open, updateMenuPosition]);

  useEffect(() => {
    if (!open) return;

    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (triggerRef.current?.contains(target) || menuRef.current?.contains(target)) {
        return;
      }

      setOpen(false);
    };

    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  const handleEnter = () => {
    if (item.trigger === "hover") {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      updateMenuPosition();
      setOpen(true);
    }
  };

  const handleLeave = () => {
    if (item.trigger === "hover") {
      timeoutRef.current = setTimeout(() => setOpen(false), 150);
    }
  };

  const handleClick = () => {
    if (item.href) {
      navigate(item.href);
    }
  };

  const handleArrowToggle = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    if (!open) updateMenuPosition();
    setOpen((v) => !v);
  };

  const menu =
    typeof document !== "undefined"
      ? createPortal(
          <div className={getPortalThemeClass()}>
            <AnimatePresence>
              {open && (
                <div
                  ref={menuRef}
                  className="fixed z-[1100] pt-2"
                  style={{
                    top: menuPosition.top,
                    left: menuPosition.left,
                    transform: "translateX(-50%)",
                  }}
                  onMouseEnter={handleEnter}
                  onMouseLeave={handleLeave}
                >
                  <motion.div
                    initial={{ opacity: 0, scale: 0.92, y: 4 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.92, y: 4 }}
                    transition={transition({ duration: 0.2 })}
                    className="min-w-[120px] liquid-glass rounded-2xl py-2 px-1"
                  >
                    {item.children!.map((child) => (
                      <button
                        key={child.label}
                        onClick={() => {
                          navigate(child.href);
                          setOpen(false);
                        }}
                        className="block w-full text-left px-4 py-2 text-sm text-foreground/80 font-body hover:text-foreground hover:bg-foreground/[0.05] rounded-xl transition-colors whitespace-nowrap"
                      >
                        {child.label}
                      </button>
                    ))}
                  </motion.div>
                </div>
              )}
            </AnimatePresence>
          </div>,
          document.body
        )
      : null;

  return (
    <div
      ref={triggerRef}
      onMouseEnter={item.trigger === "hover" ? handleEnter : undefined}
      onMouseLeave={item.trigger === "hover" ? handleLeave : undefined}
      className="flex items-center"
    >
      {item.trigger === "arrow" ? (
        <>
          <button
            onClick={handleClick}
            className="px-3 py-2 text-sm font-medium text-foreground/90 font-body hover:text-foreground transition-colors whitespace-nowrap"
          >
            {item.label}
          </button>
          <button
            type="button"
            aria-label={`展开${item.label}菜单`}
            onClick={handleArrowToggle}
            className="flex items-center justify-center pr-3 text-foreground/75 transition-colors hover:text-foreground"
          >
            <ChevronDown
              className={`h-3.5 w-3.5 shrink-0 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
            />
          </button>
        </>
      ) : (
        <button
          onClick={handleClick}
          className="px-3 py-2 text-sm font-medium text-foreground/90 font-body hover:text-foreground transition-colors flex items-center gap-1 whitespace-nowrap"
        >
          {item.label}
          {item.children ? (
            <ChevronDown
              className={`h-3.5 w-3.5 shrink-0 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
            />
          ) : null}
        </button>
      )}
      {menu}
    </div>
  );
};

const Navbar = () => {
  const navigate = useNavigate();
  const [visible, setVisible] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mobileExpanded, setMobileExpanded] = useState<string | null>(null);
  const lastScrollY = useRef(0);
  const prefersReducedMotion = useReducedMotionPreference();

  useEffect(() => {
    const scrollContainer =
      document.querySelector("[data-home-scroll]") || window;

    const getScrollY = () => {
      if (scrollContainer instanceof Window) return window.scrollY;
      return (scrollContainer as HTMLElement).scrollTop;
    };

    const handleScroll = () => {
      const currentY = getScrollY();
      const delta = currentY - lastScrollY.current;

      if (delta > 8 && currentY > 80) {
        setVisible(false);
      } else if (delta < -4) {
        setVisible(true);
      }

      lastScrollY.current = currentY;
    };

    scrollContainer.addEventListener("scroll", handleScroll, { passive: true });
    return () => scrollContainer.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    if (!mobileOpen) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleResize = () => {
      if (window.innerWidth >= 768) {
        setMobileOpen(false);
      }
    };

    window.addEventListener("resize", handleResize);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("resize", handleResize);
    };
  }, [mobileOpen]);

  const goTo = (path: string) => {
    setMobileOpen(false);
    setMobileExpanded(null);
    navigate(path);
  };

  const mobileMenu =
    typeof document !== "undefined"
      ? createPortal(
          <AnimatePresence>
            {mobileOpen && (
              <div className="fixed inset-0 z-[1000] md:hidden">
                <motion.button
                  type="button"
                  aria-label="关闭导航菜单"
                  className="absolute inset-0 bg-black/30 backdrop-blur-[2px]"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={transition({ duration: 0.2, reducedMotion: prefersReducedMotion })}
                  onClick={() => setMobileOpen(false)}
                />

                <motion.div
                  id="mobile-navigation"
                  initial={{ opacity: 0, y: -12, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -12, scale: 0.98 }}
                  transition={transition({ duration: 0.22, reducedMotion: prefersReducedMotion })}
                  className="absolute left-4 top-16 max-w-[16rem] liquid-glass-strong rounded-[28px] p-4 shadow-[0_18px_50px_rgba(0,0,0,0.14)]"
                >
                  <div className="grid gap-2">
                    {siteConfig.navigation.map((item) =>
                      item.children ? (
                        <div key={item.label} className="rounded-2xl bg-foreground/[0.03] overflow-hidden">
                          <div className="flex items-center">
                            <button type="button" onClick={() => {
                              if (item.trigger === "arrow" && item.href) { goTo(item.href); }
                              else { setMobileExpanded((prev) => prev === item.label ? null : item.label); }
                            }} className="flex-1 px-4 py-3 text-left text-sm font-body font-medium text-foreground/80 transition-colors hover:text-foreground">
                              {item.label}
                            </button>
                            <button type="button" aria-label={`展开${item.label}`}
                              onClick={() => setMobileExpanded((prev) => prev === item.label ? null : item.label)}
                              className="flex h-full items-center px-4 py-3 text-foreground/30 hover:text-foreground/60 transition-colors">
                              <ChevronDown className={`h-4 w-4 transition-transform duration-200 ${mobileExpanded === item.label ? "rotate-180" : ""}`} />
                            </button>
                          </div>
                          <AnimatePresence>
                            {mobileExpanded === item.label && (
                              <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                                transition={transition({ duration: 0.3, reducedMotion: prefersReducedMotion })} className="overflow-hidden">
                                <div className="px-2 pb-2 grid gap-0.5">
                                  {item.children!.map((child) => (
                                    <button key={child.label} type="button" onClick={() => goTo(child.href)}
                                      className="rounded-xl px-3 py-2.5 text-left text-sm font-body text-foreground/60 transition-colors hover:bg-foreground/[0.05] hover:text-foreground/80">
                                      {child.label}
                                    </button>
                                  ))}
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      ) : (
                        <button key={item.label} type="button" onClick={() => item.href && goTo(item.href)}
                          className="rounded-2xl px-4 py-3 text-left text-sm font-body font-medium text-foreground/80 transition-colors hover:bg-foreground/[0.04] hover:text-foreground">
                          {item.label}
                        </button>
                      )
                    )}
                  </div>
                </motion.div>
              </div>
            )}
          </AnimatePresence>,
          document.body
        )
      : null;

  return (
    <motion.nav
      className="fixed top-4 left-0 right-0 z-[999] px-4 sm:px-6 lg:px-16"
      initial={{ y: 0, opacity: 1 }}
      animate={{
        y: visible ? 0 : -80,
        opacity: visible ? 1 : 0,
      }}
      transition={transition({ duration: 0.35, reducedMotion: prefersReducedMotion })}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="w-9 md:w-9">
          <button
            type="button"
            aria-label="打开导航菜单"
            aria-expanded={mobileOpen}
            aria-controls="mobile-navigation"
            onClick={() => setMobileOpen((v) => !v)}
            className="flex h-9 w-9 items-center justify-center rounded-full liquid-glass text-foreground/60 hover:text-foreground transition-colors active:scale-95 md:hidden"
          >
            {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>

        <div className="hidden md:flex items-center liquid-glass rounded-full px-2 py-1.5 gap-1">
          {siteConfig.navigation.map((item) =>
            item.children ? (
              <NavDropdown key={item.label} item={item} navigate={goTo} />
            ) : (
              <button
                key={item.label}
                onClick={() => item.href && goTo(item.href)}
                className="px-3 py-2 text-sm font-medium text-foreground/90 font-body hover:text-foreground transition-colors whitespace-nowrap"
              >
                {item.label}
              </button>
            )
          )}
        </div>

        <div className="mr-1 md:mr-0"><ThemeToggle /></div>
      </div>
      {mobileMenu}
    </motion.nav>
  );
};

export default Navbar;
