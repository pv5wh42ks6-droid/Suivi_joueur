import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Suivi-effectif-r1", layout="wide")

# Agrandissement de la police pour une meilleure lisibilité
# Agrandissement de la police et mise en gras pour une meilleure lisibilité

st.markdown("""
    <style>
    html, body, [class*="css"] {
        font-size: 19px !important;
        font-weight: 600 !important;
    }
    h1, h2, h3, [data-testid="stMarkdownContainer"] p {
        font-weight: 700 !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 38px !important;
        font-weight: 800 !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 19px !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 16px !important;
        font-weight: 700 !important;
    }
    button[data-baseweb="tab"] {
        font-weight: 700 !important;
    }
    .stDataFrame {
        font-size: 18px !important;
        font-weight: 600 !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("Suivi-effectif-r1")

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

# Calcul du ratio ACWR global de l'équipe (toujours sur 7j / 28j)
charge_7j = df[df["Date"] >= maintenant - pd.Timedelta(days=7)]["Charge_sRPE"].sum()
charge_28j = df[df["Date"] >= maintenant - pd.Timedelta(days=28)]["Charge_sRPE"].sum()
charge_chronique = charge_28j / 4
jours_historique = (df["Date"].max() - df["Date"].min()).days if not df.empty else 0
acwr = (charge_7j / charge_chronique) if (charge_chronique > 0 and jours_historique >= 21) else None
# Création des 2 onglets principaux
tab1, tab2, tab3 = st.tabs(["📊 Vue Globale & Tendances", "🎯 Zoom sur une séance", "👤 Fiche Joueur"])
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
# Sélecteur du nombre de séances à analyser
    seances_uniques = df.sort_values("Date", ascending=False)["Seance_ID"].unique().tolist()
    nb_max = len(seances_uniques)

    if nb_max > 1:
        nb_seances = st.slider(
            "Nombre de dernières séances à analyser :",
            min_value=1,
            max_value=nb_max,
            value=min(4, nb_max)  # Par défaut : les 4 dernières séances (1 semaine type)
        )
        seances_retenues = seances_uniques[:nb_seances]
        df_filtre = df[df["Seance_ID"].isin(seances_retenues)]
        periode = f"{nb_seances} dernières séances"
    else:
        df_filtre = df
        periode = "Toutes les séances"
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
# ==========================================
# ONGLET 3 : FICHE INDIVIDUELLE JOUEUR
# ==========================================
with tab3:
    liste_joueurs = sorted(df["Joueur"].dropna().unique().tolist())

    if liste_joueurs:
        joueur_choisi = st.selectbox("Sélectionner un joueur :", liste_joueurs)
        df_j = df[df["Joueur"] == joueur_choisi].sort_values("Date").copy()

        # Calcul ACWR individuel
        c_7j = df_j[df_j["Date"] >= maintenant - pd.Timedelta(days=7)]["Charge_sRPE"].sum()
        c_28j = df_j[df_j["Date"] >= maintenant - pd.Timedelta(days=28)]["Charge_sRPE"].sum()
        acwr_j = (c_7j / (c_28j / 4)) if c_28j > 0 else None

        # KPIs du joueur
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Charge moyenne", f"{df_j['Charge_sRPE'].mean():.0f} UA", interpreter_charge(df_j['Charge_sRPE'].mean()), delta_color="off")
        k2.metric("RPE moyen", f"{df_j['RPE'].mean():.1f} / 10", interpreter_rpe(df_j['RPE'].mean()), delta_color="off")
        k3.metric("Bien-être moyen", f"{df_j['Score_BienEtre'].mean():.1f} / 15", interpreter_bien_etre(df_j['Score_BienEtre'].mean()), delta_color="off")
        k4.metric("Ratio ACWR", f"{acwr_j:.2f}" if acwr_j is not None else "N/A", interpreter_acwr(acwr_j), delta_color="off")

        st.divider()

        col_j1, col_j2 = st.columns(2)

        # Graphique 1 : Évolution de sa charge
        with col_j1:
            st.markdown(f"**Évolution de la charge (sRPE) — {joueur_choisi}**")
            df_j["Couleur"] = df_j["Charge_sRPE"].apply(couleur_charge)
            fig_jc = go.Figure()
            fig_jc.add_trace(go.Bar(
                x=df_j["Seance_ID"],
                y=df_j["Charge_sRPE"],
                marker_color=df_j["Couleur"],
                text=df_j["Charge_sRPE"].round(0).astype(int).astype(str) + " UA",
                textposition="outside"
            ))
            fig_jc.add_hline(y=700, line_dash="dash", line_color="#EF4444")
            fig_jc.update_layout(
                height=400,
                xaxis_title="",
                yaxis_title="Charge (UA)",
                yaxis=dict(range=[0, max(df_j["Charge_sRPE"].max() * 1.2, 800)]),
                margin=dict(t=20, b=20),
                showlegend=False
            )
            st.plotly_chart(fig_jc, use_container_width=True)

        # Graphique 2 : Évolution détaillée du bien-être (Sommeil / Fatigue / Courbatures)
        with col_j2:
            st.markdown(f"**Détail Bien-être (/5) — {joueur_choisi}**")
            fig_jbe = go.Figure()
            fig_jbe.add_trace(go.Scatter(x=df_j["Seance_ID"], y=df_j["Sommeil"], mode="lines+markers", name="Sommeil", line=dict(width=3)))
            fig_jbe.add_trace(go.Scatter(x=df_j["Seance_ID"], y=df_j["Fatigue"], mode="lines+markers", name="Forme / Fatigue", line=dict(width=3)))
            fig_jbe.add_trace(go.Scatter(x=df_j["Seance_ID"], y=df_j["Courbatures"], mode="lines+markers", name="État musculaire", line=dict(width=3)))
            fig_jbe.add_hline(y=2.5, line_dash="dash", line_color="#EF4444", annotation_text="Seuil alerte")
            fig_jbe.update_layout(
                height=400,
                xaxis_title="",
                yaxis_title="Note (/5)",
                yaxis=dict(range=[0.5, 5.5], dtick=1),
                margin=dict(t=20, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_jbe, use_container_width=True)

        # Historique complet du joueur
        with st.expander(f"Historique complet de {joueur_choisi}"):
            st.dataframe(
                df_j[["Seance_ID", "Duree", "RPE", "Charge_sRPE", "Sommeil", "Fatigue", "Courbatures", "Score_BienEtre"]]
                .iloc[::-1],
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info("Aucun joueur disponible.")
