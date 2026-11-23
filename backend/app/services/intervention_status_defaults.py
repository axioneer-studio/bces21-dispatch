"""Statuts d'intervention injectés au démarrage quand la table est vide.

Ce sont les statuts et les lieux que le Dispatch proposait avant qu'ils soient
gérés dans Administration : mêmes clés, pour que les interventions existantes
gardent leur statut. « Primo » est marqué « Primo Inter », pour la synchro avec
la Crise. Les statuts sont proposés avant les lieux.
"""

STATUS_KIND = "status"
PLACE_KIND = "place"

# (clé, libellé, emoji, Primo Inter)
DEFAULT_STATUSES: list[tuple[str, str, str, bool]] = [
    ("inter_ambulance", "Inter", "🚑", False),
    ("inter_helico", "Inter", "🚁", False),
    ("inter_bateau", "Inter", "⛵", False),
    ("pat", "Pat", "👣", False),
    ("pat_avp", "Pat AVP", "🤕", False),
    ("pat_airbag", "Pat Airbag", "🎈", False),
    ("retour_0", "Retour 0", "0️⃣", False),
    ("retour_1", "Retour 1", "1️⃣", False),
    ("retour_2", "Retour 2", "2️⃣", False),
    ("primo", "Primo", "🚨", True),
    ("navette", "Navette", "🚑", False),
    ("ope_crise", "Opé crise", "🧑‍⚕️", False),
    ("patrouille", "Patrouille", "🚑", False),
    ("patrouille_inter_service", "Patrouille inter service", "🚑", False),
    ("patrouille_vm", "Patrouille VM", "⭐", False),
    ("event", "Event", "🎉", False),
    ("renfort_lses", "Renfort LSES", "💪", False),
    ("enterrement", "Enterrement", "🪦", False),
    ("tour_bces", "Tour de BCES", "🏃🏻", False),
    ("au_coin", "Au coin", "📐", False),
    ("prise_otage", "Prise d'otage", "🏦", False),
    ("envie_caner", "Envie de caner", "☠️", False),
]

# (clé, libellé, emoji)
DEFAULT_PLACES: list[tuple[str, str, str]] = [
    ("bces", "BCES", "🏥"),
    ("lses", "LSES", "🏥"),
    ("hopital_central", "Hopital Central", "🏥"),
    ("zombie", "Zombie", "🔧"),
    ("bennys", "Bennys", "🔧"),
    ("hopital", "HOPITAL", "🏥"),
    ("galapagos", "GALAPAGOS", "🌴"),
    ("irm", "IRM", "🎧"),
    ("radio_room", "Radio", "☢️"),
    ("ope_1", "Salle Opé 1", "🛏️"),
    ("ope_2", "Salle Opé 2", "🛏️"),
    ("ope_3", "Salle Opé 3", "🛏️"),
    ("soin_intensif", "Soin Intensif", "🛏️"),
    ("gordo", "Gordo", "🛏️"),
    ("chianski", "Chianski", "🛏️"),
    ("chilliad", "Chilliad", "🛏️"),
    ("josiah", "Josiah", "🛏️"),
]

# (clé, libellé, emoji, Primo Inter, type), dans l'ordre d'affichage de chaque type.
DEFAULT_INTERVENTION_STATUSES: list[tuple[str, str, str, bool, str]] = [
    *((key, label, emoji, is_primo, STATUS_KIND) for key, label, emoji, is_primo in DEFAULT_STATUSES),
    *((key, label, emoji, False, PLACE_KIND) for key, label, emoji in DEFAULT_PLACES),
]
