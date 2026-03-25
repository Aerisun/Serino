import type { ZodType, ZodError } from "zod";

// Vite replaces __SERINO_DEV__ at build time via the `define` option.
// In Node / test environments where no bundler runs, fall back to `true`
// so validation is enabled by default during development.
declare const __SERINO_DEV__: boolean | undefined;
const isDev: boolean =
  typeof __SERINO_DEV__ !== "undefined" ? __SERINO_DEV__ : true;

function formatZodError(error: ZodError, context?: string): string {
  const prefix = context ? `[API Contract: ${context}]` : "[API Contract]";
  const issues = error.issues.map(
    (issue) => `  - ${issue.path.join(".")}: ${issue.message} (${issue.code})`,
  );
  return `${prefix} Response validation failed:\n${issues.join("\n")}`;
}

export function validateResponse<T>(
  schema: ZodType<T>,
  data: unknown,
  context?: string,
): T {
  if (!isDev) {
    return data as T;
  }

  const result = schema.safeParse(data);
  if (!result.success) {
    console.error(formatZodError(result.error, context));
  }
  return data as T;
}

export function withValidation<T>(
  schema: ZodType<T> | undefined,
  data: unknown,
  context?: string,
): T {
  if (!schema || !isDev) {
    return data as T;
  }
  return validateResponse(schema, data, context);
}
