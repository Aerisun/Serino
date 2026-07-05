import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentPropsWithoutRef,
  type SyntheticEvent,
} from "react";

export const AVATAR_IMAGE_RETRY_PARAM = "_aerisun_img_retry";
const LOCAL_AVATAR_IMAGE_PATH_PREFIX = "/api/v1/avatars/";
const DEFAULT_MAX_RETRIES = 3;
const DEFAULT_RETRY_BASE_DELAY_MS = 350;
const MAX_RETRY_DELAY_MS = 2400;

function isRetryableImageSrc(src: string): boolean {
  return /^https?:\/\//i.test(src) || src.startsWith(LOCAL_AVATAR_IMAGE_PATH_PREFIX);
}

export function buildRetryableImageSrc(src: string, attempt: number): string {
  if (attempt <= 0 || !isRetryableImageSrc(src)) {
    return src;
  }

  try {
    const isLocalAvatar = src.startsWith(LOCAL_AVATAR_IMAGE_PATH_PREFIX);
    const url = new URL(src, "https://aerisun.local");
    url.searchParams.set(AVATAR_IMAGE_RETRY_PARAM, String(attempt));
    return isLocalAvatar ? `${url.pathname}${url.search}${url.hash}` : url.toString();
  } catch {
    return src;
  }
}

export function retryDelayForAttempt(
  attempt: number,
  baseDelayMs = DEFAULT_RETRY_BASE_DELAY_MS,
): number {
  const normalizedAttempt = Math.max(1, Math.floor(attempt));
  const normalizedBase = Math.max(1, Math.floor(baseDelayMs));
  return Math.min(
    normalizedBase * 2 ** (normalizedAttempt - 1),
    MAX_RETRY_DELAY_MS,
  );
}

type RetryableAvatarImageProps = Omit<
  ComponentPropsWithoutRef<"img">,
  "src"
> & {
  src: string;
  maxRetries?: number;
  retryBaseDelayMs?: number;
};

export function RetryableAvatarImage({
  src,
  maxRetries = DEFAULT_MAX_RETRIES,
  retryBaseDelayMs = DEFAULT_RETRY_BASE_DELAY_MS,
  referrerPolicy,
  decoding,
  onError,
  onLoad,
  ...props
}: RetryableAvatarImageProps) {
  const [attempt, setAttempt] = useState(0);
  const retryTimerRef = useRef<number | null>(null);

  useEffect(() => {
    setAttempt(0);
    if (retryTimerRef.current !== null) {
      window.clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
  }, [src]);

  useEffect(
    () => () => {
      if (retryTimerRef.current !== null) {
        window.clearTimeout(retryTimerRef.current);
      }
    },
    [],
  );

  const imageSrc = useMemo(
    () => buildRetryableImageSrc(src, attempt),
    [attempt, src],
  );

  const handleLoad = (event: SyntheticEvent<HTMLImageElement>) => {
    if (retryTimerRef.current !== null) {
      window.clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
    onLoad?.(event);
  };

  const handleError = (event: SyntheticEvent<HTMLImageElement>) => {
    onError?.(event);
    if (attempt >= maxRetries || !isRetryableImageSrc(src)) {
      return;
    }
    if (retryTimerRef.current !== null) {
      return;
    }
    retryTimerRef.current = window.setTimeout(() => {
      retryTimerRef.current = null;
      setAttempt((current) => (current === attempt ? current + 1 : current));
    }, retryDelayForAttempt(attempt + 1, retryBaseDelayMs));
  };

  return (
    <img
      {...props}
      src={imageSrc}
      referrerPolicy={referrerPolicy ?? "no-referrer"}
      decoding={decoding ?? "async"}
      onError={handleError}
      onLoad={handleLoad}
    />
  );
}
