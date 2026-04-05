class StressDetector:
    """
    Analyse textuelle simple pour détecter frustration/stress.
    Approche par règles et mots-clés — fonctionne 100% en local.
    Aucune donnée n'est envoyée à un service externe.
    """

    STRESS_KEYWORDS = [
        "je comprends pas", "je comprends rien", "c'est nul", "impossible",
        "j'abandonne", "trop difficile", "je suis perdu", "rien ne marche",
        "j'en peux plus", "c'est incompréhensible", "je déteste", "stressé",
        "anxieux", "j'ai peur de rater", "je vais échouer", "help", "sos",
        "je galère", "je sais pas", "trop dur", "je comprends absolument rien",
        "c'est horrible", "j'arrive pas", "je n'arrive pas"
    ]

    FRUSTRATION_MARKERS = ["!!!", "???", "...", "wtf", "nul nul", "😤", "😭", "😩"]

    def analyze(self, text: str) -> dict:
        text_lower = text.lower()
        score = 0
        detected = []

        for keyword in self.STRESS_KEYWORDS:
            if keyword in text_lower:
                score += 2
                detected.append(keyword)

        for marker in self.FRUSTRATION_MARKERS:
            if marker in text_lower:
                score += 1
                detected.append(marker)

        # Détection des majuscules (signe d'énervement)
        letters = [c for c in text if c.isalpha()]
        if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.5:
            score += 1
            detected.append("texte_en_majuscules")

        level = "normal"
        if score >= 4:
            level = "high_stress"
        elif score >= 2:
            level = "moderate_stress"
        elif score >= 1:
            level = "mild_frustration"

        return {
            "level": level,
            "score": score,
            "triggers": detected,
            "message": self._get_support_message(level)
        }

    def _get_support_message(self, level: str) -> str | None:
        messages = {
            "high_stress": (
                "Je détecte que vous êtes très stressé(e). "
                "Prenez une pause, respirez. "
                "Voulez-vous que je simplifie l'explication ?"
            ),
            "moderate_stress": "Je sens que c'est difficile. Reformulons ensemble ce point.",
            "mild_frustration": "Pas de panique ! Je suis là pour vous aider.",
            "normal": None
        }
        return messages.get(level)
