import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useBackgroundMusicConfig } from "@/contexts/runtime-config";
import { MusicPlayerContext } from "@/contexts/music-player";
import {
  advanceRandomTrack,
  clampMusicSeekTime,
  createRandomPlaybackState,
  nextSequentialIndex,
  previousRandomTrack,
  previousSequentialIndex,
  type RandomPlaybackState,
} from "@/lib/music-playback";

export function MusicPlayerProvider({ children }: { children: ReactNode }) {
  const config = useBackgroundMusicConfig();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const randomStateRef = useRef<RandomPlaybackState>(createRandomPlaybackState());
  const failedTrackIdsRef = useRef(new Set<string>());
  const [currentTrackId, setCurrentTrackId] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [hasStarted, setHasStarted] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const available = config.enabled && config.tracks.length > 0;
  const trackIdsKey = config.tracks.map((track) => track.id).join("\u0000");

  const currentTrack = useMemo(
    () =>
      config.tracks.find((track) => track.id === currentTrackId) ??
      config.tracks[0] ??
      null,
    [config.tracks, currentTrackId],
  );

  const requestTrackPlayback = useCallback(
    (trackId: string) => {
      const audio = audioRef.current;
      const track = config.tracks.find((item) => item.id === trackId);
      if (!audio || !available || !track) return;

      setCurrentTrackId(track.id);
      setHasStarted(true);
      if (
        audio.dataset.musicTrackId !== track.id ||
        audio.dataset.musicStreamUrl !== track.streamUrl
      ) {
        setCurrentTime(0);
        setDuration(0);
        audio.src = track.streamUrl;
        audio.dataset.musicTrackId = track.id;
        audio.dataset.musicStreamUrl = track.streamUrl;
        audio.load();
      }

      const playRequest = audio.play();
      if (playRequest) {
        void playRequest.catch(() => setIsPlaying(false));
      }
    },
    [available, config.tracks],
  );

  const pickNextTrackId = useCallback(
    (candidateIds = config.tracks.map((track) => track.id)) => {
      if (config.playbackMode === "random") {
        const result = advanceRandomTrack(candidateIds, randomStateRef.current);
        randomStateRef.current = result.state;
        return result.trackId;
      }

      const currentIndex = config.tracks.findIndex((track) => track.id === currentTrackId);
      if (candidateIds.length === config.tracks.length) {
        return config.tracks[nextSequentialIndex(currentIndex, config.tracks.length)]?.id ?? null;
      }

      for (let offset = 1; offset <= config.tracks.length; offset += 1) {
        const index = (Math.max(currentIndex, -1) + offset) % config.tracks.length;
        const trackId = config.tracks[index]?.id;
        if (trackId && candidateIds.includes(trackId)) return trackId;
      }
      return null;
    },
    [config.playbackMode, config.tracks, currentTrackId],
  );

  const nextTrack = useCallback(() => {
    const trackId = pickNextTrackId();
    if (trackId) requestTrackPlayback(trackId);
  }, [pickNextTrackId, requestTrackPlayback]);

  const previousTrack = useCallback(() => {
    if (!available) return;
    let trackId: string | null = null;
    if (config.playbackMode === "random") {
      const result = previousRandomTrack(
        config.tracks.map((track) => track.id),
        randomStateRef.current,
      );
      randomStateRef.current = result.state;
      trackId = result.trackId;
      if (!trackId) {
        const first = advanceRandomTrack(
          config.tracks.map((track) => track.id),
          randomStateRef.current,
        );
        randomStateRef.current = first.state;
        trackId = first.trackId;
      }
    } else {
      const currentIndex = config.tracks.findIndex((track) => track.id === currentTrackId);
      trackId =
        config.tracks[previousSequentialIndex(currentIndex, config.tracks.length)]?.id ?? null;
    }
    if (trackId) requestTrackPlayback(trackId);
  }, [available, config.playbackMode, config.tracks, currentTrackId, requestTrackPlayback]);

  const startPlayback = useCallback(() => {
    if (!available) return;
    const audio = audioRef.current;
    if (currentTrackId && audio?.dataset.musicTrackId === currentTrackId) {
      requestTrackPlayback(currentTrackId);
      return;
    }

    const trackId =
      config.playbackMode === "random"
        ? pickNextTrackId()
        : currentTrackId ?? config.tracks[0]?.id ?? null;
    if (trackId) requestTrackPlayback(trackId);
  }, [available, config.playbackMode, config.tracks, currentTrackId, pickNextTrackId, requestTrackPlayback]);

  const togglePlayback = useCallback(() => {
    const audio = audioRef.current;
    if (!available || !audio) return;
    if (!audio.paused) {
      audio.pause();
      return;
    }
    startPlayback();
  }, [available, startPlayback]);

  const seekTo = useCallback((time: number) => {
    const audio = audioRef.current;
    if (!audio) return;
    const nextTime = clampMusicSeekTime(time, audio.duration);
    if (!Number.isFinite(audio.duration) || audio.duration <= 0) return;
    audio.currentTime = nextTime;
    setCurrentTime(nextTime);
  }, []);

  const handleTrackError = useCallback(() => {
    const audio = audioRef.current;
    const failedTrackId = audio?.dataset.musicTrackId;
    if (!failedTrackId) return;
    failedTrackIdsRef.current.add(failedTrackId);

    const candidateIds = config.tracks
      .map((track) => track.id)
      .filter((trackId) => !failedTrackIdsRef.current.has(trackId));
    if (candidateIds.length === 0) {
      audio?.pause();
      setIsPlaying(false);
      return;
    }

    const trackId = pickNextTrackId(candidateIds);
    if (trackId) requestTrackPlayback(trackId);
  }, [config.tracks, pickNextTrackId, requestTrackPlayback]);

  useEffect(() => {
    randomStateRef.current = createRandomPlaybackState();
    failedTrackIdsRef.current.clear();
  }, [config.playbackMode, trackIdsKey]);

  useEffect(() => {
    if (available) return;
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.removeAttribute("src");
      delete audio.dataset.musicTrackId;
      delete audio.dataset.musicStreamUrl;
      audio.load();
    }
    setCurrentTrackId(null);
    setIsPlaying(false);
    setHasStarted(false);
    setCurrentTime(0);
    setDuration(0);
  }, [available]);

  useEffect(() => {
    if (!currentTrackId || config.tracks.some((track) => track.id === currentTrackId)) return;
    const audio = audioRef.current;
    audio?.pause();
    setCurrentTrackId(null);
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);
  }, [config.tracks, currentTrackId]);

  useEffect(() => {
    if (typeof navigator === "undefined" || !("mediaSession" in navigator)) return;
    const mediaSession = navigator.mediaSession;
    const handlers: Array<[MediaSessionAction, MediaSessionActionHandler | null]> = [
      ["play", startPlayback],
      ["pause", () => audioRef.current?.pause()],
      ["previoustrack", previousTrack],
      ["nexttrack", nextTrack],
    ];
    handlers.forEach(([action, handler]) => {
      try {
        mediaSession.setActionHandler(action, handler);
      } catch {
        // The browser may expose Media Session without supporting every action.
      }
    });
    return () => {
      handlers.forEach(([action]) => {
        try {
          mediaSession.setActionHandler(action, null);
        } catch {
          // Ignore partial Media Session implementations.
        }
      });
    };
  }, [nextTrack, previousTrack, startPlayback]);

  useEffect(() => {
    if (
      !hasStarted ||
      !currentTrack ||
      typeof navigator === "undefined" ||
      !("mediaSession" in navigator) ||
      typeof MediaMetadata === "undefined"
    ) {
      return;
    }
    navigator.mediaSession.metadata = new MediaMetadata({ title: currentTrack.title });
  }, [currentTrack, hasStarted]);

  const contextValue = useMemo(
    () => ({
      available,
      currentTrack,
      isPlaying,
      hasStarted,
      currentTime,
      duration,
      togglePlayback,
      previousTrack,
      nextTrack,
      seekTo,
    }),
    [
      available,
      currentTime,
      currentTrack,
      duration,
      hasStarted,
      isPlaying,
      nextTrack,
      previousTrack,
      seekTo,
      togglePlayback,
    ],
  );

  return (
    <MusicPlayerContext.Provider value={contextValue}>
      {children}
      <audio
        ref={audioRef}
        preload="none"
        aria-hidden="true"
        onPlay={() => setIsPlaying(true)}
        onPlaying={() => {
          failedTrackIdsRef.current.clear();
          setIsPlaying(true);
        }}
        onPause={() => setIsPlaying(false)}
        onTimeUpdate={(event) => {
          const time = event.currentTarget.currentTime;
          setCurrentTime(Number.isFinite(time) ? time : 0);
        }}
        onDurationChange={(event) => {
          const nextDuration = event.currentTarget.duration;
          setDuration(Number.isFinite(nextDuration) && nextDuration > 0 ? nextDuration : 0);
        }}
        onEmptied={() => {
          setCurrentTime(0);
          setDuration(0);
        }}
        onEnded={nextTrack}
        onError={handleTrackError}
      />
    </MusicPlayerContext.Provider>
  );
}
