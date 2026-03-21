import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { ChevronDown } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import ThemeToggle from "@/components/ThemeToggle";
import logo from "@/assets/logo.png";

interface NavItem {
  label: string;
  trigger: "hover" | "click" | "none";
  children?: { label: string; href: string }[];
  href?: string;
}

const navItems: NavItem[] = [
  {
    label: "首页",
    trigger: "hover",
    href: "/",
    children: [
      { label: "简介", href: "/#about" },
      { label: "历史", href: "/#history" },
    ],
  },
  { label: "帖子", trigger: "none", href: "/posts" },
  { label: "友链", trigger: "none", href: "/friends" },
  {
    label: "更多",
    trigger: "click",
    children: [
      { label: "碎碎念", href: "/thoughts" },
      { label: "日记", href: "/diary" },
      { label: "文摘", href: "/excerpts" },
      { label: "项目", href: "/projects" },
    ],
  },
];

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
  const triggerRef = useRef<HTMLButtonElement>(null);
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
    if (item.trigger === "click") {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      if (!open) updateMenuPosition();
      setOpen((v) => !v);
    }
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
                    transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
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
    <div onMouseEnter={handleEnter} onMouseLeave={handleLeave}>
      <button
        ref={triggerRef}
        onClick={handleClick}
        className="px-3 py-2 text-sm font-medium text-foreground/90 font-body hover:text-foreground transition-colors flex items-center gap-1 whitespace-nowrap"
      >
        {item.label}
        <ChevronDown
          className={`h-3.5 w-3.5 shrink-0 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>
      {menu}
    </div>
  );
};

const Navbar = () => {
  const navigate = useNavigate();
  const [visible, setVisible] = useState(true);
  const lastScrollY = useRef(0);

  useEffect(() => {
    const scrollContainer =
      document.querySelector(".h-screen.overflow-y-auto") || window;

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

  return (
    <motion.nav
      className="fixed top-4 left-0 right-0 z-[100] px-8 lg:px-16"
      initial={{ y: 0, opacity: 1 }}
      animate={{
        y: visible ? 0 : -80,
        opacity: visible ? 1 : 0,
      }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="flex items-center justify-between">
        <button onClick={() => navigate("/")} className="shrink-0 active:scale-[0.97]">
          <img src={logo} alt="Logo" className="h-12 w-12" />
        </button>

        <div className="hidden md:flex items-center liquid-glass rounded-full px-2 py-1.5 gap-1">
          {navItems.map((item) =>
            item.children ? (
              <NavDropdown key={item.label} item={item} navigate={navigate} />
            ) : (
              <button
                key={item.label}
                onClick={() => navigate(item.href || "/")}
                className="px-3 py-2 text-sm font-medium text-foreground/90 font-body hover:text-foreground transition-colors whitespace-nowrap"
              >
                {item.label}
              </button>
            )
          )}
        </div>

        <ThemeToggle />
      </div>
    </motion.nav>
  );
};

export default Navbar;
