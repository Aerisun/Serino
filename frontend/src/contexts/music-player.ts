import { createContext, useContext } from "react";
import type { BackgroundMusicTrack } from "@/lib/runtime-config";

export interface MusicPlayerContextValue {
  available: boolean;
  currentTrack: BackgroundMusicTrack | null;
  isPlaying: boolean;
  hasStarted: boolean;
  currentTime: number;
  duration: number;
  togglePlayback: () => void;
  previousTrack: () => void;
  nextTrack: () => void;
  seekTo: (time: number) => void;
}

export const MusicPlayerContext = createContext<MusicPlayerContextValue | null>(null);

export function useMusicPlayer() {
  const context = useContext(MusicPlayerContext);
  if (!context) {
    throw new Error("useMusicPlayer must be used within MusicPlayerProvider");
  }
  return context;
}
