import js from '@eslint/js';
import globals from 'globals';
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';

export default tseslint.config(
  {
    name: 'app/files-to-ignore',
    ignores: ['dist/**', 'coverage/**'],
  },
  {
    name: 'app/files-to-lint',
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      '@typescript-eslint/no-explicit-any': 'error',
    },
  },
  {
    name: 'app/tests',
    files: ['**/*.{test,spec}.{ts,tsx}', '**/test/**'],
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
    },
  },
);
