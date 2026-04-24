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
        currentSessionId: crypto.randomUUID(),
        isTyping: false,
        messages: {},
        attachedFiles: [],
        deleteTargetId: null,
        // Contexte de clarification : message original en attente d'une précision
        pendingClarificationContext: null
    };

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
                { text: "Donne-moi 3 exercices de maths niveau CM2" },
                { text: "Exercices de remédiation en français pour la 6ème" },
                { text: "C'est quoi PLANETE 3.0 ?" },
                { text: "Comment avancer dans ma carrière d'enseignant ?" }
            ]
        }
    };

    // === INITIALIZATION ===
    function init() {
        applyTheme();
        applyLanguage(state.lang);
        renderHistory();
        attachEventListeners();
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

    function applyLanguage(lang) {
        state.lang = lang;
        localStorage.setItem("simen_lang", lang);

        const content = I18N[lang] || I18N["fr"];

        elements.messageInput.placeholder = content.placeholder;
        document.querySelector(".new-chat-btn span").textContent = content.newChat;
        document.getElementById("welcome-section").querySelector("h2").textContent = content.welcomeH2;
        document.getElementById("welcome-section").querySelector("p").textContent = content.welcomeP;

        // Update typing text
        if (elements.typingText) {
            elements.typingText.textContent = content.typing;
        }

        // Render Quick Access Cards
        elements.quickGrid.innerHTML = "";
        content.quickQs.forEach(q => {
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
        const message = text || elements.messageInput.value.trim();
        if ((!message && state.attachedFiles.length === 0) || state.isTyping) return;

        // Si une clarification est en attente, enrichir le message avec le contexte
        if (state.pendingClarificationContext && message) {
            message = state.pendingClarificationContext + " — " + message;
            state.pendingClarificationContext = null;
        }

        // Build display message with file names
        let displayMsg = message;
        if (state.attachedFiles.length > 0) {
            const fileNames = state.attachedFiles.map(f => `📎 ${f.name}`).join("\n");
            displayMsg = message ? `${message}\n\n${fileNames}` : fileNames;
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
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: message,
                    language: state.lang,
                    session_id: state.currentSessionId
                })
            });

            elements.typingIndicator.style.display = "none";

            if (response.ok) {
                const data = await response.json();
                await appendBotMessageStreaming(data.response);
                // Si le serveur renvoie des options de clarification, les afficher
                if (data.clarification && data.clarification.options && data.clarification.options.length > 0) {
                    // Stocker le message orignal (sans le contexte déjà ajouté)
                    state.pendingClarificationContext = message;
                    showClarificationOptions(data.clarification.options);
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
                <div class="msg-bubble">${role === "bot" ? marked.parse(text) : escapeHTML(text)}</div>
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

    async function appendBotMessageStreaming(fullText) {
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
        actions.innerHTML = `
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

        // Streaming effect
        const words = fullText.split(" ");
        let displayedText = "";

        for (let i = 0; i < words.length; i++) {
            displayedText += words[i] + " ";
            bubble.innerHTML = marked.parse(displayedText);
            scrollToBottom();
            await new Promise(r => setTimeout(r, CONFIG.STREAM_SPEED));
        }

        // Final render with full text for correct markdown
        bubble.innerHTML = marked.parse(fullText);
        if (window.lucide) lucide.createIcons();
    }

    function scrollToBottom() {
        elements.chatViewport.scrollTo({ top: elements.chatViewport.scrollHeight, behavior: "smooth" });
    }

    // === CLARIFICATION AVEC OPTIONS CLIQUABLES ===
    function showClarificationOptions(options) {
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
                // Désactiver tous les boutons après clic
                optionsDiv.querySelectorAll(".clarification-btn").forEach(b => {
                    b.disabled = true;
                    b.classList.remove("selected");
                });
                btn.classList.add("selected");
                // Envoyer directement le choix (le contexte est dans state.pendingClarificationContext)
                sendMessage(opt);
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

        localStorage.setItem("simen_history", JSON.stringify(state.history));
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
        localStorage.setItem("simen_history", JSON.stringify(state.history));

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

        // Try to load from server history
        fetch(`${CONFIG.API_URL}/chat/history/${id}?limit=50`)
            .then(r => r.ok ? r.json() : null)
            .then(data => {
                if (data && data.messages && data.messages.length > 0) {
                    data.messages.forEach(msg => {
                        appendMessage(msg.role === "assistant" ? "bot" : "user", msg.content);
                    });
                } else {
                    elements.welcomeSection.style.display = "block";
                }
            })
            .catch(() => {
                elements.welcomeSection.style.display = "block";
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
