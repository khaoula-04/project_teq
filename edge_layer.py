import time


class EdgeLayer:
    """
    Simule la couche Edge : cache local, mode dégradé,
    mesure de latence, routage des requêtes.
    """

    def __init__(self):
        self.cache = {}
        self.cloud_available = True
        self.latency_threshold_ms = 200

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

        # 2. Traitement local si cloud indisponible (mode dégradé)
        if not self.cloud_available:
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

    def _degraded_mode_response(self, query: str) -> str:
        """Réponses prédéfinies pour le mode hors-ligne."""
        fallback = {
            "planning": "Mode hors-ligne : consultez votre emploi du temps ENT.",
            "résumé": "Mode hors-ligne : résumé non disponible sans connexion.",
            "résume": "Mode hors-ligne : résumé non disponible sans connexion.",
            "cours": "Mode hors-ligne : accédez à vos cours téléchargés localement.",
            "default": "Je fonctionne en mode dégradé. Reconnectez-vous pour une réponse complète."
        }
        for key in fallback:
            if key in query.lower():
                return fallback[key]
        return fallback["default"]

    def simulate_cloud_outage(self):
        """Simule une coupure de connexion cloud."""
        self.cloud_available = False

    def restore_cloud(self):
        """Restaure la connexion cloud."""
        self.cloud_available = True

    def get_cache_size(self) -> int:
        return len(self.cache)
