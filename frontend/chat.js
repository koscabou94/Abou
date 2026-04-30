/**
 * DPTIC - Assistant Éducatif Client Logic
 * Features: Markdown, Streaming, Dark Mode, Sidebar, File Upload, Internationalization
 */

(function () {
    "use strict";

    // === CONFIGURATION & STATE ===
    const CONFIG = {
        API_URL: window.API_URL || "/api",
        STREAM_SPEED: 8,
        MAX_HISTORY: 50,
        MAX_FILE_SIZE: 10 * 1024 * 1024, // 10 MB
        ALLOWED_TYPES: ["image/jpeg", "image/png", "image/gif", "image/webp", "application/pdf",
            "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/plain", "text/csv"]
    };

    let state = {
        lang: localStorage.getItem("simen_lang") || "fr",
        theme: localStorage.getItem("simen_theme") || "light",
        isSidebarOpen: window.innerWidth > 900,
        history: JSON.parse(localStorage.getItem("simen_history") || "[]"),
        // Messages stockés localement par session : { sessionId: [{role, content}, ...] }
        sessionMessages: JSON.parse(localStorage.getItem("simen_session_messages") || "{}"),
        currentSessionId: crypto.randomUUID(),
        isTyping: false,
        messages: {},
        attachedFiles: [],
        deleteTargetId: null,
        // Contexte de clarification : message original en attente d'une précision
        pendingClarificationContext: null,
        // === AUTH ===
        token: localStorage.getItem("edubot_token") || null,
        user: JSON.parse(localStorage.getItem("edubot_user") || "null"),
        // Methode active dans le modal de login
        authMethod: "ien",
        // Flag : OTP a deja ete demande pour la methode courante
        otpSent: false,
    };

    // === HELPER : appel API avec Authorization Bearer si connecte ===
    function authHeaders(extra) {
        const h = Object.assign({ "Content-Type": "application/json" }, extra || {});
        if (state.token) h["Authorization"] = `Bearer ${state.token}`;
        return h;
    }

    // === DOM ELEMENTS ===
    const elements = {
        app: document.querySelector(".app-layout"),
        sidebar: document.getElementById("sidebar"),
        sidebarToggle: document.getElementById("sidebar-toggle-btn"),
        mobileMenuBtn: document.getElementById("mobile-menu-btn"),
        themeToggle: document.getElementById("theme-toggle"),
        historyList: document.getElementById("sidebar-history"),
        newChatBtn: document.getElementById("new-chat-btn"),
        settingsBtn: document.getElementById("settings-btn"),
        settingsModal: document.getElementById("settings-modal"),

        chatViewport: document.getElementById("chat-viewport"),
        messagesArea: document.getElementById("messages-area"),
        welcomeSection: document.getElementById("welcome-section"),
        quickGrid: document.getElementById("quick-questions-grid"),
        typingIndicator: document.getElementById("typing-indicator"),
        typingText: document.getElementById("typing-text"),

        messageInput: document.getElementById("message-input"),
        sendBtn: document.getElementById("send-btn"),
        langBtns: document.querySelectorAll(".lang-pill"),

        attachBtn: document.getElementById("attach-btn"),
        fileInput: document.getElementById("file-input"),
        filePreview: document.getElementById("file-preview"),
        deleteModal: document.getElementById("delete-modal"),
        deleteCancelBtn: document.getElementById("delete-cancel-btn"),
        deleteConfirmBtn: document.getElementById("delete-confirm-btn"),
        homeBtn: document.getElementById("home-btn")
    };

    // === LOCALIZATION (Français uniquement) ===
    const I18N = {
        fr: {
            welcomeH2: "Bonjour, comment puis-je vous aider ?",
            welcomeP: "Posez vos questions sur l'éducation, les carrières, les plateformes et les démarches administratives.",
            placeholder: "Posez votre question...",
            typing: "Recherche en cours...",
            historyEmpty: "Aucune conversation récente",
            newChat: "Nouveau Chat",
            errorNetwork: "Connexion au serveur impossible. Vérifiez votre accès internet.",
            errorServer: "Désolé, une erreur technique est survenue. Veuillez réessayer.",
            quickQs: [
                { text: "Donne-moi 3 exercices de maths CM2" },
                { text: "Quel est le programme de français en CE1 ?" },
                { text: "Comment se connecter à PLANETE ?" },
                { text: "Fiche pédagogique de mathématiques pour le CE2" }
            ]
        }
    };

    // === MARKED.JS HARDENING (defense ultime contre le gras) ===
    // Override le renderer marked pour que MEME SI un **texte** ou
    // *texte* arrive, il soit rendu en texte simple (pas <strong>/<em>).
    // C'est la 5e barriere contre le gras (apres : SYSTEM_PROMPT,
    // _clean_llm_response, stripBold, et CSS).
    if (typeof marked !== "undefined" && marked.Renderer) {
        const noBoldRenderer = new marked.Renderer();
        // Ignorer completement le rendu strong/em : retourner juste le texte
        noBoldRenderer.strong = (text) => {
            // marked v4+ passe parfois un objet { text }
            if (typeof text === "object" && text !== null && "text" in text) text = text.text;
            return String(text);
        };
        noBoldRenderer.em = (text) => {
            if (typeof text === "object" && text !== null && "text" in text) text = text.text;
            return String(text);
        };
        marked.setOptions({ renderer: noBoldRenderer });
    }

    // ============================================================
    // AUTHENTIFICATION
    // ============================================================

    function persistAuth() {
        if (state.token) localStorage.setItem("edubot_token", state.token);
        else              localStorage.removeItem("edubot_token");
        if (state.user)  localStorage.setItem("edubot_user", JSON.stringify(state.user));
        else              localStorage.removeItem("edubot_user");
    }

    /** Met à jour le bloc auth dans la sidebar (login button vs user card). */
    function renderAuthBlock() {
        const loginBtn = document.getElementById("auth-login-btn");
        const userCard = document.getElementById("auth-user-card");
        if (!loginBtn || !userCard) return;

        if (state.user && state.user.is_authenticated) {
            loginBtn.classList.add("hidden");
            userCard.classList.remove("hidden");
            const name = state.user.full_name || "Utilisateur";
            const initial = name.trim().charAt(0).toUpperCase() || "?";
            document.getElementById("auth-avatar").textContent = initial;
            document.getElementById("auth-user-name").textContent = name;
            const profile = state.user.profile_type || "";
            const level = state.user.level ? ` · ${state.user.level}` : "";
            document.getElementById("auth-user-role").textContent =
                profile.charAt(0).toUpperCase() + profile.slice(1) + level;
        } else {
            loginBtn.classList.remove("hidden");
            userCard.classList.add("hidden");
        }
    }

    function showLoginModal() {
        const modal = document.getElementById("login-modal");
        if (!modal) return;
        // Reset etat du modal
        state.authMethod = "ien";
        state.otpSent = false;
        document.querySelectorAll(".auth-tab").forEach(t =>
            t.classList.toggle("active", t.dataset.method === "ien"));
        updateAuthFormForMethod("ien");
        document.getElementById("auth-id-input").value = "";
        document.getElementById("auth-password-input").value = "";
        document.getElementById("auth-otp-input").value = "";
        document.getElementById("auth-error").classList.add("hidden");
        modal.classList.remove("hidden");
        if (window.lucide) lucide.createIcons();
    }

    function hideLoginModal() {
        const modal = document.getElementById("login-modal");
        if (modal) modal.classList.add("hidden");
    }

    function showProfileModal() {
        const modal = document.getElementById("profile-modal");
        if (!modal) return;
        // Reset le formulaire profil
        document.querySelectorAll(".profile-type-btn").forEach(b => b.classList.remove("selected"));
        document.getElementById("profile-name-input").value = state.user?.full_name || "";
        document.getElementById("profile-school-input").value = state.user?.school || "";
        document.getElementById("profile-level-select").value = state.user?.level || "";
        document.getElementById("profile-level-field").classList.add("hidden");
        document.getElementById("profile-error").classList.add("hidden");
        modal.classList.remove("hidden");
        if (window.lucide) lucide.createIcons();
    }

    function hideProfileModal() {
        const modal = document.getElementById("profile-modal");
        if (modal) modal.classList.add("hidden");
    }

    /** Adapte les champs du formulaire de login selon la methode active. */
    function updateAuthFormForMethod(method) {
        state.authMethod = method;
        state.otpSent = false;
        const labelEl = document.getElementById("auth-id-label");
        const idInput = document.getElementById("auth-id-input");
        const hintEl  = document.getElementById("auth-id-hint");
        const passField = document.getElementById("auth-password-field");
        const otpField  = document.getElementById("auth-otp-field");
        const submitBtn = document.getElementById("auth-submit-btn");

        if (method === "ien") {
            labelEl.textContent = "Votre IEN";
            idInput.placeholder = "Ex : 200001";
            idInput.type = "text";
            idInput.inputMode = "numeric";
            hintEl.textContent = "Identifiant Éducation Nationale (5 à 12 chiffres)";
            passField.classList.remove("hidden");
            otpField.classList.add("hidden");
            submitBtn.textContent = "Se connecter";
        } else if (method === "email") {
            labelEl.textContent = "Adresse e-mail";
            idInput.placeholder = "prenom.nom@education.sn";
            idInput.type = "email";
            idInput.inputMode = "email";
            hintEl.textContent = "Nous vous enverrons un code à 6 chiffres.";
            passField.classList.add("hidden");
            otpField.classList.add("hidden");
            submitBtn.textContent = "Recevoir un code";
        } else if (method === "phone") {
            labelEl.textContent = "Numéro de téléphone";
            idInput.placeholder = "+221 77 696 15 45";
            idInput.type = "tel";
            idInput.inputMode = "tel";
            hintEl.textContent = "Format international avec l'indicatif (+221).";
            passField.classList.add("hidden");
            otpField.classList.add("hidden");
            submitBtn.textContent = "Recevoir un code";
        }
    }

    function showAuthError(message) {
        const el = document.getElementById("auth-error");
        if (!el) return;
        el.textContent = message;
        el.classList.remove("hidden");
    }

    /** Soumission du formulaire de login. */
    async function handleAuthSubmit(e) {
        e.preventDefault();
        const submitBtn = document.getElementById("auth-submit-btn");
        const errEl = document.getElementById("auth-error");
        errEl.classList.add("hidden");
        submitBtn.disabled = true;

        const method = state.authMethod;
        const identifier = document.getElementById("auth-id-input").value.trim();
        const password = document.getElementById("auth-password-input").value;
        const otp = document.getElementById("auth-otp-input").value.trim();

        if (!identifier) {
            showAuthError("Veuillez saisir votre identifiant.");
            submitBtn.disabled = false;
            return;
        }

        try {
            // Etape 1 : pour email/phone, demander d'abord un OTP
            if ((method === "email" || method === "phone") && !state.otpSent) {
                const r = await fetch(`${CONFIG.API_URL}/auth/request-otp`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ method, identifier }),
                });
                if (!r.ok) {
                    const d = await r.json().catch(() => null);
                    throw new Error(d?.detail || "Erreur d'envoi du code.");
                }
                state.otpSent = true;
                document.getElementById("auth-otp-field").classList.remove("hidden");
                submitBtn.textContent = "Valider le code";
                submitBtn.disabled = false;
                return;
            }

            // Etape 2 : login (IEN+password OU email/phone+OTP)
            const body = { method, identifier, session_id: state.currentSessionId };
            if (method === "ien")  body.password = password;
            if (method === "email" || method === "phone") body.otp = otp;

            const r = await fetch(`${CONFIG.API_URL}/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            const data = await r.json();
            if (!r.ok) throw new Error(data?.detail || "Connexion échouée.");

            state.token = data.access_token;
            state.user = data.user;
            persistAuth();
            renderAuthBlock();
            applyLanguage(state.lang);  // re-render quick cards selon profil
            hideLoginModal();

            if (!data.profile_complete) {
                showProfileModal();
            }
        } catch (err) {
            showAuthError(err.message || "Erreur inconnue.");
        } finally {
            submitBtn.disabled = false;
        }
    }

    /** Soumission du formulaire de profil (premier login). */
    async function handleProfileSubmit(e) {
        e.preventDefault();
        const submitBtn = document.getElementById("profile-submit-btn");
        const errEl = document.getElementById("profile-error");
        errEl.classList.add("hidden");
        submitBtn.disabled = true;

        const selected = document.querySelector(".profile-type-btn.selected");
        const profile_type = selected ? selected.dataset.value : null;
        const full_name = document.getElementById("profile-name-input").value.trim();
        const school = document.getElementById("profile-school-input").value.trim();
        const level = document.getElementById("profile-level-select").value || null;

        if (!profile_type) {
            errEl.textContent = "Choisissez votre profil.";
            errEl.classList.remove("hidden");
            submitBtn.disabled = false;
            return;
        }
        if (!full_name) {
            errEl.textContent = "Indiquez votre nom complet.";
            errEl.classList.remove("hidden");
            submitBtn.disabled = false;
            return;
        }
        if ((profile_type === "eleve" || profile_type === "parent") && !level) {
            errEl.textContent = "Indiquez le niveau scolaire.";
            errEl.classList.remove("hidden");
            submitBtn.disabled = false;
            return;
        }

        try {
            const r = await fetch(`${CONFIG.API_URL}/auth/register`, {
                method: "POST",
                headers: authHeaders(),
                body: JSON.stringify({ profile_type, full_name, school, level }),
            });
            const data = await r.json();
            if (!r.ok) throw new Error(data?.detail || "Échec de l'enregistrement.");

            state.token = data.access_token;
            state.user = data.user;
            persistAuth();
            renderAuthBlock();
            applyLanguage(state.lang);
            hideProfileModal();
        } catch (err) {
            errEl.textContent = err.message || "Erreur inconnue.";
            errEl.classList.remove("hidden");
        } finally {
            submitBtn.disabled = false;
        }
    }

    function logout() {
        state.token = null;
        state.user = null;
        persistAuth();
        renderAuthBlock();
        applyLanguage(state.lang);
    }

    function attachAuthListeners() {
        // Onglets
        document.querySelectorAll(".auth-tab").forEach(tab => {
            tab.onclick = () => {
                document.querySelectorAll(".auth-tab").forEach(t => t.classList.remove("active"));
                tab.classList.add("active");
                updateAuthFormForMethod(tab.dataset.method);
            };
        });
        // Form login
        const form = document.getElementById("auth-form");
        if (form) form.onsubmit = handleAuthSubmit;
        // Bouton invite
        const guestBtn = document.getElementById("auth-guest-btn");
        if (guestBtn) guestBtn.onclick = () => hideLoginModal();
        // Boutons sidebar
        const loginBtn = document.getElementById("auth-login-btn");
        if (loginBtn) loginBtn.onclick = showLoginModal;
        const logoutBtn = document.getElementById("auth-logout-btn");
        if (logoutBtn) logoutBtn.onclick = logout;
        // Fermer modal en cliquant sur le backdrop
        const loginModal = document.getElementById("login-modal");
        if (loginModal) loginModal.onclick = (e) => {
            if (e.target === loginModal) hideLoginModal();
        };

        // Form profil : selection type
        document.querySelectorAll(".profile-type-btn").forEach(btn => {
            btn.onclick = () => {
                document.querySelectorAll(".profile-type-btn").forEach(b => b.classList.remove("selected"));
                btn.classList.add("selected");
                // Niveau requis pour eleve/parent
                const lvl = document.getElementById("profile-level-field");
                if (btn.dataset.value === "eleve" || btn.dataset.value === "parent") {
                    lvl.classList.remove("hidden");
                } else {
                    lvl.classList.add("hidden");
                }
            };
        });
        const profileForm = document.getElementById("profile-form");
        if (profileForm) profileForm.onsubmit = handleProfileSubmit;
    }

    // === INITIALIZATION ===
    function init() {
        applyTheme();
        applyLanguage(state.lang);
        renderHistory();
        attachEventListeners();
        attachAuthListeners();
        renderAuthBlock();
        autoResizeInput();

        // Set initial sidebar state
        if (!state.isSidebarOpen) {
            elements.sidebar.classList.add("collapsed");
            elements.mobileMenuBtn.style.display = "flex";
        } else {
            elements.mobileMenuBtn.style.display = "none";
        }

        updateDirection();

        if (window.lucide) lucide.createIcons();
    }

    // === THEME & UI LOGIC ===
    function applyTheme() {
        const isDark = state.theme === "dark";
        document.documentElement.classList.toggle("dark", isDark);
        document.documentElement.classList.toggle("light", !isDark);
        document.getElementById("theme-icon-light").classList.toggle("hidden", isDark);
        document.getElementById("theme-icon-dark").classList.toggle("hidden", !isDark);
        localStorage.setItem("simen_theme", state.theme);
    }

    function toggleTheme() {
        state.theme = state.theme === "light" ? "dark" : "light";
        applyTheme();
    }

    function updateDirection() {
        document.documentElement.dir = "ltr";
    }

    /** Construit les suggestions d'accueil adaptees au profil utilisateur. */
    function buildQuickSuggestions() {
        const u = state.user;
        if (!u || !u.is_authenticated) return I18N.fr.quickQs;

        const lvl = u.level || "CM2";
        switch (u.profile_type) {
            case "enseignant":
                return [
                    { text: `Fiche pédagogique de mathématiques pour le ${lvl || "CM2"}` },
                    { text: `Évaluation de français ${lvl || "CE2"}` },
                    { text: "Comment importer le personnel sur PLANETE ?" },
                    { text: "Comment justifier une absence dans PLANETE ?" },
                ];
            case "eleve":
                return [
                    { text: `3 exercices de maths pour le ${lvl}` },
                    { text: `Programme de français en ${lvl}` },
                    { text: `Donne-moi des exercices de conjugaison ${lvl}` },
                    { text: lvl === "Terminale" ? "Comment réviser pour le BAC ?"
                          : lvl === "3ème"     ? "Comment me préparer au BFEM ?"
                          :                       "Comment me préparer au CFEE ?" },
                ];
            case "parent":
                return [
                    { text: `Que doit savoir mon enfant en ${lvl} ?` },
                    { text: `3 exercices pour aider mon enfant en ${lvl}` },
                    { text: "Quel est le calendrier scolaire ?" },
                    { text: "Quelles sont les bourses disponibles ?" },
                ];
            default:
                return I18N.fr.quickQs;
        }
    }

    /** Personnalise le titre d'accueil selon le profil. */
    function buildWelcomeText() {
        const u = state.user;
        const def = I18N.fr;
        if (!u || !u.is_authenticated || !u.full_name) {
            return { h2: def.welcomeH2, p: def.welcomeP };
        }
        const firstName = u.full_name.split(" ")[0];
        return {
            h2: `Bonjour ${firstName}, comment puis-je vous aider ?`,
            p: u.profile_type === "enseignant"
                ? `Vos outils pédagogiques et PLANETE en un clic${u.school ? " — " + u.school : ""}.`
                : u.profile_type === "eleve"
                ? `Exercices, programme et révisions pour le ${u.level || "niveau"}.`
                : u.profile_type === "parent"
                ? `Suivez la scolarité de votre enfant en ${u.level || "classe"} et trouvez des conseils.`
                : def.welcomeP,
        };
    }

    function applyLanguage(lang) {
        state.lang = lang;
        localStorage.setItem("simen_lang", lang);

        const content = I18N[lang] || I18N["fr"];
        const welcome = buildWelcomeText();
        const quickQs = buildQuickSuggestions();

        elements.messageInput.placeholder = content.placeholder;
        document.querySelector(".new-chat-btn span").textContent = content.newChat;
        document.getElementById("welcome-section").querySelector("h2").textContent = welcome.h2;
        document.getElementById("welcome-section").querySelector("p").textContent = welcome.p;

        // Update typing text
        if (elements.typingText) {
            elements.typingText.textContent = content.typing;
        }

        // Render Quick Access Cards (adaptes au profil utilisateur)
        elements.quickGrid.innerHTML = "";
        quickQs.forEach(q => {
            const card = document.createElement("div");
            card.className = "quick-card";
            card.innerHTML = `
                <div class="quick-card-body">
                    <span class="quick-card-text">${q.text}</span>
                </div>`;
            card.onclick = () => sendMessage(q.text);
            elements.quickGrid.appendChild(card);
        });

        // Update active pill
        elements.langBtns.forEach(btn => {
            btn.classList.toggle("active", btn.dataset.lang === lang);
        });

        // Update RTL
        updateDirection();
    }

    function toggleSidebar() {
        state.isSidebarOpen = !state.isSidebarOpen;
        elements.sidebar.classList.toggle("collapsed", !state.isSidebarOpen);

        // Mobile overlay
        const overlay = document.getElementById("sidebar-overlay");
        if (overlay) {
            overlay.classList.toggle("active", state.isSidebarOpen && window.innerWidth <= 900);
        }

        // Show/hide the top-left menu button when sidebar is closed/open
        elements.mobileMenuBtn.style.display = state.isSidebarOpen ? "none" : "flex";

        const icon = state.isSidebarOpen ? "chevrons-left" : "chevrons-right";
        elements.sidebarToggle.querySelector("i").setAttribute("data-lucide", icon);
        lucide.createIcons();
    }

    // === MESSAGING LOGIC ===
    async function sendMessage(text = null) {
        let message = text || elements.messageInput.value.trim();
        if ((!message && state.attachedFiles.length === 0) || state.isTyping) return;

        // Garder l'affichage court (ce que l'utilisateur a tapé/cliqué)
        const userDisplayText = message;

        // Si une clarification est en attente, on enrichit le message envoyé à l'API
        // UNIQUEMENT si la saisie ressemble à une réponse courte de clarification
        // (≤ 3 mots, ex: "CM2", "Mathématiques", "Anglais"). Sinon l'utilisateur
        // a abandonné la clarification pour poser une nouvelle question : on efface.
        if (state.pendingClarificationContext && message) {
            const wordCount = message.trim().split(/\s+/).length;
            if (wordCount <= 3) {
                message = state.pendingClarificationContext + " — " + message;
            }
            // Dans tous les cas on efface : la clarification est consommée ou abandonnée
            state.pendingClarificationContext = null;
        }

        // Build display message with file names (affichage seulement, pas pour l'API)
        let displayMsg = userDisplayText;
        if (state.attachedFiles.length > 0) {
            const fileNames = state.attachedFiles.map(f => `📎 ${f.name}`).join("\n");
            displayMsg = userDisplayText ? `${userDisplayText}\n\n${fileNames}` : fileNames;
        }

        // Reset UI
        elements.messageInput.value = "";
        elements.messageInput.style.height = "auto";
        elements.sendBtn.disabled = true;
        state.attachedFiles = [];
        renderFilePreview();
        elements.welcomeSection.style.display = "none";
        // Afficher le bouton Accueil dès qu'une conversation commence
        if (elements.homeBtn) elements.homeBtn.classList.remove("hidden");

        // Add User Message
        appendMessage("user", displayMsg);

        // Show Typing (dots only, no text)
        state.isTyping = true;
        elements.typingIndicator.style.display = "flex";
        scrollToBottom();

        try {
            const response = await fetch(`${CONFIG.API_URL}/chat`, {
                method: "POST",
                headers: authHeaders(),
                body: JSON.stringify({
                    message: message,
                    language: state.lang,
                    session_id: state.currentSessionId
                })
            });

            elements.typingIndicator.style.display = "none";

            if (response.ok) {
                const data = await response.json();
                // Tagger le bubble avec session+source pour le feedback
                window._lastBotResponse = {
                    sessionId: state.currentSessionId,
                    source: data.source,
                    intent: data.intent,
                    question: message,
                    response: data.response,
                    timestamp: data.timestamp,
                };
                await appendBotMessageStreaming(data.response, data.source);
                // Si le serveur renvoie des options de clarification, les afficher
                // On passe `message` (le message complet envoyé à l'API) comme contexte capturé
                if (data.clarification && data.clarification.options && data.clarification.options.length > 0) {
                    showClarificationOptions(data.clarification.options, message);
                }
                // Suggestions de relance contextuelles (apparaissent sous la reponse)
                if (data.suggestions && data.suggestions.length > 0) {
                    showSuggestions(data.suggestions);
                }
                addToHistory(message, data.response);
            } else {
                const errorData = await response.json().catch(() => null);
                const errorMsg = errorData?.detail || content.errorServer;
                appendMessage("bot", errorMsg);
            }
        } catch (err) {
            elements.typingIndicator.style.display = "none";
            appendMessage("bot", content.errorNetwork);
        } finally {
            state.isTyping = false;
            elements.sendBtn.disabled = (elements.messageInput.value.trim().length === 0 && state.attachedFiles.length === 0);
        }
    }

    function appendMessage(role, text) {
        const msgNode = document.createElement("div");
        msgNode.className = `message-node ${role}`;

        const dpticIcon = `<div class="msg-icon dptic-icon-sm"><svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="36" height="36" rx="8" fill="#008751"/><path d="M18 8L6 14l12 6 12-6-12-6z" fill="#FDEF42"/><path d="M10 17v6c0 2.5 3.6 4.5 8 4.5s8-2 8-4.5v-6l-8 4-8-4z" fill="white" opacity="0.9"/><rect x="26" y="14" width="1.5" height="10" rx="0.75" fill="#FDEF42"/><circle cx="26.75" cy="25" r="1.5" fill="#FDEF42"/></svg></div>`;
        const html = `
            ${role === "bot" ? dpticIcon : ""}
            <div class="msg-content">
                <div class="msg-bubble">${role === "bot" ? marked.parse(stripBold(text)) : escapeHTML(text)}</div>
                ${role === "bot" ? `
                <div class="msg-actions">
                    <button class="msg-action-btn copy-btn" title="Copier" onclick="window.copyMessage(this)">
                        <i data-lucide="copy" style="width:14px;height:14px"></i>
                    </button>
                    <button class="msg-action-btn" title="Télécharger en PDF" onclick="window.downloadPDF(this)">
                        <i data-lucide="download" style="width:14px;height:14px"></i>
                    </button>
                </div>` : ""}
            </div>
        `;

        msgNode.innerHTML = html;
        elements.messagesArea.appendChild(msgNode);
        scrollToBottom();
        if (window.lucide) lucide.createIcons();
    }

    /**
     * Mappe la source backend en libelle UI + classe CSS.
     * Retourne null pour les sources qu'on n'affiche pas (salutation, error...).
     */
    function getSourceBadge(source) {
        if (!source) return null;
        const OFFICIAL = ["planete_faq", "faq", "knowledge"];
        const AI = ["llm", "cache"];
        if (OFFICIAL.includes(source)) {
            const label = source === "planete_faq" ? "Source officielle PLANETE"
                        : source === "faq"          ? "FAQ officielle"
                        :                             "Base de connaissances";
            return { label, cls: "badge-official", icon: "shield-check" };
        }
        if (AI.includes(source)) {
            return { label: "Réponse générée par IA", cls: "badge-ai", icon: "sparkles" };
        }
        return null;  // greeting, clarification, error → pas de badge
    }

    async function appendBotMessageStreaming(fullText, source = null) {
        const msgNode = document.createElement("div");
        msgNode.className = "message-node bot";

        const iconDiv = document.createElement("div");
        iconDiv.className = "msg-icon dptic-icon-sm";
        iconDiv.innerHTML = `<svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="36" height="36" rx="8" fill="#008751"/><path d="M18 8L6 14l12 6 12-6-12-6z" fill="#FDEF42"/><path d="M10 17v6c0 2.5 3.6 4.5 8 4.5s8-2 8-4.5v-6l-8 4-8-4z" fill="white" opacity="0.9"/><rect x="26" y="14" width="1.5" height="10" rx="0.75" fill="#FDEF42"/><circle cx="26.75" cy="25" r="1.5" fill="#FDEF42"/></svg>`;

        const container = document.createElement("div");
        container.className = "msg-content";

        const bubble = document.createElement("div");
        bubble.className = "msg-bubble";

        const actions = document.createElement("div");
        actions.className = "msg-actions";
        const badgeInfo = getSourceBadge(source);
        const badgeHTML = badgeInfo
            ? `<span class="source-badge ${badgeInfo.cls}" title="Type de source"><i data-lucide="${badgeInfo.icon}" style="width:12px;height:12px"></i>${badgeInfo.label}</span>`
            : "";
        actions.innerHTML = `
            ${badgeHTML}
            <button class="msg-action-btn feedback-btn feedback-up" title="Réponse utile" onclick="window.sendFeedback(this, 'up')">
                <i data-lucide="thumbs-up" style="width:14px;height:14px"></i>
            </button>
            <button class="msg-action-btn feedback-btn feedback-down" title="Réponse à améliorer" onclick="window.sendFeedback(this, 'down')">
                <i data-lucide="thumbs-down" style="width:14px;height:14px"></i>
            </button>
            <button class="msg-action-btn copy-btn" title="Copier" onclick="window.copyMessage(this)">
                <i data-lucide="copy" style="width:14px;height:14px"></i>
            </button>
            <button class="msg-action-btn" title="Télécharger en PDF" onclick="window.downloadPDF(this)">
                <i data-lucide="download" style="width:14px;height:14px"></i>
            </button>
        `;

        container.appendChild(bubble);
        container.appendChild(actions);
        msgNode.appendChild(iconDiv);
        msgNode.appendChild(container);
        elements.messagesArea.appendChild(msgNode);

        // Streaming effect — on ne re-parse le markdown que tous les
        // PARSE_EVERY mots pour eviter d'appeler marked.parse() 800 fois
        // sur une longue reponse (cause principale du jank ressenti).
        // L'effet visuel reste fluide mais le CPU souffle.
        const words = fullText.split(" ");
        const PARSE_EVERY = 6;
        let displayedText = "";

        for (let i = 0; i < words.length; i++) {
            displayedText += words[i] + " ";
            // Re-parse au pas N, ou sur fin de bloc structure (titres / separateurs)
            const word = words[i];
            const isBlockBoundary = word === "---" || word.startsWith("###") || word.endsWith("\n\n");
            if (i % PARSE_EVERY === 0 || isBlockBoundary || i === words.length - 1) {
                bubble.innerHTML = marked.parse(stripBold(displayedText));
            }
            scrollToBottom();
            await new Promise(r => setTimeout(r, CONFIG.STREAM_SPEED));
        }

        // Final render with full text for correct markdown
        bubble.innerHTML = marked.parse(stripBold(fullText));
        if (window.lucide) lucide.createIcons();
    }

    function scrollToBottom() {
        elements.chatViewport.scrollTo({ top: elements.chatViewport.scrollHeight, behavior: "smooth" });
    }

    // === CLARIFICATION AVEC OPTIONS CLIQUABLES ===
    // apiContext : le message COMPLET déjà envoyé à l'API (avec tout le contexte précédent)
    // Chaque bouton capture apiContext en closure — pas de dépendance à l'état global
    function showClarificationOptions(options, apiContext) {
        // Mettre à jour pendingClarificationContext pour le cas où l'utilisateur tape au lieu de cliquer
        state.pendingClarificationContext = apiContext || null;

        // Trouver le dernier message du bot
        const allBotMessages = elements.messagesArea.querySelectorAll(".message-node.bot");
        const lastBotMessage = allBotMessages[allBotMessages.length - 1];
        if (!lastBotMessage) return;

        const msgContent = lastBotMessage.querySelector(".msg-content");
        if (!msgContent) return;

        // Supprimer d'anciens boutons de clarification s'il y en a
        const oldOptions = msgContent.querySelector(".clarification-options");
        if (oldOptions) oldOptions.remove();

        const optionsDiv = document.createElement("div");
        optionsDiv.className = "clarification-options";

        options.forEach(opt => {
            const btn = document.createElement("button");
            btn.className = "clarification-btn";
            btn.textContent = opt;
            btn.onclick = () => {
                // Désactiver tous les boutons pour éviter double-clic
                optionsDiv.querySelectorAll(".clarification-btn").forEach(b => {
                    b.disabled = true;
                    b.classList.remove("selected");
                });
                btn.classList.add("selected");

                // Construire le message API complet avec le contexte capturé en closure
                const fullApiMessage = apiContext ? `${apiContext} — ${opt}` : opt;

                // Vider le pendingClarificationContext (on gère ici directement)
                state.pendingClarificationContext = null;

                // Envoyer : afficher `opt` dans le chat, mais envoyer `fullApiMessage` à l'API
                sendClarifiedMessage(opt, fullApiMessage);
            };
            optionsDiv.appendChild(btn);
        });

        // Insérer avant les actions (copier/PDF)
        const actions = msgContent.querySelector(".msg-actions");
        if (actions) {
            msgContent.insertBefore(optionsDiv, actions);
        } else {
            msgContent.appendChild(optionsDiv);
        }
        scrollToBottom();
    }

    /**
     * Affiche les suggestions de relance contextuelles sous le dernier
     * message du bot (boutons cliquables pour des questions de relance).
     */
    function showSuggestions(suggestions) {
        if (!suggestions || suggestions.length === 0) return;
        // Note : le sélecteur correct est .message-node.bot (cf. appendMessage / appendBotMessageStreaming)
        const allBotMessages = document.querySelectorAll(".message-node.bot");
        const lastBotMessage = allBotMessages[allBotMessages.length - 1];
        if (!lastBotMessage) return;
        const msgContent = lastBotMessage.querySelector(".msg-content");
        if (!msgContent) return;

        // Eviter doublon
        const old = msgContent.querySelector(".suggestion-chips");
        if (old) old.remove();

        const wrap = document.createElement("div");
        wrap.className = "suggestion-chips";
        const label = document.createElement("div");
        label.className = "suggestion-label";
        label.textContent = "Vous pouvez aussi demander :";
        wrap.appendChild(label);

        const row = document.createElement("div");
        row.className = "suggestion-row";
        suggestions.forEach(text => {
            const chip = document.createElement("button");
            chip.className = "suggestion-chip";
            chip.textContent = text;
            chip.onclick = () => {
                // Disable et envoyer la question
                wrap.querySelectorAll(".suggestion-chip").forEach(b => b.disabled = true);
                sendMessage(text);
            };
            row.appendChild(chip);
        });
        wrap.appendChild(row);

        // Inserer avant les actions (copier/PDF) si elles existent
        const actions = msgContent.querySelector(".msg-actions");
        if (actions) {
            msgContent.insertBefore(wrap, actions);
        } else {
            msgContent.appendChild(wrap);
        }
        scrollToBottom();
    }

    // Envoie un message de clarification : affiche displayText dans le chat, envoie apiMessage à l'API
    async function sendClarifiedMessage(displayText, apiMessage) {
        if (state.isTyping) return;

        elements.welcomeSection.style.display = "none";
        if (elements.homeBtn) elements.homeBtn.classList.remove("hidden");

        // Afficher le choix de l'utilisateur proprement
        appendMessage("user", displayText);

        state.isTyping = true;
        elements.typingIndicator.style.display = "flex";
        scrollToBottom();

        try {
            const response = await fetch(`${CONFIG.API_URL}/chat`, {
                method: "POST",
                headers: authHeaders(),
                body: JSON.stringify({
                    message: apiMessage,
                    language: state.lang,
                    session_id: state.currentSessionId
                })
            });

            elements.typingIndicator.style.display = "none";

            if (response.ok) {
                const data = await response.json();
                window._lastBotResponse = {
                    sessionId: state.currentSessionId,
                    source: data.source,
                    intent: data.intent,
                    question: apiMessage,
                    response: data.response,
                    timestamp: data.timestamp,
                };
                await appendBotMessageStreaming(data.response, data.source);
                // Nouvelle clarification ? Passer apiMessage comme nouveau contexte
                if (data.clarification && data.clarification.options && data.clarification.options.length > 0) {
                    showClarificationOptions(data.clarification.options, apiMessage);
                }
                // Suggestions de relance
                if (data.suggestions && data.suggestions.length > 0) {
                    showSuggestions(data.suggestions);
                }
                addToHistory(displayText, data.response);
            } else {
                appendMessage("bot", I18N.fr.errorServer);
            }
        } catch (err) {
            elements.typingIndicator.style.display = "none";
            appendMessage("bot", I18N.fr.errorNetwork);
        } finally {
            state.isTyping = false;
            elements.sendBtn.disabled = (elements.messageInput.value.trim().length === 0 && state.attachedFiles.length === 0);
        }
    }

    // === FEEDBACK 👍 / 👎 ===
    // Envoie un vote au backend pour piloter l'amelioration des reponses.
    // Persiste aussi en localStorage pour que le vote reste actif au reload.
    window.sendFeedback = async function (btn, vote) {
        const actionsBar = btn.closest(".msg-actions");
        if (!actionsBar) return;
        // Eviter le double-vote sur la meme reponse
        if (actionsBar.dataset.voted) return;
        actionsBar.dataset.voted = vote;

        // Marquer visuellement le bouton choisi + desactiver les deux
        actionsBar.querySelectorAll(".feedback-btn").forEach(b => {
            b.disabled = true;
            b.classList.remove("active");
        });
        btn.classList.add("active");

        // Recuperer le contexte de la derniere reponse bot
        const ctx = window._lastBotResponse || {};
        const bubble = btn.closest(".msg-content")?.querySelector(".msg-bubble");
        const responseText = bubble ? (bubble.innerText || bubble.textContent) : ctx.response;

        const payload = {
            session_id: ctx.sessionId || state.currentSessionId,
            vote,
            intent: ctx.intent || null,
            source: ctx.source || null,
            question: ctx.question || null,
            answer: (responseText || "").substring(0, 1000),
        };

        // Persister en local (pour suivi cote utilisateur)
        try {
            const localKey = "edubot_feedback";
            const stored = JSON.parse(localStorage.getItem(localKey) || "[]");
            stored.push({ ...payload, timestamp: new Date().toISOString() });
            // Garder max 100 votes en local
            localStorage.setItem(localKey, JSON.stringify(stored.slice(-100)));
        } catch (_) { /* localStorage plein ou indisponible */ }

        // Envoyer au backend (best-effort, non bloquant)
        try {
            await fetch(`${CONFIG.API_URL}/feedback`, {
                method: "POST",
                headers: authHeaders(),
                body: JSON.stringify(payload),
            });
        } catch (_) { /* endpoint indisponible : le vote reste en local */ }

        // Petit feedback visuel temporaire
        const original = btn.innerHTML;
        btn.innerHTML = '<i data-lucide="check" style="width:14px;height:14px"></i>';
        if (window.lucide) lucide.createIcons();
        setTimeout(() => {
            btn.innerHTML = original;
            if (window.lucide) lucide.createIcons();
        }, 1500);
    };

    // === COPY TO CLIPBOARD ===
    window.copyMessage = function (btn) {
        const bubble = btn.closest(".msg-content").querySelector(".msg-bubble");
        const text = bubble.innerText || bubble.textContent;
        navigator.clipboard.writeText(text).then(() => {
            btn.innerHTML = '<i data-lucide="check" style="width:14px;height:14px"></i>';
            if (window.lucide) lucide.createIcons();
            setTimeout(() => {
                btn.innerHTML = '<i data-lucide="copy" style="width:14px;height:14px"></i>';
                if (window.lucide) lucide.createIcons();
            }, 2000);
        });
    };

    // === TÉLÉCHARGEMENT PDF (jsPDF — vrai fichier .pdf) ===
    window.downloadPDF = function (btn) {
        const bubble = btn.closest(".msg-content").querySelector(".msg-bubble");
        const today = new Date().toLocaleDateString("fr-SN", { weekday: "long", year: "numeric", month: "long", day: "numeric" });

        // Afficher un indicateur de chargement sur le bouton
        const originalHTML = btn.innerHTML;
        btn.innerHTML = '<i data-lucide="loader-2" style="width:14px;height:14px;animation:spin 1s linear infinite"></i>';
        if (window.lucide) lucide.createIcons();
        btn.disabled = true;

        // Créer un conteneur temporaire bien formaté pour le rendu HTML → PDF
        const tempDiv = document.createElement("div");
        tempDiv.style.cssText = `
            position: fixed;
            top: -9999px;
            left: -9999px;
            width: 760px;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 13px;
            color: #1a1a2e;
            background: #ffffff;
            padding: 40px 50px;
            line-height: 1.8;
            z-index: -1;
        `;

        tempDiv.innerHTML = `
            <div style="display:flex;align-items:center;gap:16px;padding-bottom:14px;border-bottom:3px solid #008751;margin-bottom:24px;">
                <div style="display:flex;width:54px;height:36px;border-radius:4px;overflow:hidden;flex-shrink:0;">
                    <div style="flex:1;background:#008751;"></div>
                    <div style="flex:1;background:#FDEF42;display:flex;align-items:center;justify-content:center;color:#008751;font-size:14px;">★</div>
                    <div style="flex:1;background:#E31B23;"></div>
                </div>
                <div>
                    <div style="font-size:14px;font-weight:700;color:#008751;">EduBot — Ministère de l'Éducation Nationale</div>
                    <div style="font-size:11px;color:#666;margin-top:3px;">République du Sénégal &nbsp;·&nbsp; ${today}</div>
                </div>
            </div>
            <div class="pdf-body" style="line-height:1.8;">${bubble.innerHTML}</div>
            <div style="margin-top:36px;padding-top:12px;border-top:1px solid #eee;font-size:10px;color:#aaa;text-align:center;">
                Document généré par EduBot &nbsp;•&nbsp; educonnect-w7tr.onrender.com &nbsp;•&nbsp; Ministère de l'Éducation Nationale du Sénégal
            </div>
        `;

        // Styles internes pour les éléments markdown
        const styleTag = document.createElement("style");
        styleTag.textContent = `
            .pdf-body h1,.pdf-body h2,.pdf-body h3{color:#008751;margin:18px 0 8px;font-weight:700;}
            .pdf-body h1{font-size:16px;}.pdf-body h2{font-size:15px;}.pdf-body h3{font-size:14px;}
            .pdf-body hr{border:none;border-top:1px solid #ddd;margin:14px 0;}
            .pdf-body p{margin:8px 0;}
            .pdf-body ul,.pdf-body ol{margin:8px 0 8px 22px;}
            .pdf-body li{margin:4px 0;}
            .pdf-body strong{font-weight:700;}
            .pdf-body em{font-style:italic;}
            .pdf-body table{width:100%;border-collapse:collapse;margin:12px 0;font-size:12px;}
            .pdf-body th{background:#008751;color:#fff;padding:6px 8px;text-align:left;}
            .pdf-body td{border:1px solid #ddd;padding:6px 8px;}
            .pdf-body tr:nth-child(even) td{background:#f7f7f7;}
            .pdf-body code{background:#f4f4f5;padding:2px 6px;border-radius:4px;font-size:12px;}
            .pdf-body blockquote{border-left:3px solid #008751;padding-left:12px;color:#555;font-style:italic;}
        `;
        tempDiv.prepend(styleTag);
        document.body.appendChild(tempDiv);

        // Utiliser html2canvas + jsPDF pour générer un vrai PDF
        const generatePDF = () => {
            const { jsPDF } = window.jspdf;

            html2canvas(tempDiv, {
                scale: 2,
                useCORS: true,
                backgroundColor: "#ffffff",
                logging: false,
                width: 760,
                windowWidth: 760
            }).then(canvas => {
                const imgData = canvas.toDataURL("image/jpeg", 0.92);
                const doc = new jsPDF("p", "mm", "a4");

                const pageWidth = doc.internal.pageSize.getWidth();   // 210mm
                const pageHeight = doc.internal.pageSize.getHeight(); // 297mm
                const margin = 10;
                const contentWidth = pageWidth - margin * 2;
                const imgWidth = canvas.width;
                const imgHeight = canvas.height;
                const ratio = contentWidth / imgWidth;
                const contentHeightMm = imgHeight * ratio;

                let position = margin;
                let heightLeft = contentHeightMm;

                // Première page
                doc.addImage(imgData, "JPEG", margin, position, contentWidth, contentHeightMm);
                heightLeft -= (pageHeight - margin * 2);

                // Pages supplémentaires si le contenu est long
                while (heightLeft > 0) {
                    position = -(pageHeight - margin * 2) + (contentHeightMm - heightLeft) * -1;
                    doc.addPage();
                    doc.addImage(imgData, "JPEG", margin, margin + position, contentWidth, contentHeightMm);
                    heightLeft -= (pageHeight - margin * 2);
                }

                // Générer un nom de fichier avec la date
                const dateStr = new Date().toISOString().slice(0, 10);
                doc.save(`EduBot-${dateStr}.pdf`);

                // Nettoyer
                document.body.removeChild(tempDiv);
                btn.innerHTML = originalHTML;
                btn.disabled = false;
                if (window.lucide) lucide.createIcons();
            }).catch(err => {
                console.error("Erreur génération PDF:", err);
                document.body.removeChild(tempDiv);
                btn.innerHTML = originalHTML;
                btn.disabled = false;
                if (window.lucide) lucide.createIcons();
                alert("Erreur lors de la génération du PDF. Veuillez réessayer.");
            });
        };

        // Laisser le temps au DOM de se mettre à jour avant le rendu
        setTimeout(generatePDF, 300);
    };

    // === UTILS ===

    /**
     * Supprime le gras et italique residuels (Markdown + HTML) avant le rendu.
     * Defense en couche frontend : le backend a deja nettoye en profondeur,
     * et marked.js override neutralise strong/em au rendu. Une seule passe
     * suffit ici — c'est appele a chaque mot pendant le streaming.
     */
    function stripBold(text) {
        if (!text) return text;
        // Gras+italique ***...*** d'abord (le plus large)
        text = text.replace(/\*\*\*([^*]+?)\*\*\*/gs, '$1');
        // Gras **...** (multilignes)
        text = text.replace(/\*\*\s*([\s\S]+?)\s*\*\*/g, '$1');
        // Gras __...__
        text = text.replace(/__\s*([\s\S]+?)\s*__/g, '$1');
        // ** orphelins
        text = text.replace(/\*\*/g, '');
        // Italique *texte* (preserver les * de debut de ligne pour les listes)
        text = text.replace(/(^|[^\n*])\*([^\s*][^*\n]*?[^\s*])\*/g, '$1$2');
        // HTML <strong>/<b>/<em>/<i>
        text = text.replace(/<\/?(strong|b|em|i)\s*[^>]*>/gi, '');
        return text;
    }

    function escapeHTML(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    function autoResizeInput() {
        elements.messageInput.addEventListener("input", function () {
            this.style.height = "auto";
            this.style.height = Math.min(this.scrollHeight, 200) + "px";
            elements.sendBtn.disabled = (this.value.trim().length === 0 && state.attachedFiles.length === 0);
        });
    }

    function addToHistory(userMsg, botMsg) {
        const session = {
            id: state.currentSessionId,
            title: userMsg.substring(0, 35) + (userMsg.length > 35 ? "..." : ""),
            timestamp: new Date().toISOString()
        };

        const idx = state.history.findIndex(h => h.id === session.id);
        if (idx > -1) {
            state.history[idx].timestamp = session.timestamp;
        } else {
            state.history.unshift(session);
        }

        if (state.history.length > CONFIG.MAX_HISTORY) state.history.pop();

        // Sauvegarder les messages de cette session dans localStorage
        const sid = state.currentSessionId;
        if (!state.sessionMessages[sid]) state.sessionMessages[sid] = [];
        state.sessionMessages[sid].push({ role: "user", content: userMsg });
        state.sessionMessages[sid].push({ role: "bot", content: botMsg });
        // Garder max 100 messages par session (50 échanges)
        if (state.sessionMessages[sid].length > 100) {
            state.sessionMessages[sid] = state.sessionMessages[sid].slice(-100);
        }
        // Garder seulement les 30 dernières sessions pour ne pas saturer localStorage
        const activeIds = state.history.map(h => h.id);
        Object.keys(state.sessionMessages).forEach(id => {
            if (!activeIds.includes(id)) delete state.sessionMessages[id];
        });

        localStorage.setItem("simen_history", JSON.stringify(state.history));
        localStorage.setItem("simen_session_messages", JSON.stringify(state.sessionMessages));
        renderHistory();
    }

    function renderHistory() {
        const content = I18N[state.lang] || I18N["fr"];

        if (state.history.length === 0) {
            elements.historyList.innerHTML = `<div class="history-empty">${content.historyEmpty}</div>`;
            return;
        }

        elements.historyList.innerHTML = state.history.map(h => `
            <div class="history-item ${h.id === state.currentSessionId ? "active" : ""}" data-session="${h.id}">
                <i data-lucide="message-square"></i>
                <span>${h.title}</span>
                <button class="history-delete-btn" data-delete="${h.id}" title="Supprimer">
                    <i data-lucide="trash-2"></i>
                </button>
            </div>
        `).join("");

        // Attach click handlers for loading sessions
        elements.historyList.querySelectorAll(".history-item").forEach(item => {
            item.onclick = (e) => {
                // Don't load session if delete button was clicked
                if (e.target.closest(".history-delete-btn")) return;
                const id = item.getAttribute("data-session");
                loadSession(id);
            };
        });

        // Attach delete handlers
        elements.historyList.querySelectorAll(".history-delete-btn").forEach(btn => {
            btn.onclick = (e) => {
                e.stopPropagation();
                const id = btn.getAttribute("data-delete");
                showDeleteConfirm(id);
            };
        });

        if (window.lucide) lucide.createIcons();
    }

    // === RETOUR À L'ACCUEIL ===
    function goHome() {
        state.currentSessionId = crypto.randomUUID();
        elements.messagesArea.innerHTML = "";
        elements.welcomeSection.style.display = "";
        state.attachedFiles = [];
        renderFilePreview();
        renderHistory();
        // Cacher le bouton Accueil (on est de retour à l'accueil)
        if (elements.homeBtn) elements.homeBtn.classList.add("hidden");
        // Fermer la sidebar sur mobile
        if (window.innerWidth <= 900 && state.isSidebarOpen) {
            toggleSidebar();
        }
        // Remettre le focus sur le champ de texte
        elements.messageInput.focus();
    }

    // === DELETE CONVERSATION ===
    function showDeleteConfirm(sessionId) {
        state.deleteTargetId = sessionId;
        if (elements.deleteModal) {
            elements.deleteModal.classList.remove("hidden");
        }
    }

    function deleteConversation(sessionId) {
        state.history = state.history.filter(h => h.id !== sessionId);
        // Supprimer aussi les messages locaux de cette session
        delete state.sessionMessages[sessionId];
        localStorage.setItem("simen_history", JSON.stringify(state.history));
        localStorage.setItem("simen_session_messages", JSON.stringify(state.sessionMessages));

        // If we deleted the current session, start a new one
        if (sessionId === state.currentSessionId) {
            state.currentSessionId = crypto.randomUUID();
            elements.messagesArea.innerHTML = "";
            elements.welcomeSection.style.display = "";
            if (elements.homeBtn) elements.homeBtn.classList.add("hidden");
        }

        renderHistory();
    }

    // === FILE UPLOAD ===
    function getFileIcon(type) {
        if (type.startsWith("image/")) return "🖼️";
        if (type === "application/pdf") return "📄";
        if (type.includes("word")) return "📝";
        if (type.includes("excel") || type.includes("spreadsheet")) return "📊";
        return "📎";
    }

    function handleFileSelect(files) {
        for (const file of files) {
            if (file.size > CONFIG.MAX_FILE_SIZE) {
                alert(`Le fichier "${file.name}" dépasse la taille maximale de 10 Mo.`);
                continue;
            }
            state.attachedFiles.push(file);
        }
        renderFilePreview();
        elements.sendBtn.disabled = (elements.messageInput.value.trim().length === 0 && state.attachedFiles.length === 0);
    }

    function removeFile(index) {
        state.attachedFiles.splice(index, 1);
        renderFilePreview();
        elements.sendBtn.disabled = (elements.messageInput.value.trim().length === 0 && state.attachedFiles.length === 0);
    }

    function renderFilePreview() {
        if (!elements.filePreview) return;

        if (state.attachedFiles.length === 0) {
            elements.filePreview.classList.add("hidden");
            elements.filePreview.innerHTML = "";
            return;
        }

        elements.filePreview.classList.remove("hidden");
        elements.filePreview.innerHTML = state.attachedFiles.map((file, i) => {
            const icon = getFileIcon(file.type);
            const isImage = file.type.startsWith("image/");
            const imgTag = isImage ? `<img class="file-preview-img" src="${URL.createObjectURL(file)}" alt="${file.name}">` : "";
            return `
                <div class="file-preview-item">
                    ${imgTag || `<span class="file-icon">${icon}</span>`}
                    <span class="file-name">${file.name}</span>
                    <button class="file-remove" onclick="window.removeAttachedFile(${i})" title="Retirer">&times;</button>
                </div>
            `;
        }).join("");
    }

    window.removeAttachedFile = function(index) {
        removeFile(index);
    };

    function loadSession(id) {
        state.currentSessionId = id;
        elements.messagesArea.innerHTML = "";
        elements.welcomeSection.style.display = "none";
        if (elements.homeBtn) elements.homeBtn.classList.remove("hidden");

        // 1. Charger depuis localStorage (priorité — fonctionne même après redémarrage serveur)
        const localMsgs = state.sessionMessages[id];
        if (localMsgs && localMsgs.length > 0) {
            localMsgs.forEach(msg => appendMessage(msg.role, msg.content));
            renderHistory();
            if (window.innerWidth <= 900 && state.isSidebarOpen) toggleSidebar();
            scrollToBottom();
            return;
        }

        // 2. Fallback : essayer le serveur (si les messages ne sont pas en local)
        fetch(`${CONFIG.API_URL}/chat/history/${id}?limit=50`)
            .then(r => r.ok ? r.json() : null)
            .then(data => {
                if (data && data.messages && data.messages.length > 0) {
                    // Sauvegarder en local pour les prochaines fois
                    state.sessionMessages[id] = data.messages.map(m => ({
                        role: m.role === "assistant" ? "bot" : "user",
                        content: m.content
                    }));
                    localStorage.setItem("simen_session_messages", JSON.stringify(state.sessionMessages));
                    data.messages.forEach(msg => {
                        appendMessage(msg.role === "assistant" ? "bot" : "user", msg.content);
                    });
                } else {
                    // Aucun message trouvé nulle part
                    appendMessage("bot", "Cette conversation n'est plus disponible. Commencez un nouveau chat !");
                }
            })
            .catch(() => {
                appendMessage("bot", "Impossible de charger cette conversation. Vérifiez votre connexion.");
            });

        renderHistory();

        // Close sidebar on mobile after selection
        if (window.innerWidth <= 900 && state.isSidebarOpen) {
            toggleSidebar();
        }
    }

    function attachEventListeners() {
        elements.sidebarToggle.onclick = toggleSidebar;
        elements.mobileMenuBtn.onclick = toggleSidebar;
        elements.themeToggle.onclick = toggleTheme;

        elements.sendBtn.onclick = () => sendMessage();

        // Enter to send (all devices), Shift+Enter for new line
        elements.messageInput.onkeydown = (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        };

        elements.langBtns.forEach(btn => {
            btn.onclick = () => applyLanguage(btn.dataset.lang);
        });

        elements.newChatBtn.onclick = () => goHome();

        // Bouton Accueil (retour écran d'accueil depuis une conversation)
        if (elements.homeBtn) {
            elements.homeBtn.onclick = () => goHome();
        }

        // File upload
        if (elements.attachBtn && elements.fileInput) {
            elements.attachBtn.onclick = () => elements.fileInput.click();
            elements.fileInput.onchange = (e) => {
                if (e.target.files.length > 0) {
                    handleFileSelect(e.target.files);
                    e.target.value = ""; // Reset so same file can be picked again
                }
            };
        }

        // Drag & Drop on input area
        const inputWrapper = document.querySelector(".input-wrapper");
        if (inputWrapper) {
            inputWrapper.addEventListener("dragover", (e) => {
                e.preventDefault();
                inputWrapper.style.borderColor = "var(--color-simen)";
            });
            inputWrapper.addEventListener("dragleave", () => {
                inputWrapper.style.borderColor = "";
            });
            inputWrapper.addEventListener("drop", (e) => {
                e.preventDefault();
                inputWrapper.style.borderColor = "";
                if (e.dataTransfer.files.length > 0) {
                    handleFileSelect(e.dataTransfer.files);
                }
            });
        }

        // Delete confirmation modal
        if (elements.deleteModal) {
            elements.deleteCancelBtn.onclick = () => {
                state.deleteTargetId = null;
                elements.deleteModal.classList.add("hidden");
            };
            elements.deleteConfirmBtn.onclick = () => {
                if (state.deleteTargetId) {
                    deleteConversation(state.deleteTargetId);
                    state.deleteTargetId = null;
                }
                elements.deleteModal.classList.add("hidden");
            };
            elements.deleteModal.onclick = (e) => {
                if (e.target === elements.deleteModal) {
                    state.deleteTargetId = null;
                    elements.deleteModal.classList.add("hidden");
                }
            };
        }

        // Settings modal
        if (elements.settingsBtn && elements.settingsModal) {
            elements.settingsBtn.onclick = () => {
                elements.settingsModal.classList.remove("hidden");
            };
            elements.settingsModal.querySelector(".close-modal-btn").onclick = () => {
                elements.settingsModal.classList.add("hidden");
            };
            elements.settingsModal.onclick = (e) => {
                if (e.target === elements.settingsModal) {
                    elements.settingsModal.classList.add("hidden");
                }
            };
        }

        // Responsive sidebar
        window.addEventListener("resize", () => {
            if (window.innerWidth > 900) {
                state.isSidebarOpen = true;
                elements.sidebar.classList.remove("collapsed");
                elements.mobileMenuBtn.style.display = "none";
            }
        });
    }

    // Run
    init();

})();
