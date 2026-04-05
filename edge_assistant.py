"""
Assistant IA Génératif Edge — Campus Intelligent ENSA Beni Mellal
Module : Technologies Émergentes & Quantum | Pr. TOUIL

Point d'entrée principal. Lance `python edge_assistant.py` pour démarrer.

Commandes spéciales dans le chat :
  offline  → simule une coupure cloud (mode dégradé)
  online   → restaure la connexion cloud
  stats    → affiche les statistiques de la session
  history  → affiche les dernières interactions
  quit     → quitte le programme
"""

import time
import os
from edge_layer import EdgeLayer
from stress_detector import StressDetector
from local_db import LocalDatabase


class EdgeAssistant:

    SYSTEM_PROMPT = (
        "Tu es Farfalla, un assistant pédagogique IA pour étudiants de l'ENSA Béni Mellal. "
        "Tu peux : résumer des cours, répondre à des questions, proposer un planning. "
        "Réponds toujours en français, de manière claire et concise. "
        "Si l'étudiant semble stressé, sois particulièrement bienveillant et rassurant."
    )

    def __init__(self, student_id: str = "student_001"):
        self.edge = EdgeLayer()
        self.stress_detector = StressDetector()
        self.db = LocalDatabase()
        self.student_id = student_id

    def chat(self, user_input: str) -> str:
        start = time.time()

        # Étape 1 : Détection du stress (100% local, jamais envoyé au cloud)
        stress_analysis = self.stress_detector.analyze(user_input)

        # Étape 2 : Traitement via couche Edge (cache ou mode dégradé)
        edge_result = self.edge.process(user_input, self.student_id)

        if edge_result["source"] in ("edge_cache", "edge_local_degraded"):
            response = edge_result["response"]
            source = edge_result["source"]
            latency = edge_result["latency_ms"]
        else:
            # Étape 3 : Appel cloud LLM (query uniquement, sans données personnelles)
            response, latency = self._call_cloud_llm(user_input)
            source = "cloud"
            # Mise en cache Edge pour les prochaines requêtes identiques
            self.edge.cache_response(user_input, response)

        # Étape 4 : Message de support si stress détecté
        if stress_analysis["message"]:
            response = f"[Support] {stress_analysis['message']}\n\n{response}"

        # Étape 5 : Journalisation locale uniquement (données jamais en cloud)
        self.db.log_interaction(
            self.student_id, user_input, response,
            stress_analysis["level"], source, latency
        )

        total_latency = (time.time() - start) * 1000
        print(f"  [Latence: {total_latency:.1f}ms | Source: {source} | "
              f"Stress: {stress_analysis['level']} | Cache: {self.edge.get_cache_size()} entrées]")

        return response

    def _call_cloud_llm(self, query: str) -> tuple[str, float]:
        """
        Appel à l'API LLM cloud.

        Pour activer une vraie API, décommentez le bloc correspondant
        et définissez votre clé API dans la variable d'environnement.

        Option 1 — API Anthropic (Claude) :
            export ANTHROPIC_API_KEY="sk-ant-..."
            pip install anthropic

        Option 2 — API OpenAI :
            export OPENAI_API_KEY="sk-..."
            pip install openai
        """
        start = time.time()

        openai_key = os.environ.get("OPENAI_API_KEY")
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

        if openai_key:
            # --- OpenAI ---
            try:
                import openai
                client = openai.OpenAI(api_key=openai_key)
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    max_tokens=500,
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": query}
                    ]
                )
                response = completion.choices[0].message.content
                latency = (time.time() - start) * 1000
                return response, latency
            except Exception as e:
                print(f"  [Erreur API OpenAI: {e}]")

        elif anthropic_key:
            # --- Anthropic (Claude) ---
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=anthropic_key)
                message = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=500,
                    system=self.SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": query}]
                )
                response = message.content[0].text
                latency = (time.time() - start) * 1000
                return response, latency
            except Exception as e:
                print(f"  [Erreur API Anthropic: {e}]")

        # --- Mode simulation (sans clé API) ---
        # Réponses simulées réalistes pour la démo
        simulated_responses = {
            "résumé": (
                "Voici un résumé du chapitre demandé :\n"
                "• Point clé 1 : Les réseaux de neurones générateurs adversariaux (GANs) "
                "utilisent deux réseaux en compétition.\n"
                "• Point clé 2 : Le générateur crée des données synthétiques, "
                "le discriminateur évalue leur authenticité.\n"
                "• Point clé 3 : L'entraînement converge quand le discriminateur "
                "ne peut plus distinguer le réel du synthétique."
            ),
            "planning": (
                "Voici un planning suggéré pour votre semaine :\n"
                "• Lundi : Mathématiques (2h) + Révision cours (1h)\n"
                "• Mardi : TP Programmation (3h)\n"
                "• Mercredi : Lecture cours TEQ (2h)\n"
                "• Jeudi : Préparation mini-projet (3h)\n"
                "• Vendredi : Révisions générales + repos"
            ),
            "default": (
                f"[Réponse LLM simulée — activez une clé API pour des réponses réelles]\n\n"
                f"Concernant votre question : '{query}'\n\n"
                "Je peux vous aider avec des résumés de cours, des questions "
                "sur le contenu pédagogique, et la planification de vos révisions. "
                "N'hésitez pas à reformuler votre question."
            )
        }

        response = simulated_responses["default"]
        for key in simulated_responses:
            if key in query.lower():
                response = simulated_responses[key]
                break

        latency = (time.time() - start) * 1000
        return response, latency


def print_banner():
    print("=" * 60)
    print("   Farfalla — Campus Intelligent ENSA Béni Mellal")
    print("   Module TEQ | Architecture Cloud-Fog-Edge")
    print("=" * 60)
    print("Commandes : 'offline' | 'online' | 'stats' | 'history' | 'quit'")
    print("-" * 60)


def main():
    print_banner()

    student_id = input("Votre identifiant étudiant (ex: student_001) : ").strip()
    if not student_id:
        student_id = "student_001"

    assistant = EdgeAssistant(student_id=student_id)
    print(f"\nBonjour ! Je suis votre assistant pédagogique Edge. Comment puis-je vous aider ?\n")

    while True:
        try:
            user_input = input("Vous: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[Système] Au revoir !")
            break

        if not user_input:
            continue

        # Commandes système
        if user_input.lower() == "quit":
            print("[Système] Au revoir ! Bonne continuation dans vos études.")
            break

        if user_input.lower() == "offline":
            assistant.edge.simulate_cloud_outage()
            print("[Système] Mode hors-ligne activé — simulation coupure cloud\n")
            continue

        if user_input.lower() == "online":
            assistant.edge.restore_cloud()
            print("[Système] Connexion cloud restaurée\n")
            continue

        if user_input.lower() == "stats":
            stats = assistant.db.get_stats()
            print("\n[Statistiques de session]")
            print(f"  Total interactions : {stats['total_interactions']}")
            print(f"  Par source         : {stats['by_source']}")
            print(f"  Distribution stress: {stats['stress_distribution']}")
            print(f"  Latence moyenne    : {stats['avg_latency_ms']} ms\n")
            continue

        if user_input.lower() == "history":
            history = assistant.db.get_student_history(assistant.student_id)
            print(f"\n[Historique — {assistant.student_id}]")
            if not history:
                print("  Aucune interaction enregistrée.")
            for row in history:
                query, response, stress, source, latency, ts = row
                print(f"  [{ts[:19]}] ({source}, {stress}) : {query[:60]}...")
            print()
            continue

        # Traitement normal
        response = assistant.chat(user_input)
        print(f"\nAssistant: {response}\n")


if __name__ == "__main__":
    main()
