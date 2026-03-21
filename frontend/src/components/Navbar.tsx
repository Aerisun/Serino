import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { ChevronDown, Menu, X } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import ThemeToggle from "@/components/ThemeToggle";
import logo from "@/assets/logo.png";
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
                  className="fixed z-[200] pt-2"
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
      if (window.innerWidth < 768) {
        setVisible(true);
        return;
      }

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
    navigate(path);
  };

  const mobileMenu =
    typeof document !== "undefined"
      ? createPortal(
          <AnimatePresence>
            {mobileOpen && (
              <div className="fixed inset-0 z-[180] md:hidden">
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
                  className="absolute left-4 right-4 top-20 liquid-glass-strong rounded-[28px] p-4 shadow-[0_18px_50px_rgba(0,0,0,0.14)]"
                >
                  <div className="mb-4 flex items-center justify-between">
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.24em] text-foreground/30">
                        Navigation
                      </p>
                      <p className="mt-1 text-sm font-heading italic text-foreground/80">
                        {siteConfig.name}
                      </p>
                    </div>
                    <button
                      type="button"
                      aria-label="关闭导航菜单"
                      onClick={() => setMobileOpen(false)}
                      className="flex h-9 w-9 items-center justify-center rounded-full liquid-glass text-foreground/55"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>

                  <div className="grid gap-2">
                    {siteConfig.navigation.map((item) =>
                      item.children ? (
                        <div key={item.label} className="rounded-2xl bg-foreground/[0.02] p-3">
                          <button
                            type="button"
                            onClick={() => item.href && goTo(item.href)}
                            className="flex w-full items-center justify-between px-1 text-left text-sm font-body text-foreground/78"
                          >
                            <span>{item.label}</span>
                            <span className="text-[10px] uppercase tracking-[0.22em] text-foreground/22">
                              分组
                            </span>
                          </button>
                          <div className="mt-2 grid gap-1">
                            {item.children.map((child) => (
                              <button
                                key={child.label}
                                type="button"
                                onClick={() => goTo(child.href)}
                                className="flex items-center justify-between rounded-xl px-3 py-2 text-left text-sm font-body text-foreground/72 transition-colors hover:bg-foreground/[0.05]"
                              >
                                <span>{child.label}</span>
                                <span className="text-[10px] uppercase tracking-[0.2em] text-foreground/18">
                                  进入
                                </span>
                              </button>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <button
                          key={item.label}
                          type="button"
                          onClick={() => item.href && goTo(item.href)}
                          className="flex items-center justify-between rounded-2xl px-4 py-3 text-left text-sm font-body text-foreground/78 transition-colors hover:bg-foreground/[0.04]"
                        >
                          <span>{item.label}</span>
                          <span className="text-[10px] uppercase tracking-[0.22em] text-foreground/22">
                            入口
                          </span>
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
      className="fixed top-4 left-0 right-0 z-[100] px-4 sm:px-6 lg:px-16"
      initial={{ y: 0, opacity: 1 }}
      animate={{
        y: visible ? 0 : -80,
        opacity: visible ? 1 : 0,
      }}
      transition={transition({ duration: 0.35, reducedMotion: prefersReducedMotion })}
    >
      <div className="flex items-center justify-between gap-3">
        <button onClick={() => goTo("/")} className="shrink-0 active:scale-[0.97]">
          <img src={logo} alt="Logo" className="h-12 w-12" />
        </button>

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

        <div className="flex items-center gap-2">
          <ThemeToggle />
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
      </div>
      {mobileMenu}
    </motion.nav>
  );
};

export default Navbar;
