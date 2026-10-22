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
export const register = (email, password, name) =>
  api("/api/register", { method: "POST", body: { email, password, name } });
export const logout = () => api("/api/logout", { method: "POST", body: {} });
export const changePassword = (current, next) =>
  api("/api/account/password", { method: "POST", body: { current, new: next } });

// ── администрирование ──
export const adminUsers = () => api("/api/admin/users");
export const adminCreate = (data) => api("/api/admin/users", { method: "POST", body: data });
export const adminBulk = (names) => api("/api/admin/users/bulk", { method: "POST", body: { names } });
export const adminReset = (id) => api(`/api/admin/users/${id}/reset`, { method: "POST", body: {} });
export const adminUpdate = (id, data) => api(`/api/admin/users/${id}`, { method: "PATCH", body: data });
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

export function checkFile(file, profile, onProgress) {
  const data = new FormData();
  data.append("file", file);
  data.append("profile", profile);
  return postForm("/api/check", data, onProgress);
}

/** Исправление: сначала по upload_id (файл уже на сервере), если он устарел — отправляем файл заново. */
export async function fixFile({ uploadId, file, profile, onProgress }) {
  if (uploadId) {
    const data = new FormData();
    data.append("upload_id", uploadId);
    data.append("profile", profile);
    try {
      return await postForm("/api/fix", data);
    } catch (e) {
      if (e.code !== "upload_expired") throw e;
    }
  }
  const data = new FormData();
  data.append("file", file);
  data.append("profile", profile);
  return postForm("/api/fix", data, onProgress);
}

export const reportUrl = (id) => `/api/report/${id}`;
export const annotatedUrl = (uploadId, profile) => `/api/annotated/${uploadId}?profile=${encodeURIComponent(profile)}`;
export const fixedUrl = (id) => `/api/fixed/${id}`;
