async function parse(resp) {
  if (resp.ok) return resp.json();
  const problem = await resp.json().catch(() => ({}));
  throw new Error(problem.error || "Не удалось выполнить запрос. Попробуйте ещё раз.");
}

export const fetchProfiles = () => fetch("/api/profiles").then(parse);

export function checkFile(file, profile) {
  const data = new FormData();
  data.append("file", file);
  data.append("profile", profile);
  return fetch("/api/check", { method: "POST", body: data }).then(parse);
}

export const reportUrl = (id) => `/api/report/${id}`;

export const fetchConfig = () => fetch("/api/config").then(parse);

export function fixFile(file, profile) {
  const data = new FormData();
  data.append("file", file);
  data.append("profile", profile);
  return fetch("/api/fix", { method: "POST", body: data }).then(parse);
}

export const fixedUrl = (id) => `/api/fixed/${id}`;
