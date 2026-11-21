import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

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
    df["Type"] = df["Type"].astype(str).str.strip().str.capitalize()
    df["Charge_sRPE"] = df["Duree"] * df["RPE"]
    df["Score_BienEtre"] = df["Sommeil"] + df["Fatigue"] + df["Courbatures"]
    df["Seance_ID"] = df["Date"].dt.strftime("%d/%m/%Y") + " — " + df["Type"]
    return df

df = load_data(SHEET_URL)
maintenant = pd.Timestamp.now()

# Fonctions d'interprétation
def interpreter_rpe(rpe):
    if rpe < 2: return "Très facile / Récupération"
    elif rpe < 3.5: return "Facile à Modéré"
    elif rpe < 5: return "Assez difficile"
    elif rpe < 7: return "Difficile (Séance intense)"
    elif rpe < 9: return "Très difficile (Haute charge)"
    else: return "Effort maximal"

def interpreter_charge(charge):
    if charge < 300: return "Charge faible (Récup / J-1)"
    elif charge < 500: return "Charge modérée (Entretien)"
    elif charge < 700: return "Charge élevée (Développement)"
    else: return "Charge très élevée (Surcharge)"

def interpreter_bien_etre(score):
    if score <= 8: return "Fatigue importante (Vigilance)"
    elif score <= 11: return "État moyen (À surveiller)"
    else: return "Bonne fraîcheur"

def interpreter_acwr(val):
    if val is None: return "Données insuffisantes"
    elif val < 0.8: return "Sous-charge"
    elif val <= 1.3: return "Zone optimale"
    elif val <= 1.5: return "Vigilance (Pic de charge)"
    else: return "Zone rouge (Risque blessure)"

def couleur_charge(val):
    if val >= 700: return "#EF4444"   # Rouge (Surcharge)
    elif val >= 500: return "#F59E0B" # Orange (Élevée)
    else: return "#10B981"            # Vert (Modérée/Faible)

# 2. Filtres dans la barre latérale
st.sidebar.header("Filtres (Vue Globale)")

periode = st.sidebar.selectbox(
    "Période d'analyse",
    ["7 derniers jours", "14 derniers jours", "21 derniers jours", "28 derniers jours", "Toute la saison"]
)

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

# Calcul du ratio ACWR
df_acwr = df if selection == "Tous" else df[df["Joueur"] == selection]
charge_7j = df_acwr[df_acwr["Date"] >= maintenant - pd.Timedelta(days=7)]["Charge_sRPE"].sum()
charge_28j = df_acwr[df_acwr["Date"] >= maintenant - pd.Timedelta(days=28)]["Charge_sRPE"].sum()
charge_chronique = charge_28j / 4
acwr = (charge_7j / charge_chronique) if charge_chronique > 0 else None

# Création des 2 onglets principaux
tab1, tab2 = st.tabs(["📊 Vue Globale & Tendances", "🎯 Zoom sur une séance"])

# ==========================================
# ONGLET 1 : VUE GLOBALE & ALERTES
# ==========================================
with tab1:
    st.subheader("Alertes Fatigue / Surcharge (dernières 48h)")
    df_48h = df[df["Date"] >= maintenant - pd.Timedelta(hours=48)].copy()
    df_48h = df_48h.sort_values("Date").drop_duplicates(subset=["Joueur"], keep="last")

    def analyser_alerte(row):
        motifs = []
        if row["Courbatures"] <= 2: motifs.append("Douleurs / Courbatures")
        if row["Sommeil"] <= 2: motifs.append("Mauvais sommeil")
        if row["Score_BienEtre"] <= 8: motifs.append("Bien-être bas")
        if row["RPE"] >= 8 or row["Charge_sRPE"] >= 700: motifs.append("Grosse charge")
        return " + ".join(motifs)

    def niveau_alerte(row):
        if (row["RPE"] >= 8 and row["Score_BienEtre"] <= 8) or row["Courbatures"] <= 2:
            return "🔴 Critique"
        return "🟠 Vigilance"

    def action_coach(row):
        if row["Courbatures"] <= 2: return "Bilan individuel / Adapter la séance"
        elif row["RPE"] >= 8 and row["Score_BienEtre"] <= 8: return "Alléger le volume / Récupération"
        else: return "Surveiller à l'échauffement"

    if not df_48h.empty:
        df_48h["Motif"] = df_48h.apply(analyser_alerte, axis=1)
        alertes = df_48h[df_48h["Motif"] != ""].copy()

        if not alertes.empty:
            alertes["Niveau"] = alertes.apply(niveau_alerte, axis=1)
            alertes["Action conseillée"] = alertes.apply(action_coach, axis=1)
            alertes["Priorite"] = alertes["Niveau"].apply(lambda x: 0 if "Critique" in x else 1)
            alertes = alertes.sort_values(by="Priorite")

            st.warning(f"{len(alertes)} joueur(s) en alerte sur les 48 dernières heures")
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

    # KPIs Globaux
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

    # Graphique d'évolution Plotly (coloré par intensité)
    st.subheader(f"Évolution de la charge (sRPE) — {periode}")
    if not df_filtre.empty:
        charge_jour = (
            df_filtre.sort_values("Date")
            .groupby("Seance_ID", sort=False)["Charge_sRPE"]
            .mean()
            .reset_index()
        )
        charge_jour["Couleur"] = charge_jour["Charge_sRPE"].apply(couleur_charge)

        fig_evol = go.Figure()
        fig_evol.add_trace(go.Bar(
            x=charge_jour["Seance_ID"],
            y=charge_jour["Charge_sRPE"],
            marker_color=charge_jour["Couleur"],
            text=charge_jour["Charge_sRPE"].round(0).astype(int).astype(str) + " UA",
            textposition="outside",
            textfont=dict(size=15)
        ))
        fig_evol.add_hline(
            y=700, line_dash="dash", line_color="#EF4444",
            annotation_text="Seuil Surcharge (700 UA)", annotation_position="top left"
        )
        fig_evol.update_layout(
            height=420,
            xaxis_title="",
            yaxis_title="Charge moyenne (UA)",
            yaxis=dict(range=[0, max(charge_jour["Charge_sRPE"].max() * 1.18, 800)]),
            margin=dict(t=30, b=20),
            showlegend=False
        )
        st.plotly_chart(fig_evol, use_container_width=True)

    with st.expander("Guide de lecture des indicateurs (RPE, Charge, Bien-être, ACWR)"):
        st.markdown("""
        * **Vert (< 500 UA) :** Charge faible à modérée (récupération / entretien).
        * **Orange (500 – 700 UA) :** Grosse séance de développement.
        * **Rouge (> 700 UA) :** Très grosse charge (match ou pic hebdomadaire).
        * **Bien-être (/15) :** 12-15 = Frais | 9-11 = Moyen | ≤ 8 = Fatigue importante.
        * **ACWR :** 0,8 à 1,3 = Zone optimale | > 1,5 = Zone rouge (pic trop brutal).
        """)

# ==========================================
# ONGLET 2 : ZOOM SUR UNE SÉANCE PRÉCISE
# ==========================================
with tab2:
    seances_dispo = df.sort_values("Date", ascending=False)["Seance_ID"].unique().tolist()

    if seances_dispo:
        seance_choisie = st.selectbox("Choisir une séance à analyser :", seances_dispo)
        df_seance = df[df["Seance_ID"] == seance_choisie].copy()

        # KPIs de la séance
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Joueurs ayant répondu", f"{df_seance['Joueur'].nunique()}")
        c2.metric("Charge moyenne", f"{df_seance['Charge_sRPE'].mean():.0f} UA")
        c3.metric("RPE moyen", f"{df_seance['RPE'].mean():.1f} / 10")
        c4.metric("Bien-être moyen", f"{df_seance['Score_BienEtre'].mean():.1f} / 15")

        st.divider()

        col_g1, col_g2 = st.columns(2)

        # Graphique 1 : Classement Charge par joueur
        with col_g1:
            st.markdown("**Charge (sRPE) par joueur**")
            df_tri = df_seance.sort_values("Charge_sRPE", ascending=True)
            df_tri["Couleur"] = df_tri["Charge_sRPE"].apply(couleur_charge)
            moy_seance = df_tri["Charge_sRPE"].mean()

            fig_joueurs = go.Figure()
            fig_joueurs.add_trace(go.Bar(
                y=df_tri["Joueur"],
                x=df_tri["Charge_sRPE"],
                orientation="h",
                marker_color=df_tri["Couleur"],
                text=df_tri["Charge_sRPE"].round(0).astype(int).astype(str) + " UA",
                textposition="outside"
            ))
            fig_joueurs.add_vline(
                x=moy_seance, line_dash="dash", line_color="gray",
                annotation_text=f"Moy: {moy_seance:.0f}", annotation_position="top right"
            )
            fig_joueurs.update_layout(
                height=500,
                xaxis_title="Charge sRPE (UA)",
                yaxis_title="",
                xaxis=dict(range=[0, df_tri["Charge_sRPE"].max() * 1.2]),
                margin=dict(t=20, b=20, l=10, r=20),
                showlegend=False
            )
            st.plotly_chart(fig_joueurs, use_container_width=True)

        # Graphique 2 : Matrice Charge vs Bien-être
        with col_g2:
            st.markdown("**Matrice Charge vs Bien-être (Détection Fatigue)**")
            fig_scatter = px.scatter(
                df_seance,
                x="Charge_sRPE",
                y="Score_BienEtre",
                text="Joueur",
                color="Score_BienEtre",
                color_continuous_scale=["#EF4444", "#F59E0B", "#10B981"],
                range_color=[3, 15],
                size="RPE",
                size_max=18,
                hover_data=["RPE", "Duree", "Sommeil", "Fatigue", "Courbatures"]
            )
            # Zone rouge en bas à droite (Grosse charge + Bien-être bas)
            fig_scatter.add_shape(
                type="rect", x0=600, y0=2.5, x1=max(df_seance["Charge_sRPE"].max() * 1.1, 900), y1=8.5,
                fillcolor="rgba(239, 68, 68, 0.15)", line_width=0, layer="below"
            )
            fig_scatter.add_annotation(
                x=max(df_seance["Charge_sRPE"].max() * 0.95, 750), y=3.5,
                text="ZONE À RISQUE", showarrow=False, font=dict(color="#EF4444", size=13)
            )
            fig_scatter.update_traces(textposition="top center", textfont=dict(size=12))
            fig_scatter.update_layout(
                height=500,
                xaxis_title="Charge de la séance (sRPE)",
                yaxis_title="Score Bien-être (/15)",
                yaxis=dict(range=[2.5, 16]),
                coloraxis_showscale=False,
                margin=dict(t=20, b=20)
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

        # Tableau détaillé de la séance
        with st.expander("Voir le tableau détaillé de la séance"):
            st.dataframe(
                df_seance[["Joueur", "Duree", "RPE", "Charge_sRPE", "Sommeil", "Fatigue", "Courbatures", "Score_BienEtre"]]
                .sort_values("Charge_sRPE", ascending=False),
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info("Aucune séance disponible.")
