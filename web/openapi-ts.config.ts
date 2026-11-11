import { defineConfig } from '@hey-api/openapi-ts'

// 后端接口改了之后在仓库根目录跑：
//   uv run python scripts/dump_webui_openapi.py > web/openapi.json && (cd web && pnpm gen)
export default defineConfig({
  input: './openapi.json',
  output: { path: './app/client' },
  plugins: ['@hey-api/client-fetch', '@pinia/colada'],
})
