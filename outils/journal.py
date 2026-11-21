"""Journal d'activité du clipping : écrit dans le journal commun de la Salle des agents
(~/.claude/salle-agents/evenements.jsonl), avec le projet « Clipping ».

Dans un script :  from journal import noter ; noter("monteur", "debut", "uqC2WA8Q0RE", "Monte le clip 1")
En ligne de commande (pour /clipper, avant et après chaque agent Claude) :
  python -I outils/journal.py <agent> <debut|fin|info|erreur> <id_video ou -> "<texte>"
"""
import importlib.util, sys
from pathlib import Path

# Le journal commun porte le même nom de fichier que celui-ci : on le charge sous un autre nom pour ne pas s'importer soi-même.
_spec = importlib.util.spec_from_file_location("journal_commun", Path.home() / ".claude" / "salle-agents" / "journal.py")
_commun = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_commun)
_noter = _commun.noter


def noter(agent, etat, video=None, texte=""):
    _noter(agent, etat, video, texte, projet="Clipping")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    noter(sys.argv[1], sys.argv[2], sys.argv[3], " ".join(sys.argv[4:]))
