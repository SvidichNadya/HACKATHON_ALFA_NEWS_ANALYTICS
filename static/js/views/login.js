import { h, mount, icon } from "../dom.js";
import { api } from "../api.js";
import { sweep } from "../charts.js";

export function loginView(me, done) {
  const err = h("div", { class: "err", role: "alert", hidden: true });
  const login = h("input", { class: "input", autocomplete: "username", id: "lg", required: true });
  const pass = h("input", { class: "input", type: "password", autocomplete: "current-password", id: "pw", required: true });
  const submit = async (e) => {
    e.preventDefault();
    err.hidden = true;
    try { await api("/api/login", { method: "POST", body: { login: login.value, password: pass.value } }); location.hash = "#/home"; done(); }
    catch (x) { err.textContent = x.message; err.hidden = false; }
  };
  return h("div", { class: "login" },
    h("section", { class: "login-art" }, h("div", { class: "row" }, h("span", { class: "brand-mark" }, h("svg", { viewBox: "0 0 24 24", width: 20, height: 20 }, h("path", { d: "M5 19 12 5l7 14M8 14.500h8", fill: "none", stroke: "#fff", "stroke-width": "2.400", "stroke-linecap": "round", "stroke-linejoin": "round" }))), h("b", null, "Альфа-Бизнес")),
      h("div", null, h("h1", null, "Бизнес-радар"), h("p", null, "Внешние события, которые действительно затрагивают вашу компанию: что произошло, почему это важно именно вам, что говорит банк и что стоит проверить.")),
      h("div", { class: "small", style: { opacity: ".6" } }, "Прототип. Данные компаний и новости синтетические."), sweep([{ importance: 90, priority: "critical" }, { importance: 60, priority: "high" }, { importance: 40 }, { importance: 70, priority: "high" }], 220)),
    h("form", { class: "login-form", onSubmit: submit }, h("div", null, h("h2", null, "Вход в сервис"), h("p", { class: "muted", style: { marginTop: "6px" } }, "Используйте учётную запись представителя компании.")),
      h("label", { class: "f", for: "lg" }, "Логин", login), h("label", { class: "f", for: "pw" }, "Пароль", pass), err, h("button", { class: "btn primary", type: "submit" }, "Войти"),
      h("div", { class: "card flat tight" }, h("b", { class: "small" }, "Демонстрационные учётные записи"), h("p", { class: "tiny muted", style: { margin: "4px 0 10px" } }, "Пароль для всех — из переменной RADAR_DEMO_PASSWORD (по умолчанию в README)."),
        h("div", { class: "demo-list" }, me.demo_accounts.map((a) => h("button", { type: "button", class: "demo-acc", onClick: () => { login.value = a.login; pass.focus(); } }, h("span", null, h("b", { class: "small" }, a.name), h("div", { class: "tiny muted" }, a.role)), h("code", { class: "tiny" }, a.login)))))));
}
