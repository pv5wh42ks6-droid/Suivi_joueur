import streamlit as st
import pandas as pd

st.set_page_config(page_title="Suivi Charge & Fatigue", layout="wide")

# Agrandissement de la police pour une meilleure lisibilité
st.markdown("""
    <style>
    html, body, [class*="css"] {
        font-size: 19px !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 38px !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 19px !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 16px !important;
    }
    .stDataFrame {
        font-size: 18px !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("Suivi de Charge (sRPE) & Bien-être")

# 1. Connexion au Google Sheet (remets ton lien CSV publié sur le web ici)
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSZsVjNKilfSEcCmvFoLjyDr4KNxOs06P52uO-nxqMtQPf-DZYakuj6qQ3IvpbR3jumiMz-QAeBN6Qd/pub?gid=1027957261&single=true&output=csv"

@st.cache_data(ttl=60)
def load_data(url):
    df = pd.read_csv(url)
    df.columns = [
        "Date", "Joueur", "Type", "RPE",
        "Sommeil", "Fatigue", "Courbatures", "Duree"
    ]
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")

    for col in ["Duree", "RPE", "Sommeil", "Fatigue", "Courbatures"]:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace("|", "", regex=False).str.strip(),
            errors="coerce"
        )

    df = df.dropna(subset=["Date"])
    df["Charge_sRPE"] = df["Duree"] * df["RPE"]
    df["Score_BienEtre"] = df["Sommeil"] + df["Fatigue"] + df["Courbatures"]
    return df

df = load_data(SHEET_URL)

# 2. Filtres dans la barre latérale
st.sidebar.header("Filtres")

periode = st.sidebar.selectbox(
    "Période d'analyse",
    ["7 derniers jours", "14 derniers jours", "21 derniers jours", "28 derniers jours", "Toute la saison"]
)

maintenant = pd.Timestamp.now()
jours_map = {
    "7 derniers jours": 7,
    "14 derniers jours": 14,
    "21 derniers jours": 21,
    "28 derniers jours": 28,
}

if periode in jours_map:
    df_periode = df[df["Date"] >= maintenant - pd.Timedelta(days=jours_map[periode])]
else:
    df_periode = df

joueurs = ["Tous"] + sorted(df["Joueur"].dropna().unique().tolist())
selection = st.sidebar.selectbox("Filtrer par joueur", joueurs)

df_filtre = df_periode if selection == "Tous" else df_periode[df_periode["Joueur"] == selection]

# Calcul du ratio ACWR (toujours basé sur 7 jours vs 28 jours pour le joueur ou l'équipe)
df_acwr = df if selection == "Tous" else df[df["Joueur"] == selection]
charge_7j = df_acwr[df_acwr["Date"] >= maintenant - pd.Timedelta(days=7)]["Charge_sRPE"].sum()
charge_28j = df_acwr[df_acwr["Date"] >= maintenant - pd.Timedelta(days=28)]["Charge_sRPE"].sum()
charge_chronique = charge_28j / 4  # Moyenne hebdomadaire sur 4 semaines

acwr = (charge_7j / charge_chronique) if charge_chronique > 0 else None

# Fonctions d'interprétation
def interpreter_rpe(rpe):
    if rpe < 2:
        return "Très facile / Récupération"
    elif rpe < 3.5:
        return "Facile à Modéré"
    elif rpe < 5:
        return "Assez difficile"
    elif rpe < 7:
        return "Difficile (Séance intense)"
    elif rpe < 9:
        return "Très difficile (Haute charge)"
    else:
        return "Effort maximal"

def interpreter_charge(charge):
    if charge < 300:
        return "Charge faible (Récup / J-1)"
    elif charge < 500:
        return "Charge modérée (Entretien)"
    elif charge < 700:
        return "Charge élevée (Développement)"
    else:
        return "Charge très élevée (Surcharge)"

def interpreter_bien_etre(score):
    if score <= 8:
        return "Fatigue importante (Vigilance)"
    elif score <= 11:
        return "État moyen (À surveiller)"
    else:
        return "Bonne fraîcheur"

def interpreter_acwr(val):
    if val is None:
        return "Données insuffisantes"
    elif val < 0.8:
        return "Sous-charge"
    elif val <= 1.3:
        return "Zone optimale"
    elif val <= 1.5:
        return "Vigilance (Pic de charge)"
    else:
        return "Zone rouge (Risque blessure)"

# 3. Alertes récentes enrichies (tout en haut pour le coach)
st.subheader("Alertes Fatigue / Surcharge (dernières 48h)")
df_48h = df[df["Date"] >= maintenant - pd.Timedelta(hours=48)].copy()

def analyser_alerte(row):
    motifs = []
    if row["Courbatures"] <= 2:
        motifs.append("Douleurs / Courbatures élevées")
    if row["Sommeil"] <= 2:
        motifs.append("Mauvais sommeil")
    if row["Score_BienEtre"] <= 8:
        motifs.append("Bien-être global bas")
    if row["RPE"] >= 8 or row["Charge_sRPE"] >= 700:
        motifs.append("Grosse charge (RPE/sRPE)")
    return " + ".join(motifs)

def niveau_alerte(row):
    if (row["RPE"] >= 8 and row["Score_BienEtre"] <= 8) or row["Courbatures"] <= 2:
        return "🔴 Critique"
    return "🟠 Vigilance"

def action_coach(row):
    if row["Courbatures"] <= 2:
        return "Bilan individuel / Adapter la séance"
    elif row["RPE"] >= 8 and row["Score_BienEtre"] <= 8:
        return "Alléger le volume / Récupération"
    else:
        return "Surveiller à l'échauffement"

if not df_48h.empty:
    df_48h["Motif"] = df_48h.apply(analyser_alerte, axis=1)
    alertes = df_48h[df_48h["Motif"] != ""].copy()

    if not alertes.empty:
        alertes["Niveau"] = alertes.apply(niveau_alerte, axis=1)
        alertes["Action conseillée"] = alertes.apply(action_coach, axis=1)
        alertes["Priorite"] = alertes["Niveau"].apply(lambda x: 0 if "Critique" in x else 1)
        alertes = alertes.sort_values(by="Priorite")

        st.warning(f"{len(alertes)} alerte(s) détectée(s) sur les 48 dernières heures")
        st.dataframe(
            alertes[["Niveau", "Joueur", "Motif", "Action conseillée"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("RAS : aucune alerte fatigue, douleur ou surcharge sur les dernières 48h.")
else:
    st.info("Aucune donnée saisie sur les 48 dernières heures.")

st.divider()

# 4. Indicateurs clés (KPIs)
col1, col2, col3, col4 = st.columns(4)
if not df_filtre.empty:
    charge_moy = df_filtre["Charge_sRPE"].mean()
    rpe_moy = df_filtre["RPE"].mean()
    be_moy = df_filtre["Score_BienEtre"].mean()

    col1.metric("Charge moyenne (sRPE)", f"{charge_moy:.0f} UA", interpreter_charge(charge_moy), delta_color="off")
    col2.metric("RPE moyen", f"{rpe_moy:.1f} / 10", interpreter_rpe(rpe_moy), delta_color="off")
    col3.metric("Bien-être moyen", f"{be_moy:.1f} / 15", interpreter_bien_etre(be_moy), delta_color="off")
    col4.metric(
        "Ratio ACWR (7j / 28j)",
        f"{acwr:.2f}" if acwr is not None else "N/A",
        interpreter_acwr(acwr),
        delta_color="off"
    )
else:
    st.info("Aucune donnée enregistrée sur cette période.")

# 5. Graphique d'évolution de la charge + Guide de lecture
st.subheader(f"Évolution de la charge (sRPE) — {periode}")
if not df_filtre.empty:
    charge_jour = (
        df_filtre.assign(Jour=df_filtre["Date"].dt.strftime("%d/%m"))
        .groupby("Jour", sort=False)["Charge_sRPE"]
        .mean()
    )
    st.bar_chart(charge_jour)

with st.expander("Guide de lecture des indicateurs (RPE, Charge, Bien-être, ACWR)"):
    st.markdown("""
    **Échelle RPE (Borg CR-10)**
    * **0 à 2 / 10 :** Très facile — récupération active, décrassage.
    * **3 à 4 / 10 :** Modéré à assez difficile — séance technique ou veille de match.
    * **5 à 6 / 10 :** Difficile — entraînement standard soutenu.
    * **7 à 8 / 10 :** Très difficile — séance physique intense ou match.
    * **9 à 10 / 10 :** Quasi-maximal à maximal — effort extrême.

    **Charge de séance (sRPE = Durée × RPE)**
    * **Moins de 300 UA :** Séance légère (récupération / J-1).
    * **300 – 500 UA :** Séance modérée.
    * **500 – 700 UA :** Grosse séance de travail.
    * **Plus de 700 UA :** Très grosse charge (match ou pic hebdomadaire).

    **Score Bien-être (Sommeil + Forme + Musculaire sur 15)**
    * **12 à 15 / 15 :** Joueur frais, apte à encaisser la charge.
    * **9 à 11 / 15 :** Fatigue modérée, à surveiller.
    * **8 / 15 ou moins :** Alerte fatigue — adapter la séance ou échanger avec le joueur.

    **Ratio ACWR (Charge Aiguë 7j / Charge Chronique 28j)**
    * **Moins de 0,8 :** Sous-charge (risque de perte de rythme).
    * **0,8 à 1,3 :** Zone optimale (charge bien tolérée).
    * **1,3 à 1,5 :** Vigilance (augmentation rapide de la charge).
    * **Plus de 1,5 :** Zone rouge (pic trop brutal, risque élevé de blessure).
    """)