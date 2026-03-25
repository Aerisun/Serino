import { defineConfig } from "orval";

export default defineConfig({
  admin: {
    input: {
      target: "../packages/api-client/openapi.json",
      filters: {
        tags: [
          "admin-auth",
          "admin-posts",
          "admin-diary",
          "admin-thoughts",
          "admin-excerpts",
          "admin-site-config",
          "admin-resume",
          "admin-social",
          "admin-moderation",
          "admin-assets",
          "admin-system",
          "admin-content-meta",
          "admin-import-export",
        ],
      },
    },
    output: {
      mode: "tags-split",
      target: "src/api/generated",
      schemas: "src/api/generated/model",
      client: "react-query",
      override: {
        mutator: {
          path: "./src/api/mutator/custom-instance.ts",
          name: "customInstance",
        },
        query: {
          useQuery: true,
          useMutation: true,
        },
      },
    },
  },
});
