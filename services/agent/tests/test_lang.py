from app.agent.lang import detect_lang


def test_arabic_question():
    assert detect_lang("ما هو عقد العمل؟") == "ar"


def test_french_question():
    assert detect_lang("Qu'est-ce que le contrat de travail ?") == "fr"


def test_ambiguous_defaults_to_ar():
    # Chiffres et ponctuation uniquement → pas d'alphabet majoritaire → défaut AR
    assert detect_lang("Article 505") == "fr"  # "Article" est latin
    assert detect_lang("505") == "ar"  # aucun alphabet → défaut AR


def test_mixed_ar_majority():
    # Question principalement AR avec un mot FR → AR
    assert detect_lang("ما هي عقوبة le vol في القانون المغربي؟") == "ar"


def test_mixed_fr_majority():
    # Question principalement FR avec un mot AR → FR
    assert detect_lang("Quelles sont les sanctions pour السرقة en droit marocain ?") == "fr"


def test_empty_defaults_to_ar():
    assert detect_lang("") == "ar"
