import { WEATHER_OPTIONS } from "./contentOptions";

type WeatherOption = (typeof WEATHER_OPTIONS)[number];

type IncludesWeatherOption<
  TValue extends string,
  TLabelKey extends string,
> = Extract<WeatherOption, { value: TValue; labelKey: TLabelKey }> extends never
  ? false
  : true;

type ExpectTrue<TValue extends true> = TValue;

export type WeatherOptionsContract = ExpectTrue<
  IncludesWeatherOption<"overcast", "diary.weatherOvercast">
>;
