import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Instagram Toolkit',
  tagline: 'Ferramenta CLI para automação e análise do Instagram',
  favicon: 'img/favicon.ico',

  future: {
    v4: true,
  },

  url: 'https://prof-ramos.github.io',
  baseUrl: '/instagram-toolkit/',

  organizationName: 'prof-ramos',
  projectName: 'instagram-toolkit',

  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'pt-BR',
    locales: ['pt-BR'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/prof-ramos/instagram-toolkit/tree/main/website/',
        },
        blog: {
          showReadingTime: true,
          feedOptions: {
            type: ['rss', 'atom'],
            xslt: true,
          },
          editUrl: 'https://github.com/prof-ramos/instagram-toolkit/tree/main/website/',
          onInlineTags: 'warn',
          onInlineAuthors: 'warn',
          onUntruncatedBlogPosts: 'warn',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/docusaurus-social-card.jpg',
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'Instagram Toolkit',
      logo: {
        alt: 'Instagram Toolkit',
        src: 'img/logo.svg',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'tutorialSidebar',
          position: 'left',
          label: 'Documentação',
        },
        {to: '/blog', label: 'Blog', position: 'left'},
        {
          href: 'https://github.com/prof-ramos/instagram-toolkit',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            {label: 'Introdução', to: '/docs/intro'},
            {label: 'Autenticação', to: '/docs/auth'},
            {label: 'Comandos', to: '/docs/commands'},
          ],
        },
        {
          title: 'Ferramentas',
          items: [
            {label: 'Instagram Toolkit', href: 'https://github.com/prof-ramos/instagram-toolkit'},
            {label: 'Instagrapi', href: 'https://github.com/subzeroid/instagrapi'},
          ],
        },
        {
          title: 'Redes',
          items: [
            {label: 'GitHub', href: 'https://github.com/prof-ramos'},
            {label: 'Instagram', href: 'https://instagram.com/prof.gabrielramos'},
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Gabriel Ramos. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
