import { lazy, type ComponentType, type LazyExoticComponent } from "react";

type AnyProps = object;

type Loader<T extends ComponentType<AnyProps>> = () => Promise<{ default: T }>;

type PreloadableLazyComponent<T extends ComponentType<AnyProps>> = LazyExoticComponent<T> & {
  preload: Loader<T>;
};

export function lazyWithPreload<T extends ComponentType<AnyProps>>(
  loader: Loader<T>,
): PreloadableLazyComponent<T> {
  const Component = lazy(loader) as PreloadableLazyComponent<T>;
  Component.preload = loader;
  return Component;
}
