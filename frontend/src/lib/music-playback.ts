export const MOBILE_MUSIC_COLLAPSE_MS = 2500;

export type DesktopMusicOverlay = "none" | "play-hint" | "player";

export const resolveDesktopMusicOverlay = (
  isPlaying: boolean,
  interactionActive: boolean,
): DesktopMusicOverlay => {
  if (!interactionActive) return "none";
  return isPlaying ? "player" : "play-hint";
};

export const clampMusicSeekTime = (time: number, duration: number) => {
  if (!Number.isFinite(time) || !Number.isFinite(duration) || duration <= 0) return 0;
  return Math.min(Math.max(time, 0), duration);
};

export type CollapsedMusicTapAction = "start-and-expand" | "expand";

export interface RandomPlaybackState {
  bag: string[];
  history: string[];
  cursor: number;
}

export interface RandomTrackResult {
  trackId: string | null;
  state: RandomPlaybackState;
}

export const createRandomPlaybackState = (): RandomPlaybackState => ({
  bag: [],
  history: [],
  cursor: -1,
});

export const nextSequentialIndex = (currentIndex: number, length: number) => {
  if (length <= 0) return -1;
  return currentIndex < 0 ? 0 : (currentIndex + 1) % length;
};

export const previousSequentialIndex = (currentIndex: number, length: number) => {
  if (length <= 0) return -1;
  return currentIndex <= 0 ? length - 1 : (currentIndex - 1) % length;
};

const shuffle = (values: string[], random: () => number) => {
  const result = [...values];
  for (let index = result.length - 1; index > 0; index -= 1) {
    const target = Math.floor(random() * (index + 1));
    [result[index], result[target]] = [result[target], result[index]];
  }
  return result;
};

const normalizeState = (
  trackIds: string[],
  state: RandomPlaybackState,
): RandomPlaybackState => {
  const validIds = new Set(trackIds);
  const currentTrackId = state.history[state.cursor];
  const history = state.history.filter((trackId) => validIds.has(trackId));
  const cursor = currentTrackId
    ? history.lastIndexOf(currentTrackId)
    : Math.min(state.cursor, history.length - 1);

  return {
    bag: state.bag.filter((trackId) => validIds.has(trackId)),
    history,
    cursor: Math.max(-1, cursor),
  };
};

export const advanceRandomTrack = (
  trackIds: string[],
  state: RandomPlaybackState,
  random: () => number = Math.random,
): RandomTrackResult => {
  if (trackIds.length === 0) {
    return { trackId: null, state: createRandomPlaybackState() };
  }

  const normalized = normalizeState(trackIds, state);
  if (normalized.cursor < normalized.history.length - 1) {
    const cursor = normalized.cursor + 1;
    return {
      trackId: normalized.history[cursor] ?? null,
      state: { ...normalized, cursor },
    };
  }

  let bag = normalized.bag;
  const lastTrackId = normalized.history[normalized.cursor];
  if (bag.length === 0) {
    bag = shuffle(trackIds, random);
    if (bag.length > 1 && bag[0] === lastTrackId) {
      [bag[0], bag[1]] = [bag[1], bag[0]];
    }
  }

  const [trackId, ...remainingBag] = bag;
  const history = [...normalized.history.slice(0, normalized.cursor + 1), trackId];
  return {
    trackId,
    state: {
      bag: remainingBag,
      history,
      cursor: history.length - 1,
    },
  };
};

export const previousRandomTrack = (
  trackIds: string[],
  state: RandomPlaybackState,
): RandomTrackResult => {
  const normalized = normalizeState(trackIds, state);
  if (normalized.cursor <= 0) {
    return {
      trackId: normalized.history[normalized.cursor] ?? null,
      state: normalized,
    };
  }

  const cursor = normalized.cursor - 1;
  return {
    trackId: normalized.history[cursor] ?? null,
    state: { ...normalized, cursor },
  };
};

export const resolveCollapsedMusicTap = (hasStarted: boolean): CollapsedMusicTapAction =>
  hasStarted ? "expand" : "start-and-expand";
