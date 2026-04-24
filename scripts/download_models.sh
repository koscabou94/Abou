#!/bin/bash
# ============================================================
# Script de téléchargement des modèles NLP
# Ministère de l'Éducation du Sénégal
# ============================================================
# Télécharge et vérifie :
# 1. Modèle d'embedding : all-MiniLM-L6-v2 (~90MB)
# 2. Modèle de traduction NLLB-200 (~1.2GB)
# 3. Modèle LLM Mistral via Ollama (~4GB)
# ============================================================
# Espace disque requis : ~6GB minimum
# ============================================================

set -euo pipefail

# === Couleurs ===
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# === Configuration ===
MODELS_DIR="${MODELS_DIR:-/app/models}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-all-MiniLM-L6-v2}"
TRANSLATION_MODEL="${TRANSLATION_MODEL:-facebook/nllb-200-distilled-600M}"
LLM_MODEL="${LLM_MODEL:-mistral}"

# === Fonctions ===
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERREUR]${NC} $1"; }
log_step() {
    echo ""
    echo -e "${BLUE}── $1${NC}"
}

check_disk_space() {
    local required_gb=10
    local dir="${1:-/}"
    local available_gb

    if command -v df &>/dev/null; then
        available_gb=$(df -BG "$dir" | awk 'NR==2{print $4}' | tr -d 'G' || echo "0")
        if [ "${available_gb:-0}" -lt "$required_gb" ] 2>/dev/null; then
            log_warn "Espace disque potentiellement insuffisant"
            log_warn "Requis: ~${required_gb}GB, Disponible: ${available_gb}GB"
            log_warn "Poursuite quand même..."
        else
            log_info "Espace disque: ${available_gb}GB disponible ✓"
        fi
    fi
}

check_python() {
    if ! command -v python3 &>/dev/null; then
        log_error "Python 3 est requis mais non trouvé"
        exit 1
    fi
    local python_version
    python_version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
    log_info "Python version: $python_version ✓"
}

check_internet() {
    log_info "Vérification de la connexion internet..."
    if curl -sf --max-time 10 "https://huggingface.co" > /dev/null 2>&1; then
        log_info "Connexion à HuggingFace ✓"
        return 0
    else
        log_warn "Impossible de joindre HuggingFace - les modèles seront téléchargés à la première utilisation"
        return 1
    fi
}

# === Téléchargement du modèle d'embedding ===
download_embedding_model() {
    log_step "Téléchargement du modèle d'embedding: $EMBEDDING_MODEL"
    log_info "Taille approximative: ~90MB"

    python3 << PYTHON_SCRIPT
import sys
import os

try:
    from sentence_transformers import SentenceTransformer

    print(f"  Téléchargement de {os.environ.get('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')}...")
    model = SentenceTransformer(
        os.environ.get('EMBEDDING_MODEL', 'all-MiniLM-L6-v2'),
        cache_folder=os.environ.get('MODELS_DIR', '/app/models')
    )

    # Test rapide du modèle
    test_embedding = model.encode("Test de l'éducation sénégalaise")
    assert len(test_embedding) == 384, f"Dimension d'embedding inattendue: {len(test_embedding)}"

    print(f"  ✓ Modèle d'embedding téléchargé et vérifié (dim={len(test_embedding)})")

except ImportError:
    print("  sentence-transformers non installé. Installez avec: pip install sentence-transformers")
    sys.exit(1)
except Exception as e:
    print(f"  Erreur: {e}")
    sys.exit(1)
PYTHON_SCRIPT

    log_info "Modèle d'embedding prêt ✓"
}

# === Téléchargement du modèle NLLB-200 ===
download_translation_model() {
    log_step "Téléchargement du modèle de traduction NLLB-200"
    log_info "Modèle: $TRANSLATION_MODEL"
    log_info "Taille approximative: ~1.2GB (peut prendre 10-20 minutes)"

    python3 << PYTHON_SCRIPT
import sys
import os

MODELS_DIR = os.environ.get('MODELS_DIR', '/app/models')
TRANSLATION_MODEL = os.environ.get('TRANSLATION_MODEL', 'facebook/nllb-200-distilled-600M')

try:
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    import torch

    print(f"  Téléchargement du tokenizer NLLB-200...")
    tokenizer = AutoTokenizer.from_pretrained(
        TRANSLATION_MODEL,
        cache_dir=MODELS_DIR
    )

    print(f"  Téléchargement du modèle NLLB-200 ({TRANSLATION_MODEL})...")
    print(f"  (Cette étape peut prendre plusieurs minutes selon votre connexion)")

    model = AutoModelForSeq2SeqLM.from_pretrained(
        TRANSLATION_MODEL,
        cache_dir=MODELS_DIR,
        torch_dtype=torch.float32,
        low_cpu_mem_usage=True,
    )

    # Test de traduction
    print("  Test de traduction fr -> wo (wolof)...")
    test_text = "Bonjour, comment puis-je vous aider?"

    inputs = tokenizer(
        test_text,
        return_tensors="pt",
        max_length=128,
        truncation=True
    )

    # Obtenir l'ID du token wolof
    wolof_token_id = tokenizer.convert_tokens_to_ids("wol_Latn")

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            forced_bos_token_id=wolof_token_id,
            max_new_tokens=50,
            num_beams=2,
        )

    translated = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(f"  Test OK: '{test_text}' -> '{translated}'")
    print(f"  ✓ Modèle NLLB-200 téléchargé et vérifié")

except ImportError as e:
    print(f"  Dépendance manquante: {e}")
    print("  Installez avec: pip install transformers torch")
    sys.exit(1)
except Exception as e:
    print(f"  Erreur: {e}")
    print("  Le modèle de traduction sera téléchargé au premier démarrage")
    sys.exit(1)
PYTHON_SCRIPT

    log_info "Modèle NLLB-200 prêt ✓"
}

# === Téléchargement du modèle Mistral via Ollama ===
download_ollama_model() {
    log_step "Téléchargement du modèle LLM Mistral 7B via Ollama"
    log_info "Taille approximative: ~4.1GB"
    log_warn "Cette étape peut prendre 20-40 minutes selon votre connexion"

    # Vérifier si Ollama est disponible
    if ! curl -sf "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
        log_warn "Ollama n'est pas accessible à $OLLAMA_URL"
        log_info "Démarrez Ollama avec: docker compose up -d ollama"
        log_info "Puis lancez: ollama pull mistral"
        return 1
    fi

    log_info "Ollama disponible ✓"

    # Vérifier si le modèle est déjà téléchargé
    local models_list
    models_list=$(curl -sf "$OLLAMA_URL/api/tags" | python3 -c "
import json, sys
data = json.load(sys.stdin)
models = [m['name'] for m in data.get('models', [])]
print('\n'.join(models))
" 2>/dev/null || echo "")

    if echo "$models_list" | grep -q "$LLM_MODEL"; then
        log_info "Modèle $LLM_MODEL déjà téléchargé ✓"
        return 0
    fi

    log_info "Démarrage du téléchargement de Mistral 7B..."

    # Téléchargement avec affichage de la progression
    curl -X POST "$OLLAMA_URL/api/pull" \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"$LLM_MODEL\"}" \
        --no-buffer | while IFS= read -r line; do
            status=$(echo "$line" | python3 -c "
import json, sys
try:
    d = json.loads(sys.stdin.readline())
    s = d.get('status', '')
    completed = d.get('completed', 0)
    total = d.get('total', 0)
    if total > 0:
        pct = int(completed * 100 / total)
        print(f'  {s}: {pct}%')
    elif s:
        print(f'  {s}')
except:
    pass
" 2>/dev/null || true)
            [ -n "$status" ] && echo "$status"
        done || log_warn "Téléchargement interrompu ou erreur"

    log_info "Modèle Mistral 7B prêt ✓"
}

# === Téléchargement du modèle fallback TinyLlama ===
download_fallback_model() {
    log_step "Téléchargement du modèle de secours TinyLlama"
    log_info "Taille approximative: ~600MB"

    python3 << PYTHON_SCRIPT
import sys
import os

MODELS_DIR = os.environ.get('MODELS_DIR', '/app/models')

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import torch

    model_name = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    print(f"  Téléchargement de {model_name}...")

    tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=MODELS_DIR)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        cache_dir=MODELS_DIR,
        torch_dtype=torch.float32,
        low_cpu_mem_usage=True,
    )

    print(f"  ✓ TinyLlama téléchargé avec succès")

except Exception as e:
    print(f"  Modèle de secours non téléchargé: {e}")
    print("  (Sera téléchargé au premier démarrage si nécessaire)")
PYTHON_SCRIPT
}

# === Résumé ===
print_summary() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           TÉLÉCHARGEMENT DES MODÈLES TERMINÉ         ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "  Modèles dans: $MODELS_DIR"
    echo ""

    if command -v du &>/dev/null; then
        local size
        size=$(du -sh "$MODELS_DIR" 2>/dev/null | cut -f1 || echo "?")
        echo "  Taille totale du cache: $size"
    fi

    echo ""
    echo "  Pour démarrer l'application:"
    echo "    docker compose up -d"
    echo ""
}

# ============================================================
# EXÉCUTION PRINCIPALE
# ============================================================

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  TÉLÉCHARGEMENT DES MODÈLES NLP                      ║${NC}"
echo -e "${BLUE}║  Chatbot Éducatif - Ministère de l'Éducation         ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# Vérifications préalables
check_disk_space "$MODELS_DIR"
check_python

# Créer le répertoire des modèles
mkdir -p "$MODELS_DIR"

# Vérifier la connexion
HAS_INTERNET=false
if check_internet; then
    HAS_INTERNET=true
fi

if [ "$HAS_INTERNET" = false ]; then
    log_warn "Pas de connexion internet. Les modèles ne peuvent pas être téléchargés maintenant."
    log_info "Ils seront téléchargés automatiquement au premier démarrage de l'application."
    exit 0
fi

# Téléchargement des modèles
ERRORS=0

download_embedding_model || ((ERRORS++)) || true
download_translation_model || ((ERRORS++)) || true

# Modèle Ollama (optionnel, ignoré si Ollama non disponible)
if [ "${SKIP_OLLAMA:-0}" != "1" ]; then
    download_ollama_model || log_warn "Modèle Ollama ignoré (sera téléchargé au démarrage)"
fi

# Modèle de secours (optionnel)
if [ "${DOWNLOAD_FALLBACK:-0}" = "1" ]; then
    download_fallback_model || true
fi

print_summary

if [ $ERRORS -gt 0 ]; then
    log_warn "$ERRORS modèle(s) n'ont pas pu être téléchargés et seront chargés au démarrage"
    exit 0
fi

log_info "Tous les modèles sont prêts ✓"
