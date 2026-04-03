import { createReactAppEslintConfig } from "../eslint.config.base.js";

export default createReactAppEslintConfig({
  allowExportNames: ["AuthContext", "useI18n"],
  extraRules: {
    "no-empty": "warn",
    "@typescript-eslint/no-explicit-any": "off",
    "react-hooks/exhaustive-deps": "off",
    "react-refresh/only-export-components": "off",
  },
});
