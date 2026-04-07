import time
import httpx


OLLAMA_MODEL   = "llama3.2"
OLLAMA_URL     = "http://localhost:11434/api/chat"
OLLAMA_TIMEOUT = 60.0   # seconds — local inference can take a moment

SYSTEM_PROMPT = (
    "Tu es Farfalla, un assistant pédagogique intelligent pour les étudiants de l'ENSA Béni Mellal. "
    "Tu fonctionnes en mode hors-ligne sur l'appareil local (Edge Computing). "
    "Réponds toujours en français, de façon claire, concise et bienveillante. "
    "Si la question porte sur un cours, explique avec des exemples simples. "
    "Si l'étudiant exprime du stress ou de l'anxiété, encourage-le et donne des conseils pratiques."
)


class EdgeLayer:
    """
    Couche Edge : cache local, Ollama hors-ligne, mode dégradé,
    mesure de latence, routage des requêtes.
    """

    def __init__(self):
        self.cache = {}
        self.cloud_available = True
        self.latency_threshold_ms = 200
        self._ollama_available: bool | None = None  # None = not yet checked

    def process(self, query: str, student_id: str) -> dict:
        start = time.time()

        # 1. Vérification du cache local
        if query in self.cache:
            latency = (time.time() - start) * 1000
            return {
                "source": "edge_cache",
                "response": self.cache[query],
                "latency_ms": round(latency, 2)
            }

        # 2. Traitement local si cloud indisponible
        if not self.cloud_available:
            # 2a. Essayer Ollama (LLM local)
            ollama_resp = self._call_ollama(query)
            latency = (time.time() - start) * 1000
            if ollama_resp:
                return {
                    "source": "edge_ollama",
                    "response": ollama_resp,
                    "latency_ms": round(latency, 2)
                }
            # 2b. Fallback : règles par mots-clés
            response = self._degraded_mode_response(query)
            latency = (time.time() - start) * 1000
            return {
                "source": "edge_local_degraded",
                "response": response,
                "latency_ms": round(latency, 2)
            }

        # 3. Sinon : remontée vers le cloud
        return {"source": "cloud", "query": query}

    def cache_response(self, query: str, response: str):
        self.cache[query] = response

    # ── Ollama integration ────────────────────────────────────

    def _call_ollama(self, query: str) -> str | None:
        """Call local Ollama LLM. Returns response text or None if unavailable."""
        try:
            resp = httpx.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": query},
                    ],
                    "stream": False,
                },
                timeout=OLLAMA_TIMEOUT,
            )
            resp.raise_for_status()
            content = resp.json().get("message", {}).get("content", "")
            if content:
                self._ollama_available = True
                return content.strip()
        except Exception:
            self._ollama_available = False
        return None

    def check_ollama(self) -> bool:
        """Quick ping to see if Ollama daemon is running."""
        try:
            r = httpx.get("http://localhost:11434/api/tags", timeout=3.0)
            self._ollama_available = r.status_code == 200
        except Exception:
            self._ollama_available = False
        return bool(self._ollama_available)

    def _degraded_mode_response(self, query: str) -> str:
        """Réponses prédéfinies pour le mode hors-ligne."""
        q = query.lower()

        rules = [
            (["bonjour", "salut", "hello", "bonsoir", "salam"],
             "Bonjour ! Je suis Farfalla en mode hors-ligne. "
             "Je peux répondre aux questions courantes sur vos cours. "
             "Reconnectez-vous pour des réponses complètes générées par l'IA."),

            (["planning", "emploi du temps", "schedule", "révision", "semaine"],
             "Mode hors-ligne — Planning conseillé :\n"
             "• Lundi : Mathématiques (2h) + Révision (1h)\n"
             "• Mardi : TP Programmation (3h)\n"
             "• Mercredi : Cours TEQ (2h)\n"
             "• Jeudi : Mini-projet (3h)\n"
             "• Vendredi : Révisions générales\n"
             "Reconnectez-vous pour un planning personnalisé."),

            (["résumé", "résume", "résumer", "summary"],
             "Mode hors-ligne — Je ne peux pas générer de résumé sans connexion cloud. "
             "Consultez vos cours téléchargés ou vos notes locales. "
             "Reconnectez-vous pour un résumé généré par l'IA."),

            (["edge computing", "edge"],
             "Edge Computing (hors-ligne) : traitement des données au plus près de leur source, "
             "réduisant la latence et la dépendance au cloud. "
             "Reconnectez-vous pour une explication complète."),

            (["llm", "modèle de langage", "gpt", "intelligence artificielle", "ia"],
             "LLM (hors-ligne) : grands modèles de langage entraînés sur des corpus massifs, "
             "capables de générer du texte, répondre à des questions et résumer des documents. "
             "Reconnectez-vous pour plus de détails."),

            (["stress", "anxieux", "peur", "difficile", "perdu", "comprends pas"],
             "Je vois que vous traversez un moment difficile. "
             "Prenez une pause, respirez. Même hors-ligne, je suis là pour vous. "
             "Reconnectez-vous dès que possible pour une aide complète."),

            (["cours", "chapitre", "leçon", "module", "matière"],
             "Mode hors-ligne — Consultez vos cours téléchargés localement. "
             "Reconnectez-vous pour des explications détaillées et des résumés générés par l'IA."),

            (["aide", "help", "sos", "comment", "quoi", "qu'est"],
             "Mode hors-ligne — Je peux vous aider avec : planning, définitions de base (Edge, LLM, IA). "
             "Pour des réponses complètes, reconnectez-vous au cloud."),
        ]

        for keywords, response in rules:
            if any(k in q for k in keywords):
                return response

        return (
            "Je suis Farfalla en mode hors-ligne. 📴\n"
            "Je peux répondre à des questions sur : planning, Edge Computing, LLM, IA.\n"
            "Cliquez sur 'Rétablir cloud' pour des réponses complètes."
        )

    def simulate_cloud_outage(self):
        """Simule une coupure de connexion cloud."""
        self.cloud_available = False

    def restore_cloud(self):
        """Restaure la connexion cloud."""
        self.cloud_available = True

    def get_cache_size(self) -> int:
        return len(self.cache)
