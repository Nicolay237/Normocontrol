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
