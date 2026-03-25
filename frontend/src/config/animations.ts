const ease = {
  smooth: [0.16, 1, 0.3, 1] as const,
  bounce: [0.34, 1.56, 0.64, 1] as const,
};

const duration = {
  fast: 0.2,
  normal: 0.4,
  slow: 0.55,
  expand: 0.3,
  modal: 0.35,
} as const;

const reducedMotionTiming = {
  duration: 0,
  delay: 0,
  ease: ease.smooth,
} as const;

type MotionSettings = {
  duration?: number;
  delay?: number;
  reducedMotion?: boolean;
  ease?: readonly [number, number, number, number];
};

export const transition = ({
  duration: customDuration = duration.normal,
  delay = 0,
  reducedMotion = false,
  ease: customEase = ease.smooth,
}: MotionSettings = {}) =>
  reducedMotion
    ? reducedMotionTiming
    : { duration: customDuration, delay, ease: customEase };

export const pageEntrance = (reducedMotion = false) => ({
  initial: { opacity: 0, y: reducedMotion ? 0 : 16 },
  animate: { opacity: 1, y: 0 },
  transition: transition({
    duration: duration.slow,
    reducedMotion,
  }),
});

export const staggerItem = (
  index: number,
  {
    baseDelay = 0.06,
    step = 0.04,
    duration: itemDuration = duration.normal,
    reducedMotion = false,
  }: {
    baseDelay?: number;
    step?: number;
    duration?: number;
    reducedMotion?: boolean;
  } = {}
) => ({
  initial: { opacity: 0, y: reducedMotion ? 0 : 14 },
  animate: { opacity: 1, y: 0 },
  transition: transition({
    duration: itemDuration,
    delay: reducedMotion ? 0 : baseDelay + index * step,
    reducedMotion,
  }),
});
