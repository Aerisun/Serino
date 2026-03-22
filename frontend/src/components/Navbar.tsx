import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { useLocation, useNavigate } from "react-router-dom";
import { ChevronDown, Menu, X, Search } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import ThemeToggle from "@/components/ThemeToggle";
import { transition } from "@/config";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";
import { useSiteConfig } from "@/contexts/RuntimeConfigContext";
import type { NavItem } from "@/lib/runtime-config";

type NavbarGlassVariant = "default" | "hero";

const isPathActive = (href: string | undefined, pathname: string) => {
  if (!href) return false;
  if (href === "/") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
};

const getItemIsActive = (item: NavItem, pathname: string) =>
  isPathActive(item.href, pathname) ||
  item.children?.some((child) => isPathActive(child.href, pathname)) ||
  false;

const NavDropdown = ({
  item,
  navigate,
  pathname,
  glassVariant,
}: {
  item: NavItem;
  navigate: (path: string) => void;
  pathname: string;
  glassVariant: NavbarGlassVariant;
}) => {
  const [open, setOpen] = useState(false);
  const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0 });
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const triggerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuGlassClass = glassVariant === "hero" ? "liquid-glass-hero" : "liquid-glass";
  const itemTextClass =
    glassVariant === "hero"
      ? "text-white/82 hover:text-white"
      : "text-foreground/88 hover:text-[rgb(var(--shiro-accent-rgb)/0.68)]";
  const arrowTextClass =
    glassVariant === "hero"
      ? "text-white/68 hover:text-white"
      : "text-foreground/72 hover:text-[rgb(var(--shiro-accent-rgb)/0.6)]";
  const dropdownItemClass =
    glassVariant === "hero"
      ? "text-white/80 hover:bg-white/10 hover:text-white"
      : "text-foreground/78 hover:bg-[rgb(var(--shiro-panel-rgb)/0.34)] hover:text-[rgb(var(--shiro-accent-rgb)/0.74)]";

  const updateMenuPosition = useCallback(() => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    setMenuPosition({
      top: rect.bottom,
      left: rect.left + rect.width / 2,
    });
  }, []);

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

  const isActive = getItemIsActive(item, pathname);

  const menu =
    typeof document !== "undefined"
      ? createPortal(
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
                  className={`min-w-[128px] rounded-2xl border py-2 px-1 shadow-[0_18px_48px_rgba(15,23,42,0.12)] ${menuGlassClass}`}
                  style={{ borderColor: "rgb(var(--shiro-border-rgb) / 0.42)" }}
                >
                  {item.children!.map((child) => (
                    <button
                      key={child.label}
                      onClick={() => {
                        navigate(child.href);
                        setOpen(false);
                      }}
                      className={`block w-full rounded-xl px-4 py-2 text-left text-sm font-body transition-colors whitespace-nowrap ${dropdownItemClass}`}
                    >
                      {child.label}
                    </button>
                  ))}
                </motion.div>
              </div>
            )}
          </AnimatePresence>,
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
        <div className="relative flex items-center">
          <button
            onClick={handleClick}
            className={`px-3 py-2 text-sm font-medium font-body transition-colors whitespace-nowrap ${
              isActive
                ? "text-[rgb(var(--shiro-accent-rgb)/0.82)]"
                : itemTextClass
            }`}
          >
            {item.label}
          </button>
          <button
            type="button"
            aria-label={`展开${item.label}菜单`}
            onClick={handleArrowToggle}
            className={`flex items-center justify-center pr-3 transition-colors ${
              isActive
                ? "text-[rgb(var(--shiro-accent-rgb)/0.72)]"
                : arrowTextClass
            }`}
          >
            <ChevronDown
              className={`h-3.5 w-3.5 shrink-0 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
            />
          </button>
          {isActive ? (
            <span className="pointer-events-none absolute inset-x-4 bottom-[4px] h-px bg-gradient-to-r from-transparent via-[rgb(var(--shiro-accent-rgb)/0.44)] to-transparent" />
          ) : null}
        </div>
      ) : (
        <button
          onClick={handleClick}
          className={`relative px-3 py-2 text-sm font-medium font-body transition-colors flex items-center gap-1 whitespace-nowrap ${
            isActive
              ? "text-[rgb(var(--shiro-accent-rgb)/0.82)]"
              : itemTextClass
          }`}
        >
          {item.label}
          {item.children ? (
            <ChevronDown
              className={`h-3.5 w-3.5 shrink-0 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
            />
          ) : null}
          {isActive ? (
            <span className="pointer-events-none absolute inset-x-4 bottom-[4px] h-px bg-gradient-to-r from-transparent via-[rgb(var(--shiro-accent-rgb)/0.44)] to-transparent" />
          ) : null}
        </button>
      )}
      {menu}
    </div>
  );
};

interface NavbarProps {
  glassVariant?: NavbarGlassVariant;
}

const Navbar = ({ glassVariant = "default" }: NavbarProps) => {
  const navigate = useNavigate();
  const location = useLocation();
  const site = useSiteConfig();
  const [visible, setVisible] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mobileExpanded, setMobileExpanded] = useState<string | null>(null);
  const lastScrollY = useRef(0);
  const prefersReducedMotion = useReducedMotionPreference();
  const navGlassClass = glassVariant === "hero" ? "liquid-glass-hero" : "liquid-glass";
  const navStrongGlassClass =
    glassVariant === "hero" ? "liquid-glass-hero-strong" : "liquid-glass-strong";
  const navItemTextClass =
    glassVariant === "hero"
      ? "text-white/82 hover:text-white"
      : "text-foreground/88 hover:text-[rgb(var(--shiro-accent-rgb)/0.68)]";
  const mobileItemTextClass =
    glassVariant === "hero"
      ? "text-white/82 hover:text-white"
      : "text-foreground/80 hover:text-[rgb(var(--shiro-accent-rgb)/0.66)]";
  const mobileArrowTextClass =
    glassVariant === "hero"
      ? "text-white/48 hover:text-white/82"
      : "text-foreground/30 hover:text-[rgb(var(--shiro-accent-rgb)/0.56)]";
  const mobileChildTextClass =
    glassVariant === "hero"
      ? "text-white/68 hover:bg-white/10 hover:text-white"
      : "text-foreground/60 hover:bg-[rgb(var(--shiro-panel-rgb)/0.32)] hover:text-[rgb(var(--shiro-accent-rgb)/0.72)]";
  const mobileButtonTextClass =
    glassVariant === "hero"
      ? "text-white/72 hover:text-white"
      : "text-foreground/60 hover:text-[rgb(var(--shiro-accent-rgb)/0.68)]";

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
                  className={`absolute left-4 top-16 max-w-[16rem] overflow-hidden rounded-[28px] border p-4 shadow-[0_18px_50px_rgba(0,0,0,0.14)] ${navStrongGlassClass}`}
                  style={{ borderColor: "rgb(var(--shiro-border-rgb) / 0.44)" }}
                >
                  <div
                    className="pointer-events-none absolute inset-x-5 top-0 h-px"
                    style={{
                      background:
                        "linear-gradient(90deg, transparent, rgb(var(--shiro-accent-rgb) / 0.42), transparent)",
                    }}
                  />
                  <div className="grid gap-2">
                    {site.navigation.map((item) =>
                      item.children ? (
                        <div
                          key={item.label}
                          className="overflow-hidden rounded-2xl bg-[rgb(var(--shiro-panel-rgb)/0.26)]"
                        >
                          <div className="flex items-center">
                            <button type="button" onClick={() => {
                              if (item.trigger === "arrow" && item.href) { goTo(item.href); }
                              else { setMobileExpanded((prev) => prev === item.label ? null : item.label); }
                            }} className={`flex-1 px-4 py-3 text-left text-sm font-body font-medium transition-colors ${
                              getItemIsActive(item, location.pathname)
                                ? "text-[rgb(var(--shiro-accent-rgb)/0.8)]"
                                : mobileItemTextClass
                            }`}>
                              {item.label}
                            </button>
                            <button type="button" aria-label={`展开${item.label}`}
                              onClick={() => setMobileExpanded((prev) => prev === item.label ? null : item.label)}
                              className={`flex h-full items-center px-4 py-3 transition-colors ${mobileArrowTextClass}`}>
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
                                      className={`rounded-xl px-3 py-2.5 text-left text-sm font-body transition-colors ${
                                        isPathActive(child.href, location.pathname)
                                          ? glassVariant === "hero"
                                            ? "bg-white/12 text-white"
                                            : "bg-[rgb(var(--shiro-panel-rgb)/0.36)] text-[rgb(var(--shiro-accent-rgb)/0.76)]"
                                          : mobileChildTextClass
                                      }`}>
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
                          className={`rounded-2xl px-4 py-3 text-left text-sm font-body font-medium transition-colors ${
                            getItemIsActive(item, location.pathname)
                              ? glassVariant === "hero"
                                ? "bg-white/12 text-white"
                                : "bg-[rgb(var(--shiro-panel-rgb)/0.36)] text-[rgb(var(--shiro-accent-rgb)/0.76)]"
                              : glassVariant === "hero"
                                ? "text-white/82 hover:bg-white/10 hover:text-white"
                                : "text-foreground/80 hover:bg-[rgb(var(--shiro-panel-rgb)/0.32)] hover:text-[rgb(var(--shiro-accent-rgb)/0.72)]"
                          }`}>
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
            className={`flex h-9 w-9 items-center justify-center rounded-full transition-colors active:scale-95 md:hidden ${navGlassClass} ${mobileButtonTextClass}`}
          >
            {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>

        <div
          className={`relative hidden overflow-hidden md:flex items-center rounded-full px-2 py-1.5 gap-1 shadow-[0_18px_48px_rgba(15,23,42,0.08)] ${navGlassClass}`}
        >
          <div
            className="pointer-events-none absolute inset-x-5 top-0 h-px"
            style={{
              background:
                "linear-gradient(90deg, transparent, rgb(var(--shiro-accent-rgb) / 0.4), transparent)",
            }}
          />
          <div
            className="pointer-events-none absolute inset-0 opacity-90"
            style={{
              background:
                "radial-gradient(circle at 50% 0%, rgb(var(--shiro-glow-rgb) / 0.09), transparent 66%)",
            }}
          />
          {site.navigation.map((item) =>
            item.children ? (
              <NavDropdown
                key={item.label}
                item={item}
                navigate={goTo}
                pathname={location.pathname}
                glassVariant={glassVariant}
              />
            ) : (
              <button
                key={item.label}
                onClick={() => item.href && goTo(item.href)}
                className={`relative px-3 py-2 text-sm font-medium font-body transition-colors whitespace-nowrap ${
                  getItemIsActive(item, location.pathname)
                    ? "text-[rgb(var(--shiro-accent-rgb)/0.82)]"
                    : navItemTextClass
                }`}
              >
                {item.label}
                {getItemIsActive(item, location.pathname) ? (
                  <span className="pointer-events-none absolute inset-x-4 bottom-[4px] h-px bg-gradient-to-r from-transparent via-[rgb(var(--shiro-accent-rgb)/0.44)] to-transparent" />
                ) : null}
              </button>
            )
          )}
        </div>

        <div className="flex items-center gap-2 mr-1 md:mr-0">
          <button
            type="button"
            onClick={() => window.dispatchEvent(new CustomEvent("aerisun:open-search"))}
            className="flex items-center justify-center h-8 w-8 rounded-full text-foreground/30 hover:text-foreground/60 transition-colors"
            aria-label="搜索"
          >
            <Search className="h-4 w-4" />
          </button>
          <ThemeToggle glassVariant={glassVariant} />
        </div>
      </div>
      {mobileMenu}
    </motion.nav>
  );
};

export default Navbar;
