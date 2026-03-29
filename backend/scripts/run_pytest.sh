#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
BACKEND_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)
TEST_ENV_FILE="${BACKEND_ROOT}/.env.test.local"
DEV_ENV_FILE="${BACKEND_ROOT}/.env"
PYTEST_BIN="${BACKEND_ROOT}/.venv/bin/pytest"

if [[ ! -x "${PYTEST_BIN}" ]]; then
  echo "Missing backend virtualenv pytest binary: ${PYTEST_BIN}" >&2
  echo "Use backend/.venv or activate the backend virtualenv before running tests." >&2
  exit 1
fi

if [[ ! -f "${TEST_ENV_FILE}" ]]; then
  echo "Missing test env file: ${TEST_ENV_FILE}" >&2
  echo "Copy backend/.env.test.sample to backend/.env.test.local and set VAT_TEST_DATABASE_URL." >&2
  exit 1
fi

set -a
source "${TEST_ENV_FILE}"
set +a

if [[ -z "${VAT_TEST_DATABASE_URL:-}" ]]; then
  echo "VAT_TEST_DATABASE_URL is required in ${TEST_ENV_FILE}" >&2
  exit 1
fi

if [[ -f "${DEV_ENV_FILE}" ]]; then
  DEV_DATABASE_URL=$(grep -E '^VAT_DATABASE_URL=' "${DEV_ENV_FILE}" | head -n 1 | cut -d= -f2- || true)
  if [[ -n "${DEV_DATABASE_URL}" && "${DEV_DATABASE_URL}" == "${VAT_TEST_DATABASE_URL}" ]]; then
    echo "VAT_TEST_DATABASE_URL must not point to the development database in ${DEV_ENV_FILE}" >&2
    exit 1
  fi
fi

exec "${PYTEST_BIN}" "$@"
