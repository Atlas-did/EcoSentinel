import path from "path"
import { defineConfig } from "vitest/config"

// 独立配置（**故意不复用** vite.config.ts 的 dev 插件 kimi-plugin-inspect-react）：
// G6 的最小测试网只需要 `@` 别名与 jsdom 环境。后续写 .tsx 组件测试时，
// vitest 默认用 esbuild 处理 JSX；若需要 React 插件再改成 mergeConfig。
export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    // 单例 store / 模块级状态容易跨用例残留：每个用例前清掉 mock 记录
    clearMocks: true,
    restoreMocks: true,
  },
})
