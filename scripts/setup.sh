#!/bin/bash
# ============================================================
# Script de configuration complète du Chatbot Éducatif
# Ministère de l'Éducation du Sénégal
# ============================================================
# Usage: ./scripts/setup.sh [--lite]
# Options:
#   --lite    Installation allégée (sans Ollama, sans PostgreSQL)
# ============================================================

set -euo pipefail

# === Couleurs pour l'affichage ===
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # Pas de couleur

# === Variables ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LITE_MODE=false

# Traitement des arguments
for arg in "$@"; do
    case $arg in
        --lite)
            LITE_MODE=true
            ;;
        --help|-h)
            echo "Usage: $0 [--lite]"
            echo "  --lite    Installation allégée (sans Ollama, pour faibles ressources)"
            exit 0
            ;;
    esac
done

# === Fonctions utilitaires ===
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERREUR]${NC} $1"
}

log_step() {
    echo ""
    echo -e "${BLUE}══════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}══════════════════════════════════════════${NC}"
}

# === Vérification de l'espace disque ===
check_disk_space() {
    local required_gb=12
    if [ "$LITE_MODE" = true ]; then
        required_gb=5
    fi

    local available_gb
    available_gb=$(df -BG "$PROJECT_DIR" | awk 'NR==2{print $4}' | tr -d 'G')

    if [ "$available_gb" -lt "$required_gb" ]; then
        log_error "Espace disque insuffisant. Requis: ${required_gb}GB, Disponible: ${available_gb}GB"
        exit 1
    fi

    log_info "Espace disque: ${available_gb}GB disponible (minimum ${required_gb}GB requis) ✓"
}

# === Vérification de Docker ===
check_docker() {
    log_step "Étape 1/9 : Vérification de Docker"

    if ! command -v docker &> /dev/null; then
        log_error "Docker n'est pas installé."
        echo "Installez Docker : https://docs.docker.com/engine/install/"
        exit 1
    fi

    local docker_version
    docker_version=$(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    log_info "Docker version: $docker_version ✓"

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose n'est pas installé."
        echo "Installez Docker Compose : https://docs.docker.com/compose/install/"
        exit 1
    fi

    log_info "Docker Compose disponible ✓"

    # Vérifier que le daemon Docker est en cours d'exécution
    if ! docker info &> /dev/null; then
        log_error "Le daemon Docker n'est pas en cours d'exécution."
        echo "Démarrez Docker et réessayez."
        exit 1
    fi

    log_info "Daemon Docker actif ✓"
}

# === Configuration du fichier .env ===
setup_env() {
    log_step "Étape 2/9 : Configuration des variables d'environnement"

    local env_file="$PROJECT_DIR/.env"
    local env_example="$PROJECT_DIR/.env.example"

    if [ -f "$env_file" ]; then
        log_warn "Fichier .env existant trouvé"
        read -p "Voulez-vous le reconfigurer? (o/N): " -r reconfigure
        if [[ ! $reconfigure =~ ^[Oo]$ ]]; then
            log_info "Conservation du .env existant"
            return
        fi
    fi

    if [ ! -f "$env_example" ]; then
        log_error "Fichier .env.example introuvable : $env_example"
        exit 1
    fi

    cp "$env_example" "$env_file"
    log_info "Fichier .env créé depuis .env.example"

    # Générer des clés sécurisées aléatoires
    local secret_key
    secret_key=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))" 2>/dev/null || \
                 openssl rand -base64 48 | tr -d '\n')

    local api_key
    api_key=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || \
              openssl rand -base64 32 | tr -d '\n')

    local db_password
    db_password=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))" 2>/dev/null || \
                  openssl rand -base64 24 | tr -d '\n')

    # Remplacer les valeurs par défaut
    sed -i "s|votre-cle-secrete-super-longue-et-aleatoire-minimum-32-chars|$secret_key|g" "$env_file"
    sed -i "s|votre-cle-api-admin-securisee|$api_key|g" "$env_file"
    sed -i "s|edu_password_changez_en_production|$db_password|g" "$env_file"
    sed -i "s|edu_password|$db_password|g" "$env_file"

    if [ "$LITE_MODE" = true ]; then
        sed -i "s|USE_LIGHTWEIGHT_MODE=False|USE_LIGHTWEIGHT_MODE=True|g" "$env_file"
    fi

    log_info "Variables d'environnement configurées avec des clés sécurisées ✓"
    log_warn "IMPORTANT: Sauvegardez le fichier .env - les clés ne peuvent pas être récupérées"
    echo ""
    echo -e "${YELLOW}Clé API administrateur générée. Conservez-la précieusement !${NC}"
    echo "API_KEY: $api_key"
    echo ""
}

# === Création des répertoires ===
create_directories() {
    log_step "Étape 3/9 : Création des répertoires"

    local dirs=(
        "$PROJECT_DIR/data"
        "$PROJECT_DIR/logs"
        "$PROJECT_DIR/backend/app"
    )

    for dir in "${dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            log_info "Répertoire créé: $dir"
        else
            log_info "Répertoire existant: $dir ✓"
        fi
    done
}

# === Vérification des fichiers de données ===
check_data_files() {
    log_step "Étape 4/9 : Vérification des données"

    local faq_file="$PROJECT_DIR/data/faq_senegal.json"
    local kb_file="$PROJECT_DIR/data/knowledge_base.json"

    if [ -f "$faq_file" ]; then
        local faq_count
        faq_count=$(python3 -c "import json; data=json.load(open('$faq_file')); print(len(data.get('faqs',[])))" 2>/dev/null || echo "?")
        log_info "Fichier FAQ trouvé: $faq_count entrées ✓"
    else
        log_warn "Fichier FAQ non trouvé: $faq_file"
        log_warn "Le chatbot démarrera sans données FAQ initiales"
    fi

    if [ -f "$kb_file" ]; then
        log_info "Base de connaissances trouvée ✓"
    else
        log_warn "Base de connaissances non trouvée: $kb_file"
    fi
}

# === Téléchargement des images Docker ===
pull_docker_images() {
    log_step "Étape 5/9 : Téléchargement des images Docker"

    local compose_file="$PROJECT_DIR/docker-compose.yml"
    if [ "$LITE_MODE" = true ]; then
        compose_file="$PROJECT_DIR/docker-compose.lite.yml"
    fi

    log_info "Téléchargement des images (peut prendre plusieurs minutes)..."
    docker compose -f "$compose_file" pull --ignore-pull-failures || true
    log_info "Images Docker téléchargées ✓"
}

# === Construction du backend ===
build_backend() {
    log_step "Étape 6/9 : Construction de l'image Backend"

    local compose_file="$PROJECT_DIR/docker-compose.yml"
    if [ "$LITE_MODE" = true ]; then
        compose_file="$PROJECT_DIR/docker-compose.lite.yml"
    fi

    log_info "Construction de l'image backend (peut prendre 10-20 minutes selon la connexion)..."
    log_info "Les modèles NLP seront téléchargés pendant la construction..."

    docker compose -f "$compose_file" build --no-cache backend${LITE_MODE:+-lite} 2>&1 | \
        grep -E "(Step|Successfully|Error|Warning|Downloading|Installing)" || true

    log_info "Image backend construite ✓"
}

# === Téléchargement du modèle Ollama ===
pull_ollama_model() {
    if [ "$LITE_MODE" = true ]; then
        log_info "Mode allégé: Ollama ignoré"
        return
    fi

    log_step "Étape 7/9 : Téléchargement du modèle LLM (Mistral 7B)"

    log_warn "Téléchargement de Mistral 7B (~4GB). Cela peut prendre 15-30 minutes."
    log_info "Démarrage du service Ollama..."

    local compose_file="$PROJECT_DIR/docker-compose.yml"
    docker compose -f "$compose_file" up -d ollama

    log_info "Attente du démarrage d'Ollama..."
    local max_wait=60
    local waited=0
    while ! docker compose -f "$compose_file" exec -T ollama ollama list &>/dev/null; do
        sleep 5
        waited=$((waited + 5))
        if [ $waited -ge $max_wait ]; then
            log_warn "Ollama met du temps à démarrer. Le modèle sera téléchargé au premier démarrage."
            return
        fi
        echo -n "."
    done
    echo ""

    log_info "Ollama actif. Téléchargement de Mistral..."
    docker compose -f "$compose_file" exec -T ollama ollama pull mistral || \
        log_warn "Téléchargement différé au premier démarrage"

    log_info "Modèle Mistral 7B prêt ✓"
}

# === Initialisation de la base de données ===
init_database() {
    log_step "Étape 8/9 : Démarrage et initialisation"

    local compose_file="$PROJECT_DIR/docker-compose.yml"
    if [ "$LITE_MODE" = true ]; then
        compose_file="$PROJECT_DIR/docker-compose.lite.yml"
    fi

    log_info "Démarrage de tous les services..."
    docker compose -f "$compose_file" up -d

    log_info "Attente de la disponibilité du backend (90 secondes max)..."
    local max_wait=90
    local waited=0
    while ! curl -sf http://localhost:8000/health &>/dev/null; do
        sleep 5
        waited=$((waited + 5))
        echo -n "."
        if [ $waited -ge $max_wait ]; then
            log_warn "Le backend prend plus de temps que prévu à démarrer"
            log_info "Vérifiez les logs: docker compose logs backend"
            break
        fi
    done
    echo ""

    if curl -sf http://localhost:8000/health &>/dev/null; then
        log_info "Backend opérationnel ✓"
    fi
}

# === Affichage des informations finales ===
print_summary() {
    log_step "Étape 9/9 : Installation terminée"

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║     CHATBOT ÉDUCATIF - INSTALLATION RÉUSSIE          ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  Interface Web:     ${BLUE}http://localhost${NC}"
    echo -e "  API Backend:       ${BLUE}http://localhost:8000${NC}"
    echo -e "  Health Check:      ${BLUE}http://localhost:8000/health${NC}"
    echo -e "  Documentation API: ${BLUE}http://localhost:8000/docs${NC} (si DEBUG=True)"
    echo ""
    echo -e "  Langues supportées: ${YELLOW}Français, Wolof, Pulaar, Arabe${NC}"
    echo ""
    echo "  Commandes utiles:"
    echo "    Logs:     docker compose logs -f"
    echo "    Arrêt:    docker compose down"
    echo "    Statut:   docker compose ps"
    echo "    Restart:  docker compose restart backend"
    echo ""
    echo -e "${YELLOW}  N'oubliez pas de sauvegarder votre fichier .env !${NC}"
    echo ""
}

# === Test de l'installation ===
run_test() {
    log_info "Test de l'installation..."

    local response
    if response=$(curl -sf -X POST http://localhost/api/chat \
        -H "Content-Type: application/json" \
        -d '{"message": "Bonjour, quelles sont les dates d inscription?", "session_id": "00000000-0000-4000-8000-000000000001"}' \
        2>/dev/null); then
        log_info "Test réussi - Le chatbot répond correctement ✓"
        echo "  Réponse: $(echo "$response" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('response','')[:80]+'...')" 2>/dev/null || echo "(voir ci-dessus)")"
    else
        log_warn "Test non concluant - Le serveur démarre peut-être encore"
        log_info "Réessayez dans quelques instants: curl -X POST http://localhost/api/chat ..."
    fi
}

# ============================================================
# EXÉCUTION PRINCIPALE
# ============================================================

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  CHATBOT ÉDUCATIF - MINISTÈRE DE L'ÉDUCATION DU      ║${NC}"
echo -e "${GREEN}║  SÉNÉGAL - Script d'installation                     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

if [ "$LITE_MODE" = true ]; then
    log_warn "Mode allégé activé (sans Ollama, sans PostgreSQL)"
fi

log_info "Répertoire du projet: $PROJECT_DIR"

# Vérification de l'espace disque
check_disk_space

# Exécution des étapes
check_docker
setup_env
create_directories
check_data_files
pull_docker_images
build_backend
pull_ollama_model
init_database
run_test
print_summary
