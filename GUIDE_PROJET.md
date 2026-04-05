# Guide Complet — Assistant IA Génératif Edge pour Campus Intelligent
**Module : Technologies Émergentes & Quantum | Pr. TOUIL | ENSA Beni Mellal**

---

## Table des matières

1. [Comprendre le projet](#1-comprendre-le-projet)
2. [Architecture du système](#2-architecture-du-système)
3. [Prototype — Option A (recommandée)](#3-prototype--option-a-recommandée)
4. [Analyse des risques](#4-analyse-des-risques)
5. [Structure du rapport](#5-structure-du-rapport)
6. [Préparation de la démo](#6-préparation-de-la-démo)
7. [Checklist finale](#7-checklist-finale)

---

## 1. Comprendre le projet

### Ce qu'on vous demande de concevoir

Un **assistant IA génératif local (Edge)** pour étudiants, capable de :

| Fonctionnalité | Description |
|---|---|
| Résumés de cours | Générer des résumés à partir de contenu fourni |
| Q&A étudiant | Répondre aux questions sur les cours |
| Planning personnalisé | Suggérer un emploi du temps adapté |
| Détection stress/frustration | Analyse textuelle simple du message de l'étudiant |
| Mode dégradé | Fonctionner sans connexion cloud |

### Contraintes à respecter

- Latence < 200 ms en local
- Protection des données étudiantes (pas d'envoi de données sensibles au cloud)
- Architecture imposée : **Utilisateur → Edge → Fog (optionnel) → Cloud**
- Justification de chaque choix technique

---

## 2. Architecture du système

### 2.1 Vue d'ensemble (schéma textuel)

```
┌─────────────────────────────────────────────────────────────┐
│                        CLOUD                                │
│  - Modèle LLM pré-entraîné (GPT / LLaMA)                  │
│  - Synchronisation périodique                               │
│  - Fine-tuning & mises à jour du modèle                    │
└───────────────────────────┬─────────────────────────────────┘
                            │ sync périodique (HTTPS)
┌───────────────────────────▼─────────────────────────────────┐
│                     FOG (optionnel)                         │
│  - Serveur intermédiaire campus (ex: serveur labo)         │
│  - Agrégation de requêtes                                   │
│  - Cache des réponses fréquentes                            │
└───────────────────────────┬─────────────────────────────────┘
                            │ réseau local campus
┌───────────────────────────▼─────────────────────────────────┐
│                       EDGE                                   │
│  - Modèle optimisé local (quantifié/compressé)             │
│  - Base de données locale SQLite (données étudiants)       │
│  - Couche de détection stress (règles + mots-clés)         │
│  - Mode dégradé si cloud indisponible                       │
│  - Latence cible < 200 ms                                   │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    UTILISATEUR                               │
│  - Interface chat (terminal ou web simple)                  │
│  - Étudiant ENSA                                            │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Flux des données

```
1. Étudiant envoie un message
        ↓
2. Couche Edge reçoit la requête
        ↓
3. Détection du type de requête (résumé / Q&A / planning / stress)
        ↓
4. Vérification du cache local
   ├── Cache HIT → réponse immédiate (< 50 ms)
   └── Cache MISS → traitement LLM local
        ↓
5. Si réponse locale insuffisante ET cloud disponible
   → envoi au cloud (données anonymisées uniquement)
        ↓
6. Réponse retournée à l'étudiant
        ↓
7. Journalisation locale (SQLite) — données sensibles jamais en cloud
```

### 2.3 Répartition des traitements

| Traitement | Edge | Fog | Cloud |
|---|---|---|---|
| Détection stress (règles) | ✓ | | |
| Q&A simple (cache) | ✓ | | |
| Génération résumé court | ✓ | | |
| Q&A complexe | | ✓ | ✓ |
| Fine-tuning du modèle | | | ✓ |
| Stockage données étudiants | ✓ (local uniquement) | | |
| Mises à jour modèle | | | ✓ |

---

## 3. Prototype — Option A (recommandée)

L'Option A utilise une **API LLM cloud** avec une **couche Edge simulée en Python**.

### 3.1 Structure des fichiers

```
projet_teq/
├── edge_assistant.py       # Point d'entrée principal
├── edge_layer.py           # Simulation de la couche Edge
├── stress_detector.py      # Détection frustration/stress
├── local_db.py             # Gestion SQLite (données locales)
├── cloud_llm.py            # Appel API LLM (Claude / OpenAI)
├── data/
│   └── students.db         # Base de données SQLite locale
└── requirements.txt
```

### 3.2 Code — `edge_layer.py`

```python
import time
import json
import os

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
            "default": "Je fonctionne en mode dégradé. Reconnectez-vous pour une réponse complète."
        }
        for key in fallback:
            if key in query.lower():
                return fallback[key]
        return fallback["default"]
    
    def simulate_cloud_outage(self):
        self.cloud_available = False
    
    def restore_cloud(self):
        self.cloud_available = True
```

### 3.3 Code — `stress_detector.py`

```python
class StressDetector:
    """
    Analyse textuelle simple pour détecter frustration/stress.
    Approche par règles et mots-clés — fonctionne 100% en local.
    """
    
    STRESS_KEYWORDS = [
        "je comprends pas", "c'est nul", "impossible", "j'abandonne",
        "trop difficile", "je suis perdu", "rien ne marche", "j'en peux plus",
        "c'est incompréhensible", "je déteste", "stressé", "anxieux",
        "j'ai peur de rater", "je vais échouer", "help", "sos"
    ]
    
    FRUSTRATION_MARKERS = ["!!!", "???", "...", "wtf", "nul", "nul nul"]
    
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
        if sum(1 for c in text if c.isupper()) > len(text) * 0.5:
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
    
    def _get_support_message(self, level: str) -> str:
        messages = {
            "high_stress": "Je détecte que vous êtes très stressé(e). Prenez une pause, respirez. Voulez-vous que je simplifie l'explication ?",
            "moderate_stress": "Je sens que c'est difficile. Reformulons ensemble ce point.",
            "mild_frustration": "Pas de panique ! Je suis là pour vous aider.",
            "normal": None
        }
        return messages.get(level)
```

### 3.4 Code — `local_db.py`

```python
import sqlite3
from datetime import datetime

class LocalDatabase:
    """
    Base de données locale SQLite.
    Les données étudiantes ne quittent jamais l'Edge.
    """
    
    def __init__(self, db_path: str = "data/students.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                query TEXT NOT NULL,
                response TEXT,
                stress_level TEXT,
                source TEXT,
                latency_ms REAL,
                timestamp TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS student_planning (
                student_id TEXT PRIMARY KEY,
                courses TEXT,
                preferences TEXT,
                last_updated TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def log_interaction(self, student_id, query, response, 
                        stress_level, source, latency_ms):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO interactions 
            (student_id, query, response, stress_level, source, latency_ms, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (student_id, query, response, stress_level, 
              source, latency_ms, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    
    def get_student_history(self, student_id: str, limit: int = 5):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT query, response, timestamp 
            FROM interactions 
            WHERE student_id = ?
            ORDER BY timestamp DESC LIMIT ?
        """, (student_id, limit))
        rows = c.fetchall()
        conn.close()
        return rows
```

### 3.5 Code — `edge_assistant.py` (point d'entrée)

```python
import time
import os
from edge_layer import EdgeLayer
from stress_detector import StressDetector
from local_db import LocalDatabase

# Pour l'API cloud, utilisez : import anthropic OU import openai
# Exemple avec l'API Anthropic (Claude)

class EdgeAssistant:
    
    SYSTEM_PROMPT = """Tu es un assistant pédagogique pour étudiants de l'ENSA Beni Mellal.
Tu peux : résumer des cours, répondre à des questions, proposer un planning.
Réponds toujours en français, de manière claire et concise.
Si l'étudiant semble stressé, sois particulièrement bienveillant."""
    
    def __init__(self):
        self.edge = EdgeLayer()
        self.stress_detector = StressDetector()
        self.db = LocalDatabase()
        self.student_id = "student_001"  # À rendre dynamique
    
    def chat(self, user_input: str) -> str:
        start = time.time()
        
        # Étape 1 : Détection du stress (100% local)
        stress_analysis = self.stress_detector.analyze(user_input)
        
        # Étape 2 : Traitement via couche Edge
        edge_result = self.edge.process(user_input, self.student_id)
        
        if edge_result["source"] in ("edge_cache", "edge_local_degraded"):
            response = edge_result["response"]
            source = edge_result["source"]
            latency = edge_result["latency_ms"]
        else:
            # Étape 3 : Appel cloud LLM
            response, latency = self._call_cloud_llm(user_input, stress_analysis)
            source = "cloud"
            self.edge.cache_response(user_input, response)
        
        # Étape 4 : Message de support si stress détecté
        if stress_analysis["message"]:
            response = f"[Support] {stress_analysis['message']}\n\n{response}"
        
        # Étape 5 : Journalisation locale uniquement
        self.db.log_interaction(
            self.student_id, user_input, response,
            stress_analysis["level"], source, latency
        )
        
        total_latency = (time.time() - start) * 1000
        print(f"[Latence: {total_latency:.1f}ms | Source: {source} | Stress: {stress_analysis['level']}]")
        
        return response
    
    def _call_cloud_llm(self, query: str, stress_info: dict) -> tuple:
        """Appel à l'API LLM cloud (remplacer par votre clé API)."""
        start = time.time()
        
        # Exemple avec anthropic SDK
        # import anthropic
        # client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        # message = client.messages.create(
        #     model="claude-haiku-4-5-20251001",
        #     max_tokens=500,
        #     system=self.SYSTEM_PROMPT,
        #     messages=[{"role": "user", "content": query}]
        # )
        # response = message.content[0].text
        
        # Simulation pour la démo (remplacer par l'appel réel)
        response = f"[Réponse simulée cloud] Voici ma réponse à : '{query}'"
        
        latency = (time.time() - start) * 1000
        return response, latency


def main():
    print("=== Assistant IA Edge — ENSA Beni Mellal ===")
    print("Tapez 'quit' pour quitter | 'offline' pour simuler coupure cloud\n")
    
    assistant = EdgeAssistant()
    
    while True:
        user_input = input("Vous: ").strip()
        
        if not user_input:
            continue
        if user_input.lower() == "quit":
            break
        if user_input.lower() == "offline":
            assistant.edge.simulate_cloud_outage()
            print("[Système] Mode hors-ligne activé (simulation coupure cloud)")
            continue
        if user_input.lower() == "online":
            assistant.edge.restore_cloud()
            print("[Système] Connexion cloud restaurée")
            continue
        
        response = assistant.chat(user_input)
        print(f"\nAssistant: {response}\n")


if __name__ == "__main__":
    main()
```

### 3.6 Installation

```bash
# Créer l'environnement
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Installer les dépendances
pip install anthropic sqlite3

# Créer le dossier data
mkdir -p data

# Lancer l'assistant
python edge_assistant.py
```

---

## 4. Analyse des risques

### 4.1 Tableau des risques identifiés

| Risque | Description | Impact | Solution proposée |
|---|---|---|---|
| **Biais algorithmiques** | Le LLM reproduit des biais de ses données d'entraînement | Réponses discriminatoires | Filtrage des sorties + audit régulier |
| **Dépendance au cloud** | Si le cloud tombe, l'assistant est limité | Service interrompu | Mode dégradé local + cache Edge |
| **Hallucinations** | Le LLM génère des informations fausses | Étudiants mal informés | Vérification humaine + RAG sur contenu cours |
| **Fuite de données** | Données étudiantes envoyées au cloud | Violation RGPD | Données sensibles stockées localement uniquement |
| **Attaque man-in-the-middle** | Interception des requêtes Edge → Cloud | Compromission données | Chiffrement TLS + authentification JWT |
| **Injection de prompt** | Manipulation de l'assistant par un étudiant | Comportement malveillant | Validation et nettoyage des inputs |
| **Souveraineté numérique** | Dépendance à des LLM étrangers (OpenAI, Anthropic) | Perte de contrôle | Privilégier LLaMA open-source hébergé localement |

### 4.2 Solutions de gouvernance IA

```
Filtrage      → Validation des inputs avant LLM + modération des outputs
Audit         → Journalisation de toutes les interactions (SQLite local)
Monitoring    → Dashboard des métriques (latence, taux d'erreur, stress détecté)
Gouvernance   → Politique claire sur quelles données vont au cloud
```

---

## 5. Structure du rapport (15–20 pages)

```
Page de garde
Table des matières

1. Introduction (1 page)
   - Contexte : campus intelligent, Industry 5.0
   - Problématique : IA générative locale vs cloud

2. Contexte théorique (2-3 pages)
   - Technologies émergentes (cours Ch.1)
   - IA générative : LLM, Edge AI (cours Ch.2)
   - Architecture Cloud-Fog-Edge (cours Ch.3)

3. Conception de l'architecture (3-4 pages)
   - Schéma d'architecture complet
   - Flux des données
   - Répartition des traitements
   - Justification des choix techniques

4. Prototype simplifié (3-4 pages)
   - Description de l'implémentation
   - Captures d'écran de la démo
   - Mesures de latence (tableaux)
   - Comparaison mode cloud vs mode Edge local

5. Analyse des risques (2-3 pages)
   - Tableau des risques (biais, cybersécurité, souveraineté)
   - Solutions proposées (filtrage, audit, monitoring)
   - Stratégie de souveraineté numérique

6. Conclusion (1 page)
   - Bilan
   - Perspectives (amélioration du modèle, déploiement réel)

Bibliographie
Annexes (code source, captures d'écran supplémentaires)
```

---

## 6. Préparation de la démo

### Scénario de démonstration (5 minutes)

**Acte 1 — Mode normal (cloud disponible)**
```
Vous: "Résume-moi le chapitre sur les GANs"
→ Montrer la latence mesurée
→ Réponse générée par le LLM cloud

Vous: "Résume-moi le chapitre sur les GANs"  (même question)
→ Montrer que la 2e fois, réponse vient du cache Edge (latence < 50ms)
```

**Acte 2 — Détection de stress**
```
Vous: "je comprends RIEN à ce cours c'est impossible!!!"
→ Montrer l'analyse de stress détectée
→ Message de support ajouté à la réponse
```

**Acte 3 — Mode dégradé (simulation coupure cloud)**
```
Taper: offline
Vous: "Quel est mon planning?"
→ Montrer que l'assistant répond quand même (mode dégradé)
→ Données restent locales
```

**Acte 4 — Données locales**
```
→ Ouvrir le fichier students.db avec un viewer SQLite
→ Montrer que les données sont stockées localement
→ Montrer l'historique des interactions
```

---

## 7. Checklist finale

### Livrables à préparer

- [ ] **Schéma d'architecture** (draw.io, Lucidchart, ou PowerPoint)
  - Couches Edge / Fog / Cloud clairement délimitées
  - Flux des données annotés
  - Répartition des traitements indiquée

- [ ] **Code du prototype** fonctionnel
  - `edge_layer.py` (cache + mode dégradé)
  - `stress_detector.py` (analyse textuelle)
  - `local_db.py` (SQLite)
  - `edge_assistant.py` (point d'entrée)

- [ ] **Rapport (15-20 pages)**
  - Architecture justifiée
  - Analyse des risques complète
  - Captures de la démo

- [ ] **Présentation orale (15 min)**
  - 5 min : contexte + architecture
  - 5 min : démo live
  - 5 min : analyse des risques + conclusion

### Points clés à mentionner à l'oral

1. **Pourquoi Edge et pas seulement Cloud ?** → Latence, souveraineté, mode hors-ligne
2. **Comment on protège les données étudiantes ?** → SQLite local, rien de sensible au cloud
3. **Comment on détecte le stress ?** → Règles + mots-clés, 100% local, pas de ML externe
4. **Qu'est-ce que le mode dégradé ?** → L'assistant continue de fonctionner sans internet
5. **Quels sont les risques principaux ?** → Biais, hallucinations, dépendance cloud, souveraineté

---

*Guide réalisé pour le Mini-Projet TEQ — ENSA Beni Mellal — IA & Cybersécurité S4*
