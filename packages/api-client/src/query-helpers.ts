import type { ZodType } from "zod";
import { validateResponse } from "./validation";

export function withZodSelect<TIn, TOut>(
  schema: ZodType<TOut>,
  context?: string,
): (data: TIn) => TIn {
  return (data: TIn) => {
    validateResponse(schema, data, context);
    return data;
  };
}
