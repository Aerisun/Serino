import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const BaseIcon = ({
  children,
  strokeWidth = 1.8,
  viewBox = "0 0 24 24",
  fill = "none",
  className,
  ...props
}: IconProps) => (
  <svg
    viewBox={viewBox}
    fill={fill}
    stroke="currentColor"
    strokeWidth={strokeWidth}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
    {...props}
  >
    {children}
  </svg>
);

export const Search = (props: IconProps) => (
  <BaseIcon {...props}>
    <circle cx="11" cy="11" r="6.5" />
    <path d="M16 16l4 4" />
  </BaseIcon>
);

export const Menu = (props: IconProps) => (
  <BaseIcon {...props}>
    <path d="M4 7h16" />
    <path d="M4 12h16" />
    <path d="M4 17h16" />
  </BaseIcon>
);

export const X = (props: IconProps) => (
  <BaseIcon {...props}>
    <path d="M6 6l12 12" />
    <path d="M18 6L6 18" />
  </BaseIcon>
);

export const ChevronDown = (props: IconProps) => (
  <BaseIcon {...props}>
    <path d="M6 9l6 6 6-6" />
  </BaseIcon>
);

export const Sparkles = (props: IconProps) => (
  <BaseIcon {...props}>
    <path d="M12 3l1.4 3.6L17 8l-3.6 1.4L12 13l-1.4-3.6L7 8l3.6-1.4L12 3z" />
    <path d="M18.5 13.5l.8 2 .2.5.5.2 2 .8-2 .8-.5.2-.2.5-.8 2-.8-2-.2-.5-.5-.2-2-.8 2-.8.5-.2.2-.5.8-2z" />
    <path d="M5.5 14.5l.7 1.6.2.4.4.2 1.6.7-1.6.7-.4.2-.2.4-.7 1.6-.7-1.6-.2-.4-.4-.2-1.6-.7 1.6-.7.4-.2.2-.4.7-1.6z" />
  </BaseIcon>
);

export const PencilLine = (props: IconProps) => (
  <BaseIcon {...props}>
    <path d="M4 20h4l10-10-4-4L4 16v4z" />
    <path d="M13.5 5.5l4 4" />
    <path d="M14 20h6" />
  </BaseIcon>
);

export const LogOut = (props: IconProps) => (
  <BaseIcon {...props}>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <path d="M16 17l5-5-5-5" />
    <path d="M21 12H9" />
  </BaseIcon>
);

export const BellRing = (props: IconProps) => (
  <BaseIcon {...props}>
    <path d="M15 18H5.8a1 1 0 0 1-.8-1.6L6 15V11a6 6 0 1 1 12 0v4l1 1.4a1 1 0 0 1-.8 1.6H15" />
    <path d="M10 20a2 2 0 0 0 4 0" />
    <path d="M18.5 4.5a3.5 3.5 0 0 1 1.5 2.5" />
    <path d="M5.5 4.5A3.5 3.5 0 0 0 4 7" />
  </BaseIcon>
);

export const Sun = (props: IconProps) => (
  <BaseIcon {...props}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2.5" />
    <path d="M12 19.5V22" />
    <path d="M4.9 4.9l1.8 1.8" />
    <path d="M17.3 17.3l1.8 1.8" />
    <path d="M2 12h2.5" />
    <path d="M19.5 12H22" />
    <path d="M4.9 19.1l1.8-1.8" />
    <path d="M17.3 6.7l1.8-1.8" />
  </BaseIcon>
);

export const Moon = (props: IconProps) => (
  <BaseIcon {...props}>
    <path d="M20 14.2A8.5 8.5 0 1 1 9.8 4a7 7 0 0 0 10.2 10.2z" />
  </BaseIcon>
);

export const Monitor = (props: IconProps) => (
  <BaseIcon {...props}>
    <rect x="3" y="4" width="18" height="13" rx="2" />
    <path d="M8 20h8" />
    <path d="M12 17v3" />
  </BaseIcon>
);

export const Check = (props: IconProps) => (
  <BaseIcon {...props}>
    <path d="M5 12.5l4.2 4.2L19 7.4" />
  </BaseIcon>
);

export const BellOff = (props: IconProps) => (
  <BaseIcon {...props}>
    <path d="M4 4l16 16" />
    <path d="M8 8.4V7a4 4 0 0 1 7.1-2.5" />
    <path d="M18 15V11a5.7 5.7 0 0 0-.6-2.5" />
    <path d="M6 15l-1 1.4a1 1 0 0 0 .8 1.6H15" />
    <path d="M10 20a2 2 0 0 0 4 0" />
  </BaseIcon>
);

export const Github = ({ className, ...props }: IconProps) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true" {...props}>
    <path d="M12 2C6.48 2 2 6.48 2 12a10 10 0 0 0 6.84 9.49c.5.09.68-.21.68-.47v-1.66c-2.78.6-3.37-1.18-3.37-1.18-.45-1.16-1.1-1.47-1.1-1.47-.9-.62.07-.6.07-.6 1 .07 1.52 1.02 1.52 1.02.88 1.52 2.31 1.08 2.87.83.09-.64.34-1.08.61-1.33-2.22-.25-4.56-1.11-4.56-4.94 0-1.09.39-1.98 1.02-2.68-.1-.25-.44-1.27.1-2.64 0 0 .84-.27 2.75 1.02a9.4 9.4 0 0 1 5 0c1.91-1.29 2.75-1.02 2.75-1.02.54 1.37.2 2.39.1 2.64.63.7 1.02 1.59 1.02 2.68 0 3.84-2.35 4.69-4.58 4.94.35.31.67.91.67 1.85v2.74c0 .26.18.57.69.47A10 10 0 0 0 22 12c0-5.52-4.48-10-10-10z" />
  </svg>
);

export const Lock = (props: IconProps) => (
  <BaseIcon {...props}>
    <rect x="5" y="10" width="14" height="10" rx="2" />
    <path d="M8 10V7.5a4 4 0 1 1 8 0V10" />
  </BaseIcon>
);

export const Loader2 = (props: IconProps) => (
  <BaseIcon {...props}>
    <path d="M12 3a9 9 0 1 0 9 9" />
  </BaseIcon>
);

export const Mail = (props: IconProps) => (
  <BaseIcon {...props}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="M4.5 7l7.5 6 7.5-6" />
  </BaseIcon>
);

export const RefreshCcw = (props: IconProps) => (
  <BaseIcon {...props}>
    <path d="M3 12a9 9 0 0 1 15.3-6.4L21 8" />
    <path d="M21 3v5h-5" />
    <path d="M21 12a9 9 0 0 1-15.3 6.4L3 16" />
    <path d="M3 21v-5h5" />
  </BaseIcon>
);

export const UserRoundPen = (props: IconProps) => (
  <BaseIcon {...props}>
    <circle cx="10" cy="8" r="3.5" />
    <path d="M4 19a6 6 0 0 1 10.6-3.8" />
    <path d="M15.5 21l5-5" />
    <path d="M18.5 13.5l2 2" />
  </BaseIcon>
);

export const Globe = (props: IconProps) => (
  <BaseIcon {...props}>
    <circle cx="12" cy="12" r="9" />
    <path d="M3.5 12h17" />
    <path d="M12 3a14 14 0 0 1 0 18" />
    <path d="M12 3a14 14 0 0 0 0 18" />
  </BaseIcon>
);

export const Link2 = (props: IconProps) => (
  <BaseIcon {...props}>
    <path d="M10 14l4-4" />
    <path d="M7.5 16.5l-1.8 1.8a3 3 0 1 1-4.2-4.2l3.1-3.1a3 3 0 0 1 4.2 0" />
    <path d="M16.5 7.5l1.8-1.8a3 3 0 1 1 4.2 4.2l-3.1 3.1a3 3 0 0 1-4.2 0" />
  </BaseIcon>
);

export const Phone = (props: IconProps) => (
  <BaseIcon {...props}>
    <path d="M6.5 4.5l3 3-1.9 1.9a13 13 0 0 0 7 7l1.9-1.9 3 3-1.7 1.7a2 2 0 0 1-2 .5A18 18 0 0 1 5.8 6.2a2 2 0 0 1 .5-2L6.5 4.5z" />
  </BaseIcon>
);

export const CalendarDays = (props: IconProps) => (
  <BaseIcon {...props}>
    <rect x="3" y="5" width="18" height="16" rx="2" />
    <path d="M16 3v4" />
    <path d="M8 3v4" />
    <path d="M3 10h18" />
    <path d="M8 14h.01" />
    <path d="M12 14h.01" />
    <path d="M16 14h.01" />
  </BaseIcon>
);
