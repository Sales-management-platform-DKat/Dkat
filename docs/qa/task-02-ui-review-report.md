# Task 02 – UI Review Report

## Scope reviewed

The frontend routes include Landing, Login, Catalog, Platform Admin, Dashboard, Products, Inventory, POS, Orders, Preorders, Customers, Employees, Reports, Branches, Settings, and Notifications. I reviewed the existing route wiring and shared responsive styles, then ran the application in Microsoft Edge headless against the local Vite server.

The Dashboard was rendered and inspected at desktop (1440 px), tablet (768 px), and a narrow mobile browser window. The mobile viewport exposed a Dashboard card layout issue. Notifications was inspected in the logged-in route and compared with the existing bug log entry BUG-016. Other feature pages were not individually rendered in this pass.

## Findings and changes

| Finding | Priority | Change |
|---|---|---|
| Authenticated users saw the localStorage demo Notifications page, which implied notification history was connected to the real account. The actual notification history is available from each preorder. (BUG-016) | Medium | Hide Notifications from real-account navigation and prevent direct navigation to the demo-only page. Demo sessions retain the existing screen. |
| At narrow mobile widths, Dashboard metric cards remained in two columns and became cramped/clipped. | Medium | Use a single metric column at widths up to 520 px. |

## Browser checks

- Dashboard demo rendered at desktop, tablet, and mobile widths; the mobile metric cards now stack in one column.
- Dashboard navigation and demo content loaded from the running local frontend.
- Notification navigation is filtered by session mode in the application. Automated tests verify the demo keeps the item and real accounts do not.
- Screenshots are saved in `docs/qa/screenshots/task-02/` and show the post-change Dashboard build.
- Light theme and Vietnamese labels were checked. English, dark theme, form validation, loading/error/empty states, and every feature page were not individually exercised in the browser.

## Verification

- `npm test` — Pass, 33 tests.
- `npm run build` — Pass.
- Browser: Microsoft Edge headless, local Vite development server, desktop/tablet/mobile screenshot capture.

## Remaining issues

The full screen-by-screen review requested for every business module remains outstanding. The dashboard mobile review exposed and fixed one responsive issue; no other visual defects are claimed as verified in this pass. No backend API, database, or demo data source was changed.
