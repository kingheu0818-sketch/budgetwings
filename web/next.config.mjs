const repository = process.env.GITHUB_REPOSITORY ?? '';
const repositoryName = repository.split('/')[1] ?? '';
const isGitHubPages = process.env.GITHUB_ACTIONS === 'true' && repositoryName.length > 0;
const basePath = isGitHubPages ? `/${repositoryName}` : '';

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  trailingSlash: true,
  basePath,
  assetPrefix: basePath || undefined,
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
