-- Migration: projects.website_url — optional link to a project's live product site
--
-- Purely additive, nullable column — a project without a website_url behaves
-- exactly as before. Feeds the "Product Websites" card grid on the Home
-- dashboard (frontend/components/dashboard/ProductWebsites.tsx): only
-- projects with a real, user-entered URL ever render a card there — nothing
-- fabricated or inferred from other fields.

alter table projects
  add column if not exists website_url text;
