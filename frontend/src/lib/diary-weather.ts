import {
  Cloud,
  CloudDrizzle,
  CloudFog,
  CloudHail,
  CloudLightning,
  CloudRain,
  CloudRainWind,
  CloudSnow,
  CloudSunRain,
  Haze,
  Snowflake,
  Sun,
  Wind,
} from "lucide-react";

export const DIARY_WEATHER_ICONS = {
  sunny: Sun,
  cloudy: Cloud,
  overcast: Cloud,
  fog: CloudFog,
  haze: Haze,
  light_rain: CloudDrizzle,
  shower: CloudSunRain,
  rainy: CloudRain,
  heavy_rain: CloudRainWind,
  light_snow: CloudSnow,
  snowy: CloudSnow,
  heavy_snow: Snowflake,
  sleet: CloudHail,
  stormy: CloudLightning,
  windy: Wind,
} as const;

export const DIARY_WEATHER_LABEL_KEYS = {
  sunny: "diary.weather.sunny",
  cloudy: "diary.weather.cloudy",
  overcast: "diary.weather.overcast",
  fog: "diary.weather.fog",
  haze: "diary.weather.haze",
  light_rain: "diary.weather.lightRain",
  shower: "diary.weather.shower",
  rainy: "diary.weather.rainy",
  heavy_rain: "diary.weather.heavyRain",
  light_snow: "diary.weather.lightSnow",
  snowy: "diary.weather.snowy",
  heavy_snow: "diary.weather.heavySnow",
  sleet: "diary.weather.sleet",
  stormy: "diary.weather.stormy",
  windy: "diary.weather.windy",
} as const;

export type DiaryWeather = keyof typeof DIARY_WEATHER_LABEL_KEYS;

export function normalizeDiaryWeather(value: unknown): DiaryWeather | undefined {
  return typeof value === "string" && value in DIARY_WEATHER_LABEL_KEYS
    ? (value as DiaryWeather)
    : undefined;
}

export function getDiaryWeatherLabelKey(value: unknown) {
  const weather = normalizeDiaryWeather(value);
  return weather ? DIARY_WEATHER_LABEL_KEYS[weather] : undefined;
}
