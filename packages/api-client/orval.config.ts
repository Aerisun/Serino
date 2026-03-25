import { defineConfig } from "orval";

export default defineConfig({
  admin: {
    input: {
      target: "./openapi.json",
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
      target: "src/generated",
      schemas: "src/generated/model",
      client: "react-query",
      override: {
        mutator: {
          path: "./src/mutators/admin-instance.ts",
          name: "customInstance",
        },
        query: {
          useQuery: true,
          useMutation: true,
        },
      },
    },
  },
  publicApi: {
    input: {
      target: "./openapi.json",
      filters: {
        tags: ["public", "search", "seo"],
      },
    },
    output: {
      mode: "tags-split",
      target: "src/generated",
      schemas: "src/generated/model",
      client: "react-query",
      override: {
        mutator: {
          path: "./src/mutators/public-instance.ts",
          name: "customInstance",
        },
        query: {
          useQuery: true,
          useMutation: true,
        },
      },
    },
  },
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
