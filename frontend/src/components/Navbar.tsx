import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { useLocation, useNavigate } from "react-router-dom";
import { ChevronDown, LogOut, Menu, PencilLine, Search, Sparkles, X } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import ThemeToggle from "@/components/ThemeToggle";
import { transition } from "@/config";
import { useSiteAuth } from "@/contexts/use-site-auth";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";
import { useSiteConfig } from "@/contexts/runtime-config";
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

const authProviderLabel = (provider: string) =>
  provider === "google" ? "Google" : provider === "github" ? "GitHub" : "邮箱识别";

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
  const [authMenuOpen, setAuthMenuOpen] = useState(false);
  const lastScrollY = useRef(0);
  const authMenuRef = useRef<HTMLDivElement | null>(null);
  const prefersReducedMotion = useReducedMotionPreference();
  const { user, openLogin, openProfileEditor, logout } = useSiteAuth();
  const navGlassClass = glassVariant === "hero" ? "liquid-glass-hero" : "liquid-glass";
  const navStrongGlassClass =
    glassVariant === "hero" ? "liquid-glass-hero-strong" : "liquid-glass-strong";
  const iconButtonGlassClass = glassVariant === "hero" ? "liquid-glass-hero" : "liquid-glass";
  const iconButtonToneClass =
    glassVariant === "hero"
      ? "text-white/72 hover:text-white"
      : "text-foreground/60 hover:text-foreground";
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

  useEffect(() => {
    if (!authMenuOpen) return;

    const handler = (event: MouseEvent) => {
      if (!authMenuRef.current?.contains(event.target as Node)) {
        setAuthMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [authMenuOpen]);

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
      <div className="flex items-center justify-between gap-3 md:grid md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] md:items-center md:gap-0">
        <div className="flex items-center gap-2 md:justify-self-start">
          <div className="relative flex items-center" ref={authMenuRef}>
            {user ? (
              <>
                <button
                  type="button"
                  onClick={() => setAuthMenuOpen((current) => !current)}
                  aria-label={`${user.effective_display_name} 账户菜单`}
                  className={`inline-flex h-9 w-9 items-center justify-center overflow-hidden rounded-full border px-0 transition-all sm:w-auto sm:justify-start sm:gap-2 sm:px-2.5 sm:pr-3 ${navGlassClass} ${
                    glassVariant === "hero"
                      ? "border-white/14 text-white/86 hover:text-white"
                      : "border-[rgb(var(--shiro-border-rgb)/0.22)] text-foreground/76 hover:text-foreground"
                  }`}
                >
                  <img
                    src={user.effective_avatar_url}
                    alt={user.effective_display_name}
                    className="h-6 w-6 shrink-0 rounded-full object-cover ring-1 ring-black/5"
                  />
                  <span className="hidden text-sm font-medium sm:inline">{user.effective_display_name}</span>
                  {user.is_admin ? (
                    <span className="hidden rounded-full border border-[rgb(var(--shiro-accent-rgb)/0.2)] bg-[rgb(var(--shiro-accent-rgb)/0.08)] px-2 py-0.5 text-[0.66rem] font-semibold text-[rgb(var(--shiro-accent-rgb)/0.88)] sm:inline-flex">
                      Admin
                    </span>
                  ) : null}
                </button>
                <AnimatePresence>
                  {authMenuOpen ? (
                    <motion.div
                      initial={{ opacity: 0, y: -8, scale: 0.96 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: -8, scale: 0.96 }}
                      transition={transition({ duration: 0.18, reducedMotion: prefersReducedMotion })}
                      className={`absolute left-0 top-[calc(100%+0.75rem)] w-60 overflow-hidden rounded-[1.35rem] border p-2 shadow-[0_20px_60px_rgba(15,23,42,0.16)] ${navStrongGlassClass}`}
                      style={{ borderColor: "rgb(var(--shiro-border-rgb) / 0.34)" }}
                    >
                      <div className="px-3 py-2">
                        <div className="text-sm font-semibold text-foreground">{user.effective_display_name}</div>
                        <div className="mt-1 text-xs text-foreground/46">
                          {user.is_admin
                            ? `当前是管理员模式 · 来源：${authProviderLabel(user.primary_auth_provider)}`
                            : `当前身份来源：${authProviderLabel(user.primary_auth_provider)}`}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          openProfileEditor();
                          setAuthMenuOpen(false);
                        }}
                        className="flex w-full items-center gap-2 rounded-[1rem] px-3 py-2 text-left text-sm text-foreground/66 transition hover:bg-[rgb(var(--shiro-panel-rgb)/0.36)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)]"
                      >
                        <PencilLine className="h-4 w-4" />
                        修改资料
                      </button>
                      <button
                        type="button"
                        onClick={() => void logout().then(() => setAuthMenuOpen(false))}
                        className="flex w-full items-center gap-2 rounded-[1rem] px-3 py-2 text-left text-sm text-foreground/66 transition hover:bg-[rgb(var(--shiro-panel-rgb)/0.36)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)]"
                      >
                        <LogOut className="h-4 w-4" />
                        退出登录
                      </button>
                    </motion.div>
                  ) : null}
                </AnimatePresence>
              </>
            ) : (
              <button
                type="button"
                onClick={openLogin}
                className={[
                  "group relative inline-flex h-9 items-center gap-2 overflow-hidden rounded-full px-3.5 text-sm font-medium transition-all active:scale-[0.98]",
                  glassVariant === "hero"
                    ? "liquid-glass-hero text-white"
                    : "liquid-glass text-[rgb(var(--shiro-accent-rgb)/0.92)]",
                ].join(" ")}
              >
                <span className="absolute inset-0 rounded-full border border-white/10 bg-[linear-gradient(135deg,rgb(66_133_244/0.22),rgb(234_67_53/0.12),rgb(251_188_5/0.12),rgb(52_168_83/0.22))] opacity-80" />
                <span className="absolute -inset-x-2 top-1/2 h-6 -translate-y-1/2 bg-[radial-gradient(circle,_rgb(255_255_255/0.28),_transparent_58%)] opacity-0 blur-md transition-opacity group-hover:opacity-100" />
                <Sparkles className="relative h-4 w-4" />
                <span className="relative hidden sm:inline">登录</span>
              </button>
            )}
          </div>
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
          className={`relative hidden overflow-hidden md:flex md:justify-self-center items-center rounded-full px-2 py-1.5 gap-1 shadow-[0_18px_48px_rgba(15,23,42,0.08)] ${navGlassClass}`}
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

        <div className="relative flex items-center gap-2 mr-1 md:mr-0 md:justify-self-end">
          <button
            type="button"
            onClick={() => window.dispatchEvent(new CustomEvent("aerisun:open-search"))}
            className={`flex h-9 w-9 items-center justify-center rounded-full ${iconButtonGlassClass} ${iconButtonToneClass} transition-colors active:scale-95`}
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
