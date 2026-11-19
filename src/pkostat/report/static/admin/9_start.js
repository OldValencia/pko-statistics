// Runs last: every admin page renderer is defined by now.
restoreView();
if (location.hash === "#transactions") go("transactions");
// Bookmarkable admin pages: #admin-users, #admin-budgets, #admin-data, #admin-categories, #admin-uncategorised.
if (location.hash.startsWith("#admin-") && ADMIN_TITLES[location.hash.slice(7)]) go("admin", location.hash.slice(7));
