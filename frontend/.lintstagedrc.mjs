const quote = (files) => files.map((file) => JSON.stringify(file)).join(" ")

export default {
  "frontend/**/*.{js,mjs,cjs,ts,tsx,json,css}": (files) =>
    `npm --prefix frontend exec -- oxfmt --write -- ${quote(files)}`,
  "frontend/**/*.{js,mjs,cjs,ts,tsx}": (files) =>
    `npm --prefix frontend exec -- oxlint --fix --deny-warnings --threads=1 -- ${quote(files)}`,
  "backend/**/*.py": (files) => [
    `uv run --project backend ruff format --config backend/pyproject.toml ${quote(files)}`,
    `uv run --project backend ruff check --fix --config backend/pyproject.toml ${quote(files)}`,
  ],
}
