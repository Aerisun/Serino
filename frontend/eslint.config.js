import { createReactAppEslintConfig } from "../eslint.config.base.js";

export default createReactAppEslintConfig({
  allowExportNames: ["useSiteConfig", "usePageConfig", "useFeatureFlags"],
  extraRules: {
    "react-refresh/only-export-components": "off",
  },
});
