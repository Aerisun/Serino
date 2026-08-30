export interface ImageTransitionRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface ImageTransitionFrame {
  transform: string;
  clipPath: string;
}

interface ImageTransitionInput {
  originRect: ImageTransitionRect;
  previewRect: ImageTransitionRect;
  objectPosition: string;
  originBorderRadius: number;
  previewBorderRadius: number;
}

interface ImageTransitionKeyframes {
  open: [ImageTransitionFrame, ImageTransitionFrame];
  close: [ImageTransitionFrame, ImageTransitionFrame];
}

interface InterruptedCloseTransitionInput {
  currentFrame: ImageTransitionFrame;
  originFrame: ImageTransitionFrame;
  openProgress: number | null;
  fullDuration: number;
}

const clampUnit = (value: number) => Math.min(1, Math.max(0, value));

const parsePercentage = (value: string) => {
  const match = value.match(/^(-?\d+(?:\.\d+)?)%$/);
  return match ? clampUnit(Number(match[1]) / 100) : null;
};

export const parseObjectPosition = (value: string) => {
  const tokens = value.trim().toLowerCase().split(/\s+/).filter(Boolean).slice(0, 2);
  if (tokens.length === 0) return { x: 0.5, y: 0.5 };

  let x: number | null = null;
  let y: number | null = null;

  for (const token of tokens) {
    if (token === "left") x = 0;
    else if (token === "right") x = 1;
    else if (token === "top") y = 0;
    else if (token === "bottom") y = 1;
  }

  tokens.forEach((token, index) => {
    const percentage = parsePercentage(token);
    if (percentage !== null) {
      if (index === 0) x = percentage;
      else y = percentage;
      return;
    }

    if (token !== "center") return;
    if (index === 0 && x === null && (tokens.length === 1 || y !== null)) {
      x = 0.5;
    } else if (index === 0 && y === null && x !== null) {
      y = 0.5;
    } else if (index === 1 && y === null) {
      y = 0.5;
    } else if (x === null) {
      x = 0.5;
    }
  });

  const hasRecognizedToken = tokens.some((token) =>
    token === "left"
    || token === "right"
    || token === "top"
    || token === "bottom"
    || token === "center"
    || parsePercentage(token) !== null,
  );
  if (!hasRecognizedToken) return { x: 0.5, y: 0.5 };

  return { x: x ?? 0.5, y: y ?? 0.5 };
};

const isValidRect = (rect: ImageTransitionRect) => {
  return Number.isFinite(rect.left)
    && Number.isFinite(rect.top)
    && Number.isFinite(rect.width)
    && Number.isFinite(rect.height)
    && rect.width > 0
    && rect.height > 0;
};

const normalizeRadius = (value: number) => Number.isFinite(value) ? Math.max(0, value) : 0;

const formatNumber = (value: number) => {
  const rounded = Math.abs(value) < 0.00005 ? 0 : Number(value.toFixed(4));
  return String(rounded);
};

const formatInset = (top: number, right: number, bottom: number, left: number, radius: number) => {
  return `inset(${formatNumber(top)}px ${formatNumber(right)}px ${formatNumber(bottom)}px ${formatNumber(left)}px round ${formatNumber(radius)}px)`;
};

export const buildInterruptedCloseTransition = ({
  currentFrame,
  originFrame,
  openProgress,
  fullDuration,
}: InterruptedCloseTransitionInput) => {
  const progress = openProgress === null || !Number.isFinite(openProgress)
    ? 1
    : clampUnit(openProgress);
  const duration = Number.isFinite(fullDuration) && fullDuration > 0
    ? Math.max(1, fullDuration * progress)
    : 1;

  return {
    keyframes: [currentFrame, originFrame] as [ImageTransitionFrame, ImageTransitionFrame],
    duration,
  };
};

export const buildImageTransitionKeyframes = ({
  originRect,
  previewRect,
  objectPosition,
  originBorderRadius,
  previewBorderRadius,
}: ImageTransitionInput): ImageTransitionKeyframes | null => {
  if (!isValidRect(originRect) || !isValidRect(previewRect)) return null;

  const position = parseObjectPosition(objectPosition);
  const scale = Math.max(
    originRect.width / previewRect.width,
    originRect.height / previewRect.height,
  );
  const scaledWidth = previewRect.width * scale;
  const scaledHeight = previewRect.height * scale;
  const imageLeft = originRect.left - (scaledWidth - originRect.width) * position.x;
  const imageTop = originRect.top - (scaledHeight - originRect.height) * position.y;
  const translateX = imageLeft - previewRect.left;
  const translateY = imageTop - previewRect.top;

  const clipLeft = Math.max(0, (originRect.left - imageLeft) / scale);
  const clipTop = Math.max(0, (originRect.top - imageTop) / scale);
  const clipRight = Math.max(
    0,
    previewRect.width - (originRect.left + originRect.width - imageLeft) / scale,
  );
  const clipBottom = Math.max(
    0,
    previewRect.height - (originRect.top + originRect.height - imageTop) / scale,
  );

  const originFrame: ImageTransitionFrame = {
    transform: `translate3d(${formatNumber(translateX)}px, ${formatNumber(translateY)}px, 0) scale(${formatNumber(scale)})`,
    clipPath: formatInset(
      clipTop,
      clipRight,
      clipBottom,
      clipLeft,
      normalizeRadius(originBorderRadius) / scale,
    ),
  };
  const previewFrame: ImageTransitionFrame = {
    transform: "translate3d(0px, 0px, 0) scale(1)",
    clipPath: formatInset(0, 0, 0, 0, normalizeRadius(previewBorderRadius)),
  };

  return {
    open: [originFrame, previewFrame],
    close: [previewFrame, originFrame],
  };
};
