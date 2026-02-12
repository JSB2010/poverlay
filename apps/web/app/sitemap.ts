import { MetadataRoute } from 'next';
import { PUBLIC_WEB_CONFIG } from '@/lib/public-config';

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = PUBLIC_WEB_CONFIG.siteUrl;

  return [
    {
      url: baseUrl,
      lastModified: new Date(),
      changeFrequency: 'weekly',
      priority: 1,
    },
    {
      url: `${baseUrl}/studio`,
      lastModified: new Date(),
      changeFrequency: 'weekly',
      priority: 0.9,
    },
  ];
}
