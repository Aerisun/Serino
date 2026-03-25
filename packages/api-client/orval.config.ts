import { defineConfig } from "orval";

export default defineConfig({
  contractSchemas: {
    input: {
      target: "./openapi.json",
    },
    output: {
      mode: "single",
      target: "src/generated/schemas.zod.ts",
      client: "zod",
      override: {
        zod: {
          coerce: {
            date: true,
          },
        },
      },
    },
  },
});
