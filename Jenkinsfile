// Jenkinsfile - MarkForge Docker deployment pipeline
//
// Target path:
//   Cloudflare -> HAProxy bare metal -> Docker container -> Gunicorn -> Flask
//
// Production URL:
//   https://markforge.alexandru-raul.ro
//
// Folder convention:
//   /opt/containers/markforge-{GIT_REF_NAME}-{ENVIRONMENT}{SLOT}
//
// Compose project convention:
//   markforge-{ENVIRONMENT}{SLOT}
//
// Slack notifications are sent only for deploy/remove, and only when the
// configured Jenkins Secret Text credential exists.

pipeline {
    agent any

    parameters {
        choice(name: 'ACTION', choices: ['deploy', 'restart', 'stop', 'remove', 'logs', 'status'], description: 'Action to perform on the MarkForge stack')
        choice(name: 'ENVIRONMENT', choices: ['prod', 'dev', 'pre-prod', 'test'], description: 'Target environment')
        string(name: 'SLOT', defaultValue: '01', description: 'Instance slot, for example 01, 02, 03')
        choice(name: 'GIT_REF_TYPE', choices: ['tag', 'branch'], description: 'Deploy from a Git tag or branch')
        string(name: 'GIT_REF_NAME', defaultValue: 'develop', description: 'Git tag or branch to deploy, for example v1.0.0, main, develop')
        booleanParam(name: 'FORCE_RECREATE', defaultValue: false, description: 'Force recreate containers during deployment')
        booleanParam(name: 'PULL_IMAGES', defaultValue: true, description: 'Build with latest base images')
        booleanParam(name: 'FORCE_REBUILD', defaultValue: false, description: 'Force no-cache rebuild for the MarkForge image')
        booleanParam(name: 'REMOVE_VOLUMES', defaultValue: false, description: '[DANGER] Remove named volumes on stack removal')
        string(name: 'CLIENT', defaultValue: 'markforge', description: 'Client identifier for notifications')
        choice(name: 'STRATEGY', choices: ['in-place', 'recreate'], description: 'Deployment strategy')
    }

    environment {
        GIT_REPO = 'git@github.com:Punctiq/markforge.git'
        SSH_ALIAS = 'portal'
        SSH_TIMEOUT = '30'
        CONTAINERS_BASE_DIR = '/opt/containers'
        APP_IMAGE_NAME = 'punctiq/markforge'
        APP_SERVICE_NAME = 'markforge'
        APP_PORT = '8010'
        HEALTH_PATH = '/api/v1/health'
        PUBLIC_URL = 'https://markforge.alexandru-raul.ro'
        // Jenkins Managed File ID for the production .env file. Replace this placeholder in Jenkins.
        ENV_FILE_ID = 'MARKFORGE_ENV_FILE_ID'

        // Jenkins Secret Text credential ID for the Slack webhook. Replace this placeholder in Jenkins.
        SLACK_CREDENTIAL_ID = 'MARKFORGE_SLACK_WEBHOOK_ID'
    }

    stages {
        stage('Initialize') {
            steps {
                script {
                    def gitRefName = params.GIT_REF_NAME.trim()
                    def environment = params.ENVIRONMENT
                    def slot = params.SLOT.trim().padLeft(2, '0')
                    def safeRef = gitRefName.replaceAll('[^a-zA-Z0-9._-]', '-')
                    def slotLabel = "${environment}${slot}"

                    env.DEPLOYMENT_ID = "${env.BUILD_NUMBER}-${new Date().format('yyyyMMdd-HHmmss')}"
                    env.DEPLOY_ACTION = params.ACTION
                    env.DEPLOY_FORCE_RECREATE = params.FORCE_RECREATE.toString()
                    env.DEPLOY_PULL_IMAGES = params.PULL_IMAGES.toString()
                    env.DEPLOY_FORCE_REBUILD = params.FORCE_REBUILD.toString()
                    env.DEPLOY_REMOVE_VOLUMES = params.REMOVE_VOLUMES.toString()
                    env.DEPLOY_GIT_REF_TYPE = params.GIT_REF_TYPE
                    env.DEPLOY_GIT_REF_NAME = gitRefName
                    env.DEPLOY_SAFE_REF_NAME = safeRef
                    env.DEPLOY_CLIENT = params.CLIENT.trim()
                    env.DEPLOY_ENVIRONMENT = environment
                    env.DEPLOY_STRATEGY = params.STRATEGY
                    env.DEPLOY_SLOT = slot
                    env.DEPLOY_SLOT_LABEL = slotLabel
                    env.DEPLOY_DIR = "${env.CONTAINERS_BASE_DIR}/markforge-${safeRef}-${slotLabel}"
                    env.COMPOSE_PROJECT_NAME = "markforge-${slotLabel}"
                }
            }
        }

        stage('Deployment Info') {
            steps {
                script {
                    echo '==============================================='
                    echo 'Deploying MarkForge'
                    echo '==============================================='
                    echo "Action:              ${env.DEPLOY_ACTION}"
                    echo "Client:              ${env.DEPLOY_CLIENT}"
                    echo "Environment:         ${env.DEPLOY_ENVIRONMENT}"
                    echo "Slot:                ${env.DEPLOY_SLOT} -> ${env.DEPLOY_SLOT_LABEL}"
                    echo "Strategy:            ${env.DEPLOY_STRATEGY}"
                    echo "Git Repo:            ${env.GIT_REPO}"
                    echo "Git Ref Type:        ${env.DEPLOY_GIT_REF_TYPE}"
                    echo "Git Ref Name:        ${env.DEPLOY_GIT_REF_NAME}"
                    echo "SSH Alias:           ${env.SSH_ALIAS}"
                    echo "Deploy Dir:          ${env.DEPLOY_DIR}"
                    echo "Compose Project:     ${env.COMPOSE_PROJECT_NAME}"
                    echo "App Image Name:      ${env.APP_IMAGE_NAME}"
                    echo "App Service:         ${env.APP_SERVICE_NAME}"
                    echo "App Port:            ${env.APP_PORT}"
                    echo "Health Path:         ${env.HEALTH_PATH}"
                    echo "Public URL:          ${env.PUBLIC_URL}"
                    echo "Force Recreate:      ${env.DEPLOY_FORCE_RECREATE}"
                    echo "Pull Images:         ${env.DEPLOY_PULL_IMAGES}"
                    echo "Force Rebuild:       ${env.DEPLOY_FORCE_REBUILD}"
                    echo "Remove Volumes:      ${env.DEPLOY_REMOVE_VOLUMES}"
                    echo "Deployment ID:       ${env.DEPLOYMENT_ID}"
                    echo '==============================================='
                }
            }
        }

        stage('Validate Parameters') {
            steps {
                sh '''#!/usr/bin/env bash
set -euo pipefail

if [ -z "${DEPLOY_GIT_REF_NAME}" ]; then
    echo "GIT_REF_NAME cannot be empty"
    exit 1
fi

case "${DEPLOY_GIT_REF_TYPE}" in
    branch|tag) ;;
    *) echo "Invalid GIT_REF_TYPE: ${DEPLOY_GIT_REF_TYPE}"; exit 1 ;;
esac

case "${DEPLOY_ACTION}" in
    deploy|restart|stop|remove|logs|status) ;;
    *) echo "Invalid ACTION: ${DEPLOY_ACTION}"; exit 1 ;;
esac

case "${DEPLOY_ENVIRONMENT}" in
    prod|dev|pre-prod|test) ;;
    *) echo "Invalid ENVIRONMENT: ${DEPLOY_ENVIRONMENT}"; exit 1 ;;
esac

if ! printf '%s' "${DEPLOY_SLOT}" | grep -qE '^[0-9]{2}$'; then
    echo "SLOT must be a two-digit number, got: ${DEPLOY_SLOT}"
    exit 1
fi

if printf '%s' "${DEPLOY_SAFE_REF_NAME}" | grep -qE '^[-.]*$'; then
    echo "GIT_REF_NAME must contain at least one alphanumeric, underscore, dot, or dash character"
    exit 1
fi

echo "Parameters validated"
echo "Slot label:   ${DEPLOY_SLOT_LABEL}"
echo "Deploy dir:   ${DEPLOY_DIR}"
echo "Compose proj: ${COMPOSE_PROJECT_NAME}"
'''
            }
        }

        stage('Test SSH Connection') {
            steps {
                echo 'Testing SSH connection to deployment host...'
                sh '''#!/usr/bin/env bash
set -euo pipefail

ssh -T \
    -o BatchMode=yes \
    -o ConnectTimeout="${SSH_TIMEOUT}" \
    -o ServerAliveInterval=15 \
    -o ServerAliveCountMax=3 \
    "${SSH_ALIAS}" \
    'echo "SSH connection successful" && hostname && docker --version && docker compose version && git --version'
'''
            }
        }

        stage('Notify Slack — Started') {
            when { expression { params.ACTION in ['deploy', 'remove'] } }
            steps {
                script {
                    try {
                        withCredentials([string(credentialsId: env.SLACK_CREDENTIAL_ID, variable: 'SLACK_WEBHOOK_URL')]) {
                            sh '''#!/usr/bin/env bash
set -euo pipefail

payload="$(mktemp)"
python3 - >"${payload}" <<'PY'
import json
import os

payload = {
    "username": "MarkForge Deployment Bot",
    "icon_emoji": ":hammer_and_pick:",
    "attachments": [{
        "color": "#0099CC",
        "title": "MarkForge - STARTED",
        "text": (
            "Deployment started.\n"
            f"Client: *{os.getenv('DEPLOY_CLIENT', '')}* | Env: *{os.getenv('DEPLOY_ENVIRONMENT', '')}* | Slot: *{os.getenv('DEPLOY_SLOT_LABEL', '')}* | Strategy: *{os.getenv('DEPLOY_STRATEGY', '')}*\n"
            f"Action: *{os.getenv('DEPLOY_ACTION', '')}* | Ref: *{os.getenv('DEPLOY_GIT_REF_TYPE', '')}/{os.getenv('DEPLOY_GIT_REF_NAME', '')}*\n"
            f"Deploy Dir: `{os.getenv('DEPLOY_DIR', '')}`\n"
            f"Public URL: {os.getenv('PUBLIC_URL', '')}\n"
            f"Deployment ID: `{os.getenv('DEPLOYMENT_ID', '')}`\n"
            f"<{os.getenv('BUILD_URL', '')}console|View Jenkins Build>"
        ),
        "footer": f"Jenkins | {os.getenv('JOB_NAME', 'job')}",
    }],
}
print(json.dumps(payload))
PY

set +x
curl -sS -X POST -H 'Content-type: application/json' --data @"${payload}" "${SLACK_WEBHOOK_URL}" >/dev/null || true
rm -f "${payload}"
'''
                        }
                    } catch (Exception e) {
                        echo "Slack start notification skipped: ${e.message}"
                    }
                }
            }
        }

        stage('Prepare Repository') {
            steps {
                echo 'Preparing remote repository...'
                sh '''#!/usr/bin/env bash
set -euo pipefail

ssh -T \
    -o BatchMode=yes \
    -o ConnectTimeout="${SSH_TIMEOUT}" \
    -o ServerAliveInterval=15 \
    -o ServerAliveCountMax=3 \
    "${SSH_ALIAS}" \
    bash -s -- \
    "${GIT_REPO}" \
    "${DEPLOY_GIT_REF_TYPE}" \
    "${DEPLOY_GIT_REF_NAME}" \
    "${DEPLOY_DIR}" \
    "${DEPLOYMENT_ID}" \
    "${COMPOSE_PROJECT_NAME}" \
    "${DEPLOY_SLOT_LABEL}" <<'EOF_PREP'
set -euo pipefail

GIT_REPO="$1"
GIT_REF_TYPE="$2"
GIT_REF_NAME="$3"
DEPLOY_DIR="$4"
DEPLOYMENT_ID="$5"
COMPOSE_PROJECT_NAME="$6"
SLOT_LABEL="$7"

export COMPOSE_PROJECT_NAME

echo "=== Repository Preparation ==="
echo "Git Repo:        ${GIT_REPO}"
echo "Git Ref Type:    ${GIT_REF_TYPE}"
echo "Git Ref Name:    ${GIT_REF_NAME}"
echo "Deploy Dir:      ${DEPLOY_DIR}"
echo "Slot Label:      ${SLOT_LABEL}"
echo "Deployment ID:   ${DEPLOYMENT_ID}"
echo "Compose Project: ${COMPOSE_PROJECT_NAME}"

command -v git >/dev/null 2>&1 || { echo "git not found"; exit 10; }
command -v docker >/dev/null 2>&1 || { echo "docker not found"; exit 11; }
docker compose version >/dev/null 2>&1 || { echo "docker compose not found"; exit 12; }

if [ -d "${DEPLOY_DIR}/.git" ]; then
    echo "Repository exists; fetching updates"
    cd "${DEPLOY_DIR}"
    git remote set-url origin "${GIT_REPO}"
    git fetch origin --prune --tags
else
    echo "Cloning repository into ${DEPLOY_DIR}"
    mkdir -p "$(dirname "${DEPLOY_DIR}")"
    GIT_TERMINAL_PROMPT=0 git clone "${GIT_REPO}" "${DEPLOY_DIR}"
    cd "${DEPLOY_DIR}"
    git fetch origin --prune --tags
fi

echo "Checking out requested Git ref"
if [ "${GIT_REF_TYPE}" = "tag" ]; then
    if ! git rev-parse -q --verify "refs/tags/${GIT_REF_NAME}" >/dev/null; then
        echo "Git tag not found: ${GIT_REF_NAME}"
        git tag --sort=-creatordate | head -20 || true
        exit 20
    fi
    git checkout -f "refs/tags/${GIT_REF_NAME}"
else
    if ! git ls-remote --exit-code --heads origin "${GIT_REF_NAME}" >/dev/null 2>&1; then
        echo "Git branch not found on origin: ${GIT_REF_NAME}"
        git branch -r | sed 's/^/  /' | head -40 || true
        exit 21
    fi
    git checkout -B "${GIT_REF_NAME}" "origin/${GIT_REF_NAME}"
fi

git reset --hard HEAD

echo "Cleaning repository while preserving .env"
git clean -fdx -e .env

if [ ! -f docker-compose.yml ]; then
    echo "docker-compose.yml not found in ${DEPLOY_DIR}"
    exit 22
fi

docker compose config --quiet

GIT_COMMIT_FULL="$(git rev-parse HEAD)"
GIT_COMMIT="$(git rev-parse --short=12 HEAD)"
{
    echo "APP_VERSION=${GIT_REF_NAME}-${GIT_COMMIT}"
    echo "GIT_COMMIT=${GIT_COMMIT}"
    echo "GIT_COMMIT_FULL=${GIT_COMMIT_FULL}"
    echo "GIT_REF_TYPE=${GIT_REF_TYPE}"
    echo "GIT_REF_NAME=${GIT_REF_NAME}"
    echo "DEPLOYMENT_ID=${DEPLOYMENT_ID}"
    echo "SLOT_LABEL=${SLOT_LABEL}"
    echo "COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME}"
} > .deployment-version

echo "Repository ready at commit ${GIT_COMMIT}"
EOF_PREP
'''
            }
        }

        stage('Inject Environment File') {
            when { expression { params.ACTION == 'deploy' } }
            steps {
                echo 'Syncing managed .env file and injecting deployment metadata...'
                configFileProvider([configFile(fileId: env.ENV_FILE_ID, variable: 'MANAGED_ENV_FILE')]) {
                    sh '''#!/usr/bin/env bash
set -euo pipefail

LOCAL_SHA="$(sha256sum "${MANAGED_ENV_FILE}" | awk '{print $1}')"
REMOTE_SHA="$(ssh -T -o BatchMode=yes -o ConnectTimeout="${SSH_TIMEOUT}" "${SSH_ALIAS}" "test -f '${DEPLOY_DIR}/.env.managed.sha256' && cat '${DEPLOY_DIR}/.env.managed.sha256' || true")"

if [ "${LOCAL_SHA}" != "${REMOTE_SHA}" ]; then
    echo "Managed .env changed; uploading to remote deploy directory"
    TMP_REMOTE="/tmp/markforge-env-${DEPLOYMENT_ID}-${DEPLOY_SLOT_LABEL}"
    set +x
    scp -q -o BatchMode=yes -o ConnectTimeout="${SSH_TIMEOUT}" "${MANAGED_ENV_FILE}" "${SSH_ALIAS}:${TMP_REMOTE}"
    ssh -T -o BatchMode=yes -o ConnectTimeout="${SSH_TIMEOUT}" "${SSH_ALIAS}" "install -m 600 '${TMP_REMOTE}' '${DEPLOY_DIR}/.env' && printf '%s\n' '${LOCAL_SHA}' > '${DEPLOY_DIR}/.env.managed.sha256' && chmod 600 '${DEPLOY_DIR}/.env.managed.sha256' && rm -f '${TMP_REMOTE}'"
else
    echo "Managed .env is unchanged"
fi

ssh -T \
    -o BatchMode=yes \
    -o ConnectTimeout="${SSH_TIMEOUT}" \
    -o ServerAliveInterval=15 \
    -o ServerAliveCountMax=3 \
    "${SSH_ALIAS}" \
    bash -s -- \
    "${DEPLOY_DIR}" \
    "${DEPLOY_GIT_REF_TYPE}" \
    "${DEPLOY_GIT_REF_NAME}" \
    "${DEPLOYMENT_ID}" \
    "${DEPLOY_SLOT_LABEL}" \
    "${COMPOSE_PROJECT_NAME}" <<'EOF_ENV'
set -euo pipefail

DEPLOY_DIR="$1"
GIT_REF_TYPE="$2"
GIT_REF_NAME="$3"
DEPLOYMENT_ID="$4"
SLOT_LABEL="$5"
COMPOSE_PROJECT_NAME="$6"

cd "${DEPLOY_DIR}"

if [ ! -f .env ]; then
    echo ".env file is missing after managed file sync"
    exit 30
fi

GIT_COMMIT_FULL="$(git rev-parse HEAD)"
GIT_COMMIT="$(git rev-parse --short=12 HEAD)"
APP_VERSION="${GIT_REF_NAME}-${GIT_COMMIT}"

set_env_value() {
    local key="$1"
    local value="$2"
    local tmp
    tmp="$(mktemp)"
    awk -v key="${key}" -v value="${value}" '
        BEGIN { found = 0 }
        $0 ~ "^" key "=" { print key "=" value; found = 1; next }
        { print }
        END { if (found == 0) print key "=" value }
    ' .env > "${tmp}"
    install -m 600 "${tmp}" .env
    rm -f "${tmp}"
}

set_env_value APP_VERSION "${APP_VERSION}"
set_env_value GIT_COMMIT "${GIT_COMMIT}"
set_env_value GIT_COMMIT_FULL "${GIT_COMMIT_FULL}"
set_env_value GIT_REF_TYPE "${GIT_REF_TYPE}"
set_env_value GIT_REF_NAME "${GIT_REF_NAME}"
set_env_value DEPLOYMENT_ID "${DEPLOYMENT_ID}"
set_env_value SLOT_LABEL "${SLOT_LABEL}"
set_env_value COMPOSE_PROJECT_NAME "${COMPOSE_PROJECT_NAME}"

{
    echo "APP_VERSION=${APP_VERSION}"
    echo "GIT_COMMIT=${GIT_COMMIT}"
    echo "GIT_COMMIT_FULL=${GIT_COMMIT_FULL}"
    echo "GIT_REF_TYPE=${GIT_REF_TYPE}"
    echo "GIT_REF_NAME=${GIT_REF_NAME}"
    echo "DEPLOYMENT_ID=${DEPLOYMENT_ID}"
    echo "SLOT_LABEL=${SLOT_LABEL}"
    echo "COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME}"
} > .deployment-version

echo "Deployment metadata injected into .env"
EOF_ENV
'''
                }
            }
        }

        stage('Deploy Stack') {
            when { expression { params.ACTION == 'deploy' } }
            steps {
                echo 'Building and starting MarkForge stack...'
                sh '''#!/usr/bin/env bash
set -euo pipefail

ssh -T \
    -o BatchMode=yes \
    -o ConnectTimeout="${SSH_TIMEOUT}" \
    -o ServerAliveInterval=15 \
    -o ServerAliveCountMax=3 \
    "${SSH_ALIAS}" \
    bash -s -- \
    "${DEPLOY_DIR}" \
    "${COMPOSE_PROJECT_NAME}" \
    "${APP_SERVICE_NAME}" \
    "${APP_IMAGE_NAME}" \
    "${DEPLOY_PULL_IMAGES}" \
    "${DEPLOY_FORCE_REBUILD}" \
    "${DEPLOY_FORCE_RECREATE}" \
    "${DEPLOY_STRATEGY}" <<'EOF_DEPLOY'
set -euo pipefail

DEPLOY_DIR="$1"
COMPOSE_PROJECT_NAME="$2"
APP_SERVICE_NAME="$3"
APP_IMAGE_NAME="$4"
PULL_IMAGES="$5"
FORCE_REBUILD="$6"
FORCE_RECREATE="$7"
STRATEGY="$8"

export COMPOSE_PROJECT_NAME
cd "${DEPLOY_DIR}"

docker compose config --quiet

BUILD_ARGS=()
if [ "${PULL_IMAGES}" = "true" ]; then
    BUILD_ARGS+=(--pull)
fi
if [ "${FORCE_REBUILD}" = "true" ]; then
    BUILD_ARGS+=(--no-cache)
fi

echo "Building ${APP_SERVICE_NAME}"
docker compose build "${BUILD_ARGS[@]}" "${APP_SERVICE_NAME}"

IMAGE_ID="$(docker compose images -q "${APP_SERVICE_NAME}" | head -1 || true)"
APP_VERSION="$(awk -F= '$1 == "APP_VERSION" { print $2; exit }' .deployment-version)"
if [ -n "${IMAGE_ID}" ] && [ -n "${APP_VERSION}" ]; then
    docker tag "${IMAGE_ID}" "${APP_IMAGE_NAME}:${APP_VERSION}"
    docker tag "${IMAGE_ID}" "${APP_IMAGE_NAME}:${COMPOSE_PROJECT_NAME}"
fi

UP_ARGS=(-d)
if [ "${FORCE_RECREATE}" = "true" ] || [ "${STRATEGY}" = "recreate" ]; then
    UP_ARGS+=(--force-recreate)
fi

echo "Starting ${APP_SERVICE_NAME}"
docker compose up "${UP_ARGS[@]}" "${APP_SERVICE_NAME}"
docker compose ps
EOF_DEPLOY
'''
            }
        }

        stage('Restart Stack') {
            when { expression { params.ACTION == 'restart' } }
            steps {
                echo 'Restarting MarkForge stack...'
                sh '''#!/usr/bin/env bash
set -euo pipefail
ssh -T -o BatchMode=yes -o ConnectTimeout="${SSH_TIMEOUT}" "${SSH_ALIAS}" bash -s -- "${DEPLOY_DIR}" "${COMPOSE_PROJECT_NAME}" "${APP_SERVICE_NAME}" <<'EOF_RESTART'
set -euo pipefail
DEPLOY_DIR="$1"
COMPOSE_PROJECT_NAME="$2"
APP_SERVICE_NAME="$3"
export COMPOSE_PROJECT_NAME
cd "${DEPLOY_DIR}"
docker compose config --quiet
docker compose up -d --force-recreate "${APP_SERVICE_NAME}"
docker compose ps
EOF_RESTART
'''
            }
        }

        stage('Stop Stack') {
            when { expression { params.ACTION == 'stop' } }
            steps {
                echo 'Stopping MarkForge stack...'
                sh '''#!/usr/bin/env bash
set -euo pipefail
ssh -T -o BatchMode=yes -o ConnectTimeout="${SSH_TIMEOUT}" "${SSH_ALIAS}" bash -s -- "${DEPLOY_DIR}" "${COMPOSE_PROJECT_NAME}" <<'EOF_STOP'
set -euo pipefail
DEPLOY_DIR="$1"
COMPOSE_PROJECT_NAME="$2"
export COMPOSE_PROJECT_NAME
cd "${DEPLOY_DIR}"
docker compose config --quiet
docker compose stop
docker compose ps
EOF_STOP
'''
            }
        }

        stage('Remove Stack') {
            when { expression { params.ACTION == 'remove' } }
            steps {
                echo 'Removing MarkForge stack...'
                sh '''#!/usr/bin/env bash
set -euo pipefail
ssh -T -o BatchMode=yes -o ConnectTimeout="${SSH_TIMEOUT}" "${SSH_ALIAS}" bash -s -- "${DEPLOY_DIR}" "${COMPOSE_PROJECT_NAME}" "${DEPLOY_REMOVE_VOLUMES}" <<'EOF_REMOVE'
set -euo pipefail
DEPLOY_DIR="$1"
COMPOSE_PROJECT_NAME="$2"
REMOVE_VOLUMES="$3"
export COMPOSE_PROJECT_NAME
cd "${DEPLOY_DIR}"
docker compose config --quiet
DOWN_ARGS=(--remove-orphans)
if [ "${REMOVE_VOLUMES}" = "true" ]; then
    DOWN_ARGS+=(-v)
fi
docker compose down "${DOWN_ARGS[@]}"
docker compose ps || true
EOF_REMOVE
'''
            }
        }

        stage('Show Logs') {
            when { expression { params.ACTION == 'logs' } }
            steps {
                echo 'Showing MarkForge logs...'
                sh '''#!/usr/bin/env bash
set -euo pipefail
ssh -T -o BatchMode=yes -o ConnectTimeout="${SSH_TIMEOUT}" "${SSH_ALIAS}" bash -s -- "${DEPLOY_DIR}" "${COMPOSE_PROJECT_NAME}" "${APP_SERVICE_NAME}" <<'EOF_LOGS'
set -euo pipefail
DEPLOY_DIR="$1"
COMPOSE_PROJECT_NAME="$2"
APP_SERVICE_NAME="$3"
export COMPOSE_PROJECT_NAME
cd "${DEPLOY_DIR}"
docker compose config --quiet
docker compose logs --tail=250 "${APP_SERVICE_NAME}"
EOF_LOGS
'''
            }
        }

        stage('Show Status') {
            when { expression { params.ACTION == 'status' } }
            steps {
                echo 'Showing MarkForge status...'
                sh '''#!/usr/bin/env bash
set -euo pipefail
ssh -T -o BatchMode=yes -o ConnectTimeout="${SSH_TIMEOUT}" "${SSH_ALIAS}" bash -s -- "${DEPLOY_DIR}" "${COMPOSE_PROJECT_NAME}" "${APP_SERVICE_NAME}" "${APP_PORT}" "${HEALTH_PATH}" <<'EOF_STATUS'
set -euo pipefail
DEPLOY_DIR="$1"
COMPOSE_PROJECT_NAME="$2"
APP_SERVICE_NAME="$3"
APP_PORT="$4"
HEALTH_PATH="$5"
export COMPOSE_PROJECT_NAME
cd "${DEPLOY_DIR}"

echo "=== Compose Status ==="
docker compose config --quiet
docker compose ps
echo ""

echo "=== Container Health ==="
APP_CONTAINER="$(docker compose ps "${APP_SERVICE_NAME}" --format "{{.Name}}" | head -1 || true)"
if [ -n "${APP_CONTAINER}" ]; then
    docker inspect --format='{{.Name}} {{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}} {{.State.Status}}' "${APP_CONTAINER}"
else
    echo "App container not found"
fi
echo ""

echo "=== Local Endpoint ==="
curl -fsS --max-time 5 "http://127.0.0.1:${APP_PORT}${HEALTH_PATH}" || echo "Local health endpoint failed"
echo ""

echo "=== Version Info ==="
cat .deployment-version 2>/dev/null || true
EOF_STATUS
'''
            }
        }

        stage('Health Check') {
            when { expression { params.ACTION in ['deploy', 'restart'] } }
            steps {
                echo 'Running MarkForge health checks...'
                sh '''#!/usr/bin/env bash
set -euo pipefail

ssh -T \
    -o BatchMode=yes \
    -o ConnectTimeout="${SSH_TIMEOUT}" \
    -o ServerAliveInterval=15 \
    -o ServerAliveCountMax=3 \
    "${SSH_ALIAS}" \
    bash -s -- \
    "${DEPLOY_DIR}" \
    "${COMPOSE_PROJECT_NAME}" \
    "${APP_SERVICE_NAME}" \
    "${APP_PORT}" \
    "${HEALTH_PATH}" \
    "${DEPLOY_SLOT_LABEL}" <<'EOF_HEALTH'
set -euo pipefail

DEPLOY_DIR="$1"
COMPOSE_PROJECT_NAME="$2"
APP_SERVICE_NAME="$3"
APP_PORT="$4"
HEALTH_PATH="$5"
SLOT_LABEL="$6"

export COMPOSE_PROJECT_NAME
cd "${DEPLOY_DIR}"

echo "=== Health Check - MarkForge | Slot: ${SLOT_LABEL} ==="
docker compose config --quiet

APP_CONTAINER="$(docker compose ps "${APP_SERVICE_NAME}" --format "{{.Name}}" | head -1 || true)"
if [ -z "${APP_CONTAINER}" ]; then
    echo "App container not found"
    docker compose ps
    exit 1
fi

echo "App container: ${APP_CONTAINER}"

MAX_WAIT=90
ELAPSED=0
while [ "${ELAPSED}" -lt "${MAX_WAIT}" ]; do
    APP_STATE="$(docker inspect --format='{{.State.Status}}' "${APP_CONTAINER}" 2>/dev/null || echo "missing")"
    APP_HEALTH="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${APP_CONTAINER}" 2>/dev/null || echo "missing")"

    if [ "${APP_HEALTH}" = "healthy" ]; then
        echo "App container is healthy"
        break
    fi

    if [ "${APP_HEALTH}" = "none" ] && [ "${APP_STATE}" = "running" ]; then
        echo "App container has no Docker healthcheck but is running"
        break
    fi

    echo "Waiting for app health (${ELAPSED}s/${MAX_WAIT}s): state=${APP_STATE}, health=${APP_HEALTH}"
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

if [ "${ELAPSED}" -ge "${MAX_WAIT}" ]; then
    echo "App container did not become healthy in time"
    docker compose logs --tail=150 "${APP_SERVICE_NAME}"
    exit 1
fi

echo "Checking local HAProxy-facing endpoint"
curl -fsS --retry 6 --retry-delay 5 --max-time 5 "http://127.0.0.1:${APP_PORT}${HEALTH_PATH}"
echo ""
echo "Local endpoint OK: http://127.0.0.1:${APP_PORT}${HEALTH_PATH}"

echo ""
echo "=== App Version From Container ==="
docker compose exec -T "${APP_SERVICE_NAME}" sh -lc '
echo "APP_VERSION=$APP_VERSION"
echo "GIT_COMMIT=$GIT_COMMIT"
echo "GIT_COMMIT_FULL=$GIT_COMMIT_FULL"
echo "GIT_REF_TYPE=$GIT_REF_TYPE"
echo "GIT_REF_NAME=$GIT_REF_NAME"
echo "DEPLOYMENT_ID=$DEPLOYMENT_ID"
echo "SLOT_LABEL=$SLOT_LABEL"
' || true

echo ""
echo "=== Final Compose Status ==="
docker compose ps
EOF_HEALTH
'''
            }
        }

        stage('Deployment Summary') {
            when { expression { params.ACTION in ['deploy', 'restart'] } }
            steps {
                echo 'Collecting deployment summary...'
                sh '''#!/usr/bin/env bash
set -euo pipefail

ssh -T \
    -o BatchMode=yes \
    -o ConnectTimeout="${SSH_TIMEOUT}" \
    "${SSH_ALIAS}" \
    bash -s -- \
    "${DEPLOY_DIR}" \
    "${DEPLOYMENT_ID}" \
    "${APP_SERVICE_NAME}" \
    "${COMPOSE_PROJECT_NAME}" \
    "${APP_IMAGE_NAME}" \
    "${APP_PORT}" \
    "${HEALTH_PATH}" \
    "${PUBLIC_URL}" \
    "${DEPLOY_SLOT_LABEL}" <<'EOF_SUMMARY'
set -euo pipefail

DEPLOY_DIR="$1"
DEPLOYMENT_ID="$2"
APP_SERVICE_NAME="$3"
COMPOSE_PROJECT_NAME="$4"
APP_IMAGE_NAME="$5"
APP_PORT="$6"
HEALTH_PATH="$7"
PUBLIC_URL="$8"
SLOT_LABEL="$9"

export COMPOSE_PROJECT_NAME
cd "${DEPLOY_DIR}"

echo "=== Deployment Summary ==="
echo "Deployment ID:  ${DEPLOYMENT_ID}"
echo "Slot:           ${SLOT_LABEL}"
echo "Compose:        ${COMPOSE_PROJECT_NAME}"
echo "Deploy Dir:     ${DEPLOY_DIR}"
echo "Public URL:     ${PUBLIC_URL}"
echo "Local Health:   http://127.0.0.1:${APP_PORT}${HEALTH_PATH}"
echo "Repository:     $(git remote get-url origin)"
echo "Branch/HEAD:    $(git rev-parse --abbrev-ref HEAD)"
echo "Commit:         $(git rev-parse --short=12 HEAD)"
echo "Commit Message: $(git log -1 --pretty=%B | head -1)"
echo "Deploy Time:    $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

echo "=== Version Info ==="
cat .deployment-version || true
echo ""

echo "=== Container Status ==="
docker compose config --quiet
docker compose ps --format "table {{.Name}}\\t{{.Status}}\\t{{.Ports}}"
echo ""

echo "=== Resource Usage ==="
APP_CONTAINER="$(docker compose ps "${APP_SERVICE_NAME}" --format "{{.Name}}" | head -1 || true)"
if [ -n "${APP_CONTAINER}" ]; then
    docker stats --no-stream "${APP_CONTAINER}" --format "table {{.Name}}\\t{{.CPUPerc}}\\t{{.MemUsage}}\\t{{.NetIO}}\\t{{.BlockIO}}"
fi
echo ""

echo "=== Local Docker Image Tags ==="
docker images --format "table {{.Repository}}\\t{{.Tag}}\\t{{.ID}}\\t{{.CreatedSince}}\\t{{.Size}}" | grep -E "^${APP_IMAGE_NAME}[[:space:]]+" || true
EOF_SUMMARY
'''
            }
        }
    }

    post {
        success {
            script {
                echo ''
                echo '==============================================='
                echo "${params.ACTION.toUpperCase()} SUCCESSFUL"
                echo '==============================================='
                echo "Action:        ${params.ACTION}"
                echo "Client:        ${params.CLIENT}"
                echo "Environment:   ${params.ENVIRONMENT}"
                echo "Slot:          ${env.DEPLOY_SLOT_LABEL}"
                echo "Deploy Dir:    ${env.DEPLOY_DIR}"
                echo "Compose:       ${env.COMPOSE_PROJECT_NAME}"
                echo "Git Ref:       ${params.GIT_REF_TYPE}/${params.GIT_REF_NAME}"
                echo "Public URL:    ${env.PUBLIC_URL}"
                echo "Deployment ID: ${env.DEPLOYMENT_ID}"
                echo '==============================================='

                if (params.ACTION in ['deploy', 'remove']) {
                    try {
                        withCredentials([string(credentialsId: env.SLACK_CREDENTIAL_ID, variable: 'SLACK_WEBHOOK_URL')]) {
                            sh '''#!/usr/bin/env bash
set -euo pipefail

payload="$(mktemp)"
python3 - >"${payload}" <<'PY'
import json
import os

payload = {
    "username": "MarkForge Deployment Bot",
    "icon_emoji": ":white_check_mark:",
    "attachments": [{
        "color": "good",
        "title": "MarkForge - SUCCESS",
        "text": (
            "Deployment successful.\n"
            f"Client: *{os.getenv('DEPLOY_CLIENT', '')}* | Env: *{os.getenv('DEPLOY_ENVIRONMENT', '')}* | Slot: *{os.getenv('DEPLOY_SLOT_LABEL', '')}*\n"
            f"Action: *{os.getenv('DEPLOY_ACTION', '')}* | Ref: *{os.getenv('DEPLOY_GIT_REF_TYPE', '')}/{os.getenv('DEPLOY_GIT_REF_NAME', '')}*\n"
            f"Deploy Dir: `{os.getenv('DEPLOY_DIR', '')}`\n"
            f"Public URL: {os.getenv('PUBLIC_URL', '')}\n"
            f"Deployment ID: `{os.getenv('DEPLOYMENT_ID', '')}`\n"
            f"<{os.getenv('BUILD_URL', '')}console|View Jenkins Build>"
        ),
        "footer": f"Jenkins | {os.getenv('JOB_NAME', 'job')}",
    }],
}
print(json.dumps(payload))
PY

set +x
curl -sS -X POST -H 'Content-type: application/json' --data @"${payload}" "${SLACK_WEBHOOK_URL}" >/dev/null || true
rm -f "${payload}"
'''
                        }
                    } catch (Exception e) {
                        echo "Slack success notification skipped: ${e.message}"
                    }
                }
            }
        }

        failure {
            script {
                echo ''
                echo '==============================================='
                echo "${params.ACTION.toUpperCase()} FAILED"
                echo '==============================================='
                echo "Slot:       ${env.DEPLOY_SLOT_LABEL}"
                echo "Deploy Dir: ${env.DEPLOY_DIR}"
                echo 'Check the Jenkins logs above for details'
                echo '==============================================='

                if (params.ACTION in ['deploy', 'remove']) {
                    try {
                        withCredentials([string(credentialsId: env.SLACK_CREDENTIAL_ID, variable: 'SLACK_WEBHOOK_URL')]) {
                            sh '''#!/usr/bin/env bash
set +e

payload="$(mktemp)"
python3 - >"${payload}" <<'PY'
import json
import os

payload = {
    "username": "MarkForge Deployment Bot",
    "icon_emoji": ":x:",
    "attachments": [{
        "color": "danger",
        "title": "MarkForge - FAILURE",
        "text": (
            "Deployment failed.\n"
            f"Client: *{os.getenv('DEPLOY_CLIENT', '')}* | Env: *{os.getenv('DEPLOY_ENVIRONMENT', '')}* | Slot: *{os.getenv('DEPLOY_SLOT_LABEL', '')}*\n"
            f"Action: *{os.getenv('DEPLOY_ACTION', '')}* | Ref: *{os.getenv('DEPLOY_GIT_REF_TYPE', '')}/{os.getenv('DEPLOY_GIT_REF_NAME', '')}*\n"
            f"Deploy Dir: `{os.getenv('DEPLOY_DIR', '')}`\n"
            f"Deployment ID: `{os.getenv('DEPLOYMENT_ID', '')}`\n"
            f"<{os.getenv('BUILD_URL', '')}console|View Jenkins Build>"
        ),
        "footer": f"Jenkins | {os.getenv('JOB_NAME', 'job')}",
    }],
}
print(json.dumps(payload))
PY

set +x
curl -sS -X POST -H 'Content-type: application/json' --data @"${payload}" "${SLACK_WEBHOOK_URL}" >/dev/null || true
rm -f "${payload}"
'''
                        }
                    } catch (Exception e) {
                        echo "Slack failure notification skipped: ${e.message}"
                    }
                }

                try {
                    sh '''#!/usr/bin/env bash
set +e

ssh -T \
    -o BatchMode=yes \
    -o ConnectTimeout="${SSH_TIMEOUT}" \
    "${SSH_ALIAS}" \
    "cd '${DEPLOY_DIR}' && COMPOSE_PROJECT_NAME='${COMPOSE_PROJECT_NAME}' docker compose logs --tail=150 '${APP_SERVICE_NAME}' 2>&1 || echo 'Could not retrieve MarkForge logs'" || true
'''
                } catch (Exception e) {
                    echo "Could not retrieve container logs: ${e.message}"
                }
            }
        }

        always {
            echo 'Pipeline complete'
        }
    }
}
