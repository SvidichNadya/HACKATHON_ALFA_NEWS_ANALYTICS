let csrf = "";
export const setCsrf = (t) => { csrf = t; };

export class ApiError extends Error {
  constructor(msg, status) { super(msg); this.status = status; }
}
export async function api(path, { method = "GET", body, form } = {}) {
  const opt = { method, headers: {}, credentials: "same-origin" };
  if (method !== "GET") opt.headers["X-CSRF-Token"] = csrf;
  if (form) opt.body = form;
  else if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  let r;
  try { r = await fetch(path, opt); } catch { throw new ApiError("Нет связи с сервисом. Проверьте соединение.", 0); }
  let data = null;
  try { data = await r.json(); } catch { /* empty body */ }
  if (!r.ok) throw new ApiError((data && data.error) || `Ошибка ${r.status}`, r.status);
  return data;
}
