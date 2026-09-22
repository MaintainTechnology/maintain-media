// Only the local bundle aliases framework surfaces; production uses its real imports.
/* eslint-disable @next/next/no-img-element -- This local framework mock renders ordinary DOM elements. */
export const useDashboard = () => globalThis.sourceHarness.engine;
export const errorMessage = (code, fallback) => fallback || code;
export function Image(props) { const html = { ...props }; delete html.priority; return <img alt={html.alt || ""} {...html} />; }
export function Link(props) { const html = { ...props }; delete html.prefetch; delete html.onNavigate; return <a {...html} />; }
export const UserButton = () => null;
UserButton.MenuItems = function LocalUserMenu() { return null; };
UserButton.Action = function LocalUserAction() { return null; };
