import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // React Compiler desligado no MVP: é otimização que adicionou risco (causou o bug
  // do Ranking com chave condicional de SWR) sem benefício perceptível agora.
};

export default nextConfig;
