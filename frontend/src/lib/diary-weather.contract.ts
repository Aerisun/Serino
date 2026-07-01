import { DIARY_WEATHER_LABEL_KEYS, normalizeDiaryWeather } from "./diary-weather";

type WeatherLabelKey = (typeof DIARY_WEATHER_LABEL_KEYS)["overcast"];

type ExpectOvercastLabelKey<TValue extends "diary.weather.overcast"> = TValue;

export type DiaryWeatherContract = ExpectOvercastLabelKey<WeatherLabelKey>;

export const diaryWeatherContractValue = normalizeDiaryWeather("overcast");
