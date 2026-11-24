"""Modules et questionnaire de la page Formation injectés une seule fois, au
premier démarrage : ce sont ceux de la feuille de suivi que le BCES utilisait.
Ils se modifient ensuite dans la page Formation."""

# Types dont les modules sont obligatoires par défaut (case cochée à la
# création) : les validations basiques et les formations obligatoires.
REQUIRED_CATEGORIES: tuple[str, ...] = ("basics", "mandatory")

# (type, nom)
DEFAULT_INTERN_MODULES: list[tuple[str, str]] = [
    ("basics", "DDS"),
    ("basics", "VM"),
    ("basics", "VC"),
    ("basics", "Airbag"),
    ("tools", "Examiner l’état global du patient"),
    ("tools", "Examiner les maladies du patient"),
    ("tools", "Radiologie"),
    ("tools", "Soins généraux"),
    ("tools", "Chirurgie"),
    ("tools", "Retrait de balle"),
    ("tools", "IPT"),
    ("tools", "Tenues patients"),
    ("tools", "Ouverture de dossier médical"),
    ("tools", "Changement CU"),
    ("tools", "Écriture de dossier"),
    ("tools", "Mettre les bonnes IPT"),
    ("tools", "Conduite du PIT sur route"),
    ("interventions", "AVP concitoyen"),
    ("interventions", "Déshydratation"),
    ("interventions", "Grosse bobologie"),
    ("interventions", "AVP"),
    ("interventions", "Chute +15 m"),
    ("interventions", "BPB simple"),
    ("interventions", "BPB fusillade"),
    ("interventions", "Brûlure"),
    ("interventions", "Explosion"),
    ("interventions", "Noyade"),
    ("interventions", "Arme blanche / contondante"),
    ("interventions", "Bagarre"),
    ("interventions", "Overdose"),
    ("interventions", "Animal"),
    ("interventions", "Gestion d’une unité X"),
    ("injuries", "Fissure / fracture nette"),
    ("injuries", "Fracture déplacée"),
    ("injuries", "Tassement"),
    ("injuries", "Luxation"),
    ("injuries", "Entorse"),
    ("injuries", "Chocs à la tête"),
    ("injuries", "Perforation d’organe"),
    ("injuries", "Hémorragie"),
    ("injuries", "Trépanation"),
]

# Formations de la période de formation : (type, nom)
DEFAULT_RESIDENT_MODULES: list[tuple[str, str]] = [
    ("mandatory", "Centrale"),
    ("mandatory", "Centrale de crise"),
    ("mandatory", "Off-Road"),
    ("mandatory", "Maritime"),
    ("mandatory", "Gestion Stock"),
    ("optional", "Prise d’otage"),
    ("optional", "Gestion état critique"),
    ("optional", "Permis chasse"),
    ("optional", "Détatouage"),
]

# (question, réponse attendue)
DEFAULT_INTERN_QUESTIONS: list[tuple[str, str]] = [
    (
        "Comment se gère une blessure par balle (sur place, diagnostic, opération, IPT) ? À quoi faut-il absolument penser ?",
        "Compression en cas d’hémorragie, pas d’IRM, recherche des projectiles, retrait des fragments si possible, "
        "IPT adaptés selon les cas, appel FdO via la centrale, message sur Discord.",
    ),
    (
        "Lors d’une arrivée sur un incendie ou une explosion, comment réagissez-vous et prenez-vous en charge le blessé sur place ?",
        "Attendre l’extinction du feu, sécuriser le blessé et soi-même (risque de sur-explosion), réanimation si besoin, "
        "prise des constantes, oxygène si nécessaire, antidouleurs.",
    ),
    (
        "Donner un diagnostic cohérent pour une chute de plus de 15 m et préciser les outils utilisés.",
        "Fractures multiples, hématome sous-dural, tassements vertébraux (et autres blessures cohérentes). "
        "Outils : radio, IRM, échographie selon les lésions.",
    ),
    ("Quels médicaments donner en cas de morsure d’animal ?", "AD + AI + AB + AR."),
    (
        "Quelle est la prise en charge d’une hypoglycémie (intervention, examens, traitement, IPT) ?",
        "Traitement sur place, réanimation si besoin, faire boire et manger, constantes, perfusion glucose / vitamine C, "
        "IPT 30 min sans effort physique.",
    ),
    ("Quel est le traitement d’un tassement vertébral ?", "Injection de gaz intervertébral."),
    (
        "Quels sont les IPT pour une blessure par arme blanche avec coma et que faut-il faire ?",
        "IPT 3 h. Appel FdO + message Discord « Blessure par arme ».",
    ),
    (
        "Que faire si vous ne connaissez pas un cas de figure ou en cas de doute ?",
        "Demander à un supérieur ou à un formateur.",
    ),
    (
        "Dans quels cas met-on des IPT et ouvre-t-on un dossier ?",
        "Quand le patient est à moins de 50 % de ses capacités physiques ou a des blessures moyennes à graves "
        "(rappel : plus de 75 % pansement, moins de 75 % poche de sang).",
    ),
    (
        "Avec quels outils gère-t-on une blessure grave ?",
        "Outils spécialisés, chirurgie si nécessaire, puis soins généraux.",
    ),
    (
        "Si le patient est inconscient, que faut-il faire ?",
        "Récupérer sa carte ID, ouvrir le dossier (allergies, infos), puis prise en charge normale.",
    ),
    (
        "Quels médicaments donner en cas de noyade avec de l’eau dans les poumons ?",
        "AD + AI + AB + AF + expectorants (+ oxygène).",
    ),
    (
        "Quels sont les IPT pour une fracture déplacée et quelle opération + médicaments ?",
        "Chirurgie (AL membres ou AG) : réalignement, retrait des fragments, plaques / vis, PDSR, bandages, attelle. "
        "Médicaments : AD + AI + AB.",
    ),
    (
        "Quelles blessures sont visibles à la radio, à l’échographie et à l’IRM ?",
        "Radio : os, corps étrangers. Écho : tissus mous. IRM : tissus mous + os en profondeur (sans corps étrangers).",
    ),
    (
        "Comment gère-t-on une blessure chimique ?",
        "Comme une brûlure normale, mais on analyse le sang de la personne pour vérifier si elle est contaminée.",
    ),
    ("Quels IPT pour une personne percutée par une voiture et tombée dans le coma ?", "AVP coma : 2 h à 3 h."),
    (
        "Quels IPT pour une luxation après une chute de moins de 15 m sans coma ?",
        "Entorse / luxation / fracture simple : 30 min à 1 h.",
    ),
    (
        "Si une personne est légèrement blessée par balle (GPB 9 mm) ou a une petite égratignure, quels IPT ?",
        "0 min.",
    ),
    (
        "Comment prioriser les blessures suivantes : fracture déplacée du tibia, hématome sous-dural, pneumothorax, "
        "fracture nette des côtes, brûlure au 3e degré du bras ?",
        "Hématome sous-dural → pneumothorax → fracture des côtes → fracture déplacée du tibia → brûlure au 3e degré du bras.",
    ),
    ("Quels IPT pour une explosion sans coma ? Et avec coma ?", "Sans coma : entre 1 h et 4 h. Avec coma : 6 h."),
]
