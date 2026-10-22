async function parse(resp) {
  if (resp.ok) return resp.json();
  const problem = await resp.json().catch(() => ({}));
  const err = new Error(problem.error || "Не удалось выполнить запрос. Попробуйте ещё раз.");
  err.code = problem.code;
  err.status = resp.status;
  throw err;
}

export const fetchProfiles = () => fetch("/api/profiles").then(parse);
export const fetchConfig = () => fetch("/api/config").then(parse);

/** JSON-запрос к API (куки сессии уходят автоматически — тот же сайт). */
export function api(url, { method = "GET", body } = {}) {
  return fetch(url, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  }).then(parse);
}

// ── аккаунт ──
export const login = (login, password) => api("/api/login", { method: "POST", body: { login, password } });
export const register = (email, password, name, consent) =>
  api("/api/register", { method: "POST", body: { email, password, name, consent } });
export const verifyEmail = (code) => api("/api/email/verify", { method: "POST", body: { code } });
export const resendCode = () => api("/api/email/resend", { method: "POST", body: {} });
export const forgotPassword = (email) => api("/api/password/forgot", { method: "POST", body: { email } });
export const resetPassword = (email, code, password) =>
  api("/api/password/reset", { method: "POST", body: { email, code, password } });
export const fetchLegal = (key) => fetch(`/api/legal/${key}`).then(parse);
export const logout = () => api("/api/logout", { method: "POST", body: {} });
export const changePassword = (current, next) =>
  api("/api/account/password", { method: "POST", body: { current, new: next } });

// ── администрирование ──
export const adminUsers = () => api("/api/admin/users");
export const adminCreate = (data) => api("/api/admin/users", { method: "POST", body: data });
export const adminBulk = (names) => api("/api/admin/users/bulk", { method: "POST", body: { names } });
export const adminReset = (id) => api(`/api/admin/users/${id}/reset`, { method: "POST", body: {} });
export const adminUpdate = (id, data) => api(`/api/admin/users/${id}`, { method: "PATCH", body: data });
export const adminPacks = () => api("/api/admin/packs");
export const adminPackSettings = (key, settings) =>
  api(`/api/admin/packs/${key}`, { method: "PUT", body: { settings } });
export const adminDelete = (id) => api(`/api/admin/users/${id}`, { method: "DELETE" });

/**
 * POST multipart-формы через XHR — в отличие от fetch, он сообщает прогресс отправки.
 * На мобильном интернете загрузка файла занимает заметное время, и без шкалы кажется,
 * что всё зависло. onProgress(доля 0..1) вызывается, пока файл уходит на сервер;
 * когда он ушёл целиком — onProgress(1) и начинается обработка.
 */
function postForm(url, form, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.responseType = "json";
    xhr.timeout = 180000;
    if (onProgress) {
      xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
      xhr.upload.onload = () => onProgress(1);
    }
    xhr.onload = () => {
      const body = xhr.response || {};
      if (xhr.status >= 200 && xhr.status < 300) resolve(body);
      else {
        const err = new Error(body.error || "Не удалось выполнить запрос. Попробуйте ещё раз.");
        err.code = body.code;
        err.status = xhr.status;
        reject(err);
      }
    };
    xhr.onerror = () => reject(new Error("Нет связи с сервером. Проверьте интернет и попробуйте ещё раз."));
    xhr.ontimeout = () => reject(new Error("Сервер отвечает слишком долго. Попробуйте ещё раз."));
    xhr.send(form);
  });
}

export const fetchStandards = () => fetch("/api/standards").then(parse);

/** profile: vkr | coursework | custom; для custom — список выбранных ГОСТов (standards). */
export function checkFile(file, profile, onProgress, standards) {
  const data = new FormData();
  data.append("file", file);
  data.append("profile", profile);
  if (standards) data.append("standards", standards.join(","));
  return postForm("/api/check", data, onProgress);
}

/** Исправление: сначала по upload_id (файл уже на сервере), если он устарел — отправляем файл заново. */
export async function fixFile({ uploadId, file, profile, standards, onProgress }) {
  if (uploadId) {
    const data = new FormData();
    data.append("upload_id", uploadId);
    data.append("profile", profile);
    if (standards) data.append("standards", standards.join(","));
    try {
      return await postForm("/api/fix", data);
    } catch (e) {
      if (e.code !== "upload_expired") throw e;
    }
  }
  const data = new FormData();
  data.append("file", file);
  data.append("profile", profile);
  if (standards) data.append("standards", standards.join(","));
  return postForm("/api/fix", data, onProgress);
}

export const reportUrl = (id) => `/api/report/${id}`;
export const annotatedUrl = (uploadId, profile, standards) =>
  `/api/annotated/${uploadId}?profile=${encodeURIComponent(profile)}` +
  (standards?.length ? `&standards=${encodeURIComponent(standards.join(","))}` : "");
export const fixedUrl = (id) => `/api/fixed/${id}`;
