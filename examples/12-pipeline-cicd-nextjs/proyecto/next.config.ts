import type { NextConfig } from "next";

// BASE_PATH lo define el CI (salida base_path de actions/configure-pages) para
// servir en https://<usuario>.github.io/<repo>; vacío o sin definir = raíz.
const nextConfig: NextConfig = {
  output: "export",
  basePath: process.env.BASE_PATH,
  // `next dev` escribe AGENTS.md y CLAUDE.md si detecta un agente (Claude Code,
  // Cursor...); terminarían copiados en salida/ y subidos al repo del alumno.
  agentRules: false,
};

export default nextConfig;
