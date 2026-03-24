import { defineConfig } from "orval";

export default defineConfig({
  publicApi: {
    input: {
      target: "./openapi.json",
      filters: {
        tags: ["public", "search", "seo"],
      },
    },
    output: {
      mode: "tags-split",
      target: "src/lib/api/generated",
      schemas: "src/lib/api/generated/model",
      client: "fetch",
      override: {
        mutator: {
          path: "./src/lib/api/mutator/custom-fetch.ts",
          name: "customFetch",
        },
      },
    },
  },
});
