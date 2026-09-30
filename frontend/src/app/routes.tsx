import type { RouteObject } from 'react-router-dom';
import { AppShell } from './AppShell';
import { CatalogPage } from '../pages/CatalogPage';
import { HomePage } from '../pages/HomePage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { QuotePage } from '../pages/QuotePage';
import { ApplyPage } from '../pages/ApplyPage';
import { UnderwritingReviewPage } from '../pages/UnderwritingReviewPage';
import { WorkbenchPage } from '../pages/WorkbenchPage';
import { PoliciesPage } from '../pages/PoliciesPage';
import { PolicyDetailPage } from '../pages/PolicyDetailPage';
import { EndorsePage } from '../pages/EndorsePage';
import { RenewPage } from '../pages/RenewPage';
import { CancelPage } from '../pages/CancelPage';
import { EndOfDayPage } from '../pages/EndOfDayPage';
import { PortfolioPage } from '../pages/PortfolioPage';

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <HomePage /> },
      // Story E2-S4 — the Product Catalog Manager replaces its placeholder.
      { path: 'admin/catalog', element: <CatalogPage /> },
      // Story E3-S3 — the Get a Quote screen replaces its placeholder.
      { path: 'quote', element: <QuotePage /> },
      // Story E4-S5 — Apply, Workbench and Underwriting Review replace their placeholders.
      // `/apply/:quoteId` is the canonical route; `/apply?quote=…` is the link the quote screen uses.
      { path: 'apply', element: <ApplyPage /> },
      { path: 'apply/:quoteId', element: <ApplyPage /> },
      { path: 'underwriter/queue', element: <WorkbenchPage /> },
      { path: 'underwriting', element: <WorkbenchPage /> },
      { path: 'admin/underwriting', element: <UnderwritingReviewPage /> },
      // Story E5-S3 — My Policies and Policy Detail replace their placeholders.
      { path: 'policies', element: <PoliciesPage /> },
      { path: 'policies/:policyNumber', element: <PolicyDetailPage /> },
      // Story E6-S3 — Endorse (CUSTOMER owner, ADMIN).
      { path: 'policies/:policyNumber/endorse', element: <EndorsePage /> },
      // Story E7-S4 — Renew (CUSTOMER owner) and the admin end-of-day control.
      { path: 'policies/:policyNumber/renew', element: <RenewPage /> },
      { path: 'admin/end-of-day', element: <EndOfDayPage /> },
      // Story E8-S3 — Cancel with its refund preview (CUSTOMER owner, ADMIN).
      { path: 'policies/:policyNumber/cancel', element: <CancelPage /> },
      // Story E9-S2 — the admin Portfolio dashboard replaces its placeholder.
      { path: 'admin/portfolio', element: <PortfolioPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
];
