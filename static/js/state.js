export const S = { me: null, csrf: "", companyId: null, role: null, feed: null, feedAt: 0, theme: null };
const listeners = new Set();
export const on = (fn) => { listeners.add(fn); return () => listeners.delete(fn); };
export const emit = () => listeners.forEach((f) => f());
